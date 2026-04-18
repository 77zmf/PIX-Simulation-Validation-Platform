from __future__ import annotations

import os
import shutil
import socket
import subprocess
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
ROS_SETUP_SCRIPT = Path("/opt/ros/humble/setup.bash")
EXPECTED_ROS_TOPICS = ("/clock", "/tf")


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
    return True


def _entry_by_step(logs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(entry.get("step")): entry for entry in logs}


def _probe_processes(logs: list[dict[str, Any]]) -> dict[str, Any]:
    entries = _entry_by_step(logs)
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    for step_name in EXPECTED_START_STEPS:
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
        if not pid_alive:
            failures.append(step_name)
        checks.append(
            {
                "step": step_name,
                "passed": pid_alive,
                "reason": None if pid_alive else "pid_not_alive",
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


def _ros2_available() -> bool:
    if shutil.which("ros2"):
        return True
    return ROS_SETUP_SCRIPT.exists() and shutil.which("bash") is not None


def _ros_topic_command(ros_domain_id: int, rmw_implementation: str = "") -> list[str] | None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        return None
    rmw_export = f"export RMW_IMPLEMENTATION={rmw_implementation} && " if rmw_implementation else ""
    if ROS_SETUP_SCRIPT.exists():
        shell_command = (
            f"source '{ROS_SETUP_SCRIPT}' >/dev/null 2>&1 && "
            f"export ROS_DOMAIN_ID={ros_domain_id} && {rmw_export}ros2 topic list"
        )
    elif shutil.which("ros2"):
        shell_command = f"export ROS_DOMAIN_ID={ros_domain_id} && {rmw_export}ros2 topic list"
    else:
        return None
    return [bash_path, "-lc", shell_command]


def _probe_ros_graph(
    ros_domain_id: int,
    expected_topics: list[str] | tuple[str, ...] | None = None,
    rmw_implementation: str = "",
) -> dict[str, Any]:
    command = _ros_topic_command(ros_domain_id, rmw_implementation=rmw_implementation)
    topics_to_check = tuple(expected_topics or EXPECTED_ROS_TOPICS)
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
    for attempt in range(1, ROS_GRAPH_ATTEMPTS + 1):
        completed = subprocess.run(command, capture_output=True, text=True)
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
        "stdout_tail": last_stdout[-2000:],
        "stderr_tail": last_stderr[-2000:],
    }


def probe_runtime_health(
    *,
    run_dir: Path,
    slot: RuntimeSlot,
    logs: list[dict[str, Any]],
    runtime_namespace: str,
    expected_ros_topics: list[str] | None = None,
    rmw_implementation: str = "",
) -> dict[str, Any]:
    process_check = _probe_processes(logs)
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
    if ros_graph["available"]:
        required_checks["ros_graph"] = bool(ros_graph["passed"])

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
        "checks": {
            "processes": process_check,
            "carla_rpc_port": port_check,
            "ros_graph": ros_graph,
        },
        "report_path": str(report_path),
    }
    dump_json(report_path, report)
    return report
