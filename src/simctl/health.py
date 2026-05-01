from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .config import dump_json, utc_now
from .models import RuntimeSlot


EXPECTED_START_STEPS = (
    "start-carla-server",
    "start-autoware-bridge",
    "start-autoware-stack",
    "start-carla-localization-bridge",
)

PORT_CHECK_ATTEMPTS = int(os.environ.get("SIMCTL_HEALTH_PORT_ATTEMPTS", "12"))
PORT_CHECK_WAIT_SEC = float(os.environ.get("SIMCTL_HEALTH_PORT_WAIT_SEC", "1.0"))
PORT_CONNECT_TIMEOUT_SEC = float(os.environ.get("SIMCTL_HEALTH_PORT_TIMEOUT_SEC", "0.5"))
ROS_GRAPH_ATTEMPTS = int(os.environ.get("SIMCTL_HEALTH_ROS_ATTEMPTS", "20"))
ROS_GRAPH_WAIT_SEC = float(os.environ.get("SIMCTL_HEALTH_ROS_WAIT_SEC", "1.0"))
ROS_GRAPH_COMMAND_TIMEOUT_SEC = float(os.environ.get("SIMCTL_HEALTH_ROS_COMMAND_TIMEOUT_SEC", "5.0"))
CARLA_ACTOR_ATTEMPTS = int(os.environ.get("SIMCTL_HEALTH_CARLA_ACTOR_ATTEMPTS", "20"))
CARLA_ACTOR_WAIT_SEC = float(os.environ.get("SIMCTL_HEALTH_CARLA_ACTOR_WAIT_SEC", "1.0"))
CARLA_CLIENT_TIMEOUT_SEC = float(os.environ.get("SIMCTL_HEALTH_CARLA_CLIENT_TIMEOUT_SEC", "3.0"))
ROS_SETUP_SCRIPT = Path("/opt/ros/humble/setup.bash")
EXPECTED_ROS_TOPICS = ("/clock", "/tf")
CRASH_LOG_PATTERNS = (
    "Signal 11 caught",
    "Segmentation fault",
    "LowLevelFatalError",
    "Fatal error",
    "Exception thrown:",
)


def _sleep_if_needed(wait_sec: float, *, attempt: int, attempts: int) -> None:
    if attempt < attempts:
        time.sleep(wait_sec)


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    if _pid_state(pid) == "Z":
        return False
    return True


def _pid_state(pid: int) -> str | None:
    try:
        stat_text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return stat_text.rsplit(")", 1)[1].strip().split()[0]
    except IndexError:
        return None


def _launch_log_crash_reason(log_path: str | None) -> str | None:
    if not log_path:
        return None
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for pattern in CRASH_LOG_PATTERNS:
        if pattern in text:
            return f"crash_log:{pattern}"
    return None


def _entry_by_step(logs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(entry.get("step")): entry for entry in logs}


def _process_steps_to_check(
    logs: list[dict[str, Any]],
    expected_start_steps: list[str] | tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    steps = list(EXPECTED_START_STEPS if expected_start_steps is None else expected_start_steps)
    for entry in logs:
        step = str(entry.get("step") or "")
        if entry.get("status") == "started" and step and step not in steps:
            steps.append(step)
    return tuple(steps)


def _probe_processes(
    logs: list[dict[str, Any]],
    expected_start_steps: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    entries = _entry_by_step(logs)
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    for step_name in _process_steps_to_check(logs, expected_start_steps=expected_start_steps):
        entry = entries.get(step_name)
        if entry is None:
            failures.append(step_name)
            checks.append({"step": step_name, "passed": False, "reason": "missing_launch_log"})
            continue

        if entry.get("status") != "started":
            failures.append(step_name)
            checks.append(
                {
                    "step": step_name,
                    "passed": False,
                    "reason": "process_not_running",
                    "status": entry.get("status"),
                    "returncode": entry.get("returncode"),
                    "log_path": entry.get("log_path"),
                }
            )
            continue

        pid = int(entry.get("pid", 0) or 0)
        pid_alive = _pid_is_alive(pid)
        crash_reason = _launch_log_crash_reason(entry.get("log_path"))
        passed = pid_alive and crash_reason is None
        if not passed:
            failures.append(step_name)
        checks.append(
            {
                "step": step_name,
                "passed": passed,
                "reason": crash_reason if crash_reason else (None if pid_alive else "pid_not_alive"),
                "pid": pid,
                "pid_file": entry.get("pid_file"),
                "log_path": entry.get("log_path"),
            }
        )

    return {
        "passed": not failures,
        "failed_steps": failures,
        "process_checks": checks,
    }


def _probe_tcp_port(port: int, *, host: str = "127.0.0.1") -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, PORT_CHECK_ATTEMPTS + 1):
        try:
            with socket.create_connection((host, port), timeout=PORT_CONNECT_TIMEOUT_SEC):
                return {
                    "passed": True,
                    "host": host,
                    "port": port,
                    "attempts": attempt,
                }
        except OSError as exc:
            last_error = str(exc)
            _sleep_if_needed(PORT_CHECK_WAIT_SEC, attempt=attempt, attempts=PORT_CHECK_ATTEMPTS)
    return {
        "passed": False,
        "host": host,
        "port": port,
        "attempts": PORT_CHECK_ATTEMPTS,
        "error": last_error or "tcp_connect_failed",
    }


def _actor_role(actor: Any) -> str:
    return str(getattr(actor, "attributes", {}).get("role_name", ""))


def _actor_payload(actor: Any) -> dict[str, Any]:
    payload = {
        "id": int(getattr(actor, "id", 0) or 0),
        "type_id": str(getattr(actor, "type_id", "")),
        "role_name": _actor_role(actor),
    }
    try:
        transform = actor.get_transform()
    except RuntimeError:
        return payload
    location = getattr(transform, "location", None)
    rotation = getattr(transform, "rotation", None)
    if location is not None:
        payload["location_m"] = {
            "x": round(float(location.x), 6),
            "y": round(float(location.y), 6),
            "z": round(float(location.z), 6),
        }
    if rotation is not None:
        payload["rotation_deg"] = {
            "pitch": round(float(rotation.pitch), 6),
            "yaw": round(float(rotation.yaw), 6),
            "roll": round(float(rotation.roll), 6),
        }
    return payload


def _probe_carla_actor(
    *,
    port: int,
    carla_root: str,
    actor_type: str,
    ego_role_name: str,
    host: str = "127.0.0.1",
    attempts: int | None = None,
    wait_sec: float | None = None,
) -> dict[str, Any]:
    actor_type = actor_type.strip()
    ego_role_name = ego_role_name.strip()
    if not actor_type and not ego_role_name:
        return {
            "required": False,
            "passed": None,
            "skipped_reason": "carla_actor_not_configured",
        }

    attempts = CARLA_ACTOR_ATTEMPTS if attempts is None else attempts
    wait_sec = CARLA_ACTOR_WAIT_SEC if wait_sec is None else wait_sec
    python_executable = os.environ.get("SIMCTL_CARLA_PYTHON") or shutil.which("python3") or sys.executable
    script = r"""
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

config = json.loads(sys.stdin.read())
root = Path(config["carla_root"]).expanduser()
if importlib.util.find_spec("carla") is None:
    candidates = [
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.10-linux-x86_64.egg",
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.7-linux-x86_64.egg",
        root / "PythonAPI" / "carla",
    ]
    for candidate in candidates:
        if candidate.exists():
            sys.path.insert(0, str(candidate))

def actor_role(actor):
    return str(getattr(actor, "attributes", {}).get("role_name", ""))

def actor_payload(actor):
    payload = {
        "id": int(getattr(actor, "id", 0) or 0),
        "type_id": str(getattr(actor, "type_id", "")),
        "role_name": actor_role(actor),
    }
    try:
        transform = actor.get_transform()
    except RuntimeError:
        return payload
    location = getattr(transform, "location", None)
    rotation = getattr(transform, "rotation", None)
    if location is not None:
        payload["location_m"] = {
            "x": round(float(location.x), 6),
            "y": round(float(location.y), 6),
            "z": round(float(location.z), 6),
        }
    if rotation is not None:
        payload["rotation_deg"] = {
            "pitch": round(float(rotation.pitch), 6),
            "yaw": round(float(rotation.yaw), 6),
            "roll": round(float(rotation.roll), 6),
        }
    return payload

try:
    import carla
except ImportError as exc:
    print(json.dumps({
        "required": True,
        "passed": False,
        "host": config["host"],
        "port": config["port"],
        "actor_type": config["actor_type"],
        "ego_role_name": config["ego_role_name"],
        "error": f"carla_python_api_unavailable:{exc}",
    }))
    raise SystemExit(0)

last_error = ""
last_vehicle_count = 0
last_world_map = ""
last_actors = []
client = carla.Client(config["host"], int(config["port"]))
client.set_timeout(float(config["client_timeout_sec"]))
for attempt in range(1, int(config["attempts"]) + 1):
    try:
        world = client.get_world()
        last_world_map = str(world.get_map().name)
        actors = list(world.get_actors().filter("vehicle.*"))
        last_vehicle_count = len(actors)
        last_actors = [actor_payload(actor) for actor in actors[:12]]
        for actor in actors:
            type_match = not config["actor_type"] or str(getattr(actor, "type_id", "")) == config["actor_type"]
            role_match = not config["ego_role_name"] or actor_role(actor) == config["ego_role_name"]
            if type_match and role_match:
                print(json.dumps({
                    "required": True,
                    "passed": True,
                    "host": config["host"],
                    "port": config["port"],
                    "attempts": attempt,
                    "world_map": last_world_map,
                    "actor_type": config["actor_type"],
                    "ego_role_name": config["ego_role_name"],
                    "vehicle_count": last_vehicle_count,
                    "matched_actor": actor_payload(actor),
                }))
                raise SystemExit(0)
    except (OSError, RuntimeError) as exc:
        last_error = str(exc)
    if attempt < int(config["attempts"]):
        time.sleep(float(config["wait_sec"]))

print(json.dumps({
    "required": True,
    "passed": False,
    "host": config["host"],
    "port": config["port"],
    "attempts": int(config["attempts"]),
    "world_map": last_world_map,
    "actor_type": config["actor_type"],
    "ego_role_name": config["ego_role_name"],
    "vehicle_count": last_vehicle_count,
    "sample_actors": last_actors,
    "error": last_error or "carla_actor_not_found",
}))
"""
    payload = {
        "host": host,
        "port": port,
        "carla_root": carla_root,
        "actor_type": actor_type,
        "ego_role_name": ego_role_name,
        "attempts": attempts,
        "wait_sec": wait_sec,
        "client_timeout_sec": CARLA_CLIENT_TIMEOUT_SEC,
    }
    timeout_sec = max(5.0, attempts * (wait_sec + CARLA_CLIENT_TIMEOUT_SEC) + 5.0)
    try:
        completed = subprocess.run(
            [python_executable, "-c", script],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "required": True,
            "passed": False,
            "host": host,
            "port": port,
            "actor_type": actor_type,
            "ego_role_name": ego_role_name,
            "python_executable": python_executable,
            "error": "carla_actor_probe_timeout",
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        }

    if completed.returncode != 0:
        return {
            "required": True,
            "passed": False,
            "host": host,
            "port": port,
            "actor_type": actor_type,
            "ego_role_name": ego_role_name,
            "python_executable": python_executable,
            "error": f"carla_actor_probe_process_failed:{completed.returncode}",
            "stdout_tail": (completed.stdout or "")[-2000:],
            "stderr_tail": (completed.stderr or "")[-2000:],
        }

    stdout = (completed.stdout or "").strip()
    try:
        result = json.loads(stdout.splitlines()[-1])
    except (IndexError, ValueError):
        return {
            "required": True,
            "passed": False,
            "host": host,
            "port": port,
            "actor_type": actor_type,
            "ego_role_name": ego_role_name,
            "python_executable": python_executable,
            "error": "carla_actor_probe_invalid_json",
            "stdout_tail": stdout[-2000:],
            "stderr_tail": (completed.stderr or "")[-2000:],
        }

    result["python_executable"] = python_executable
    return result


def _ros2_available() -> bool:
    if shutil.which("ros2"):
        return True
    return ROS_SETUP_SCRIPT.exists() and shutil.which("bash") is not None


def _ros_topic_command(ros_domain_id: int, rmw_implementation: str = "") -> list[str] | None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        return None
    rmw_export = f"export RMW_IMPLEMENTATION={rmw_implementation} && " if rmw_implementation else ""
    daemon_export = "export ROS2CLI_DISABLE_DAEMON=1 && "
    if ROS_SETUP_SCRIPT.exists():
        shell_command = (
            f"source '{ROS_SETUP_SCRIPT}' >/dev/null 2>&1 && "
            f"export ROS_DOMAIN_ID={ros_domain_id} && {rmw_export}{daemon_export}ros2 topic list"
        )
    elif shutil.which("ros2"):
        shell_command = f"export ROS_DOMAIN_ID={ros_domain_id} && {rmw_export}{daemon_export}ros2 topic list"
    else:
        return None
    return [bash_path, "-lc", shell_command]


def _probe_ros_graph(
    ros_domain_id: int,
    expected_topics: list[str] | tuple[str, ...] | None = None,
    rmw_implementation: str = "",
) -> dict[str, Any]:
    command = _ros_topic_command(ros_domain_id, rmw_implementation=rmw_implementation)
    topics_to_check = tuple(EXPECTED_ROS_TOPICS if expected_topics is None else expected_topics)
    if not _ros2_available() or command is None:
        return {
            "available": False,
            "passed": None,
            "skipped_reason": "ros2_cli_unavailable",
            "expected_topics": list(topics_to_check),
            "rmw_implementation": rmw_implementation,
        }

    last_stdout = ""
    last_stderr = ""
    missing_topics = list(topics_to_check)
    timed_out = False
    for attempt in range(1, ROS_GRAPH_ATTEMPTS + 1):
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=ROS_GRAPH_COMMAND_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            last_stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            last_stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            _sleep_if_needed(ROS_GRAPH_WAIT_SEC, attempt=attempt, attempts=ROS_GRAPH_ATTEMPTS)
            continue
        last_stdout = completed.stdout or ""
        last_stderr = completed.stderr or ""
        if completed.returncode == 0:
            topics = sorted({line.strip() for line in last_stdout.splitlines() if line.strip()})
            missing_topics = [topic for topic in topics_to_check if topic not in topics]
            if not missing_topics:
                return {
                    "available": True,
                    "passed": True,
                    "attempts": attempt,
                    "expected_topics": list(topics_to_check),
                    "rmw_implementation": rmw_implementation,
                    "topics": topics,
                }
        _sleep_if_needed(ROS_GRAPH_WAIT_SEC, attempt=attempt, attempts=ROS_GRAPH_ATTEMPTS)

    return {
        "available": True,
        "passed": False,
        "attempts": ROS_GRAPH_ATTEMPTS,
        "expected_topics": list(topics_to_check),
        "rmw_implementation": rmw_implementation,
        "missing_topics": missing_topics,
        "command_timeout_sec": ROS_GRAPH_COMMAND_TIMEOUT_SEC,
        "timed_out": timed_out,
        "stdout_tail": last_stdout[-2000:],
        "stderr_tail": last_stderr[-2000:],
    }


def probe_runtime_health(
    *,
    run_dir: Path,
    slot: RuntimeSlot,
    logs: list[dict[str, Any]],
    runtime_namespace: str,
    expected_process_steps: list[str] | None = None,
    expected_ros_topics: list[str] | None = None,
    rmw_implementation: str = "",
    carla_actor_check: bool = False,
    carla_actor_type: str = "",
    carla_ego_role_name: str = "",
    carla_root: str = "",
) -> dict[str, Any]:
    process_check = _probe_processes(logs, expected_start_steps=expected_process_steps)
    port_check = _probe_tcp_port(slot.carla_rpc_port)
    ros_graph = _probe_ros_graph(
        slot.ros_domain_id,
        expected_topics=expected_ros_topics,
        rmw_implementation=rmw_implementation,
    )

    required_checks = {
        "processes": process_check["passed"],
        "carla_rpc_port": port_check["passed"],
    }
    checks: dict[str, Any] = {
        "processes": process_check,
        "carla_rpc_port": port_check,
        "ros_graph": ros_graph,
    }
    if ros_graph["available"]:
        required_checks["ros_graph"] = bool(ros_graph["passed"])
    if carla_actor_check:
        actor_check = _probe_carla_actor(
            port=slot.carla_rpc_port,
            carla_root=carla_root,
            actor_type=carla_actor_type,
            ego_role_name=carla_ego_role_name,
        )
        required_checks["carla_actor"] = bool(actor_check["passed"])
        checks["carla_actor"] = actor_check

    failed_checks = [name for name, passed in required_checks.items() if not passed]
    report_path = run_dir / "health.json"
    report = {
        "checked_at": utc_now(),
        "passed": not failed_checks,
        "failed_checks": failed_checks,
        "slot_id": slot.slot_id,
        "carla_rpc_port": slot.carla_rpc_port,
        "traffic_manager_port": slot.traffic_manager_port,
        "ros_domain_id": slot.ros_domain_id,
        "rmw_implementation": rmw_implementation,
        "runtime_namespace": runtime_namespace,
        "checks": checks,
        "report_path": str(report_path),
    }
    dump_json(report_path, report)
    return report
