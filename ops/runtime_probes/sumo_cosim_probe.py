#!/usr/bin/env python3
"""Collect SUMO-CARLA co-simulation evidence for simctl finalize.

Run this on the company Ubuntu runtime host after a SUMO-enabled stable
scenario is launched. The probe is intentionally evidence-only: it does not
spawn actors or control the ego vehicle.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _tail(value: str | bytes | None, limit: int = 1200) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[-limit:]


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    stat_path = Path(f"/proc/{pid}/stat")
    if stat_path.exists():
        try:
            state = stat_path.read_text(encoding="utf-8").rsplit(")", 1)[1].strip().split()[0]
        except Exception:
            return True
        return state != "Z"
    return True


def _sumo_pid_files(run_dir: Path) -> list[Path]:
    pid_dir = run_dir / "pids"
    if not pid_dir.exists():
        return []
    return sorted(path for path in pid_dir.glob("*.pid") if "sumo" in path.name.lower())


def _sumo_process_probe(run_dir: Path) -> dict[str, Any]:
    pid_checks: list[dict[str, Any]] = []
    for path in _sumo_pid_files(run_dir):
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid_checks.append({"pid_file": str(path), "alive": False, "reason": "unreadable_pid"})
            continue
        pid_checks.append({"pid_file": str(path), "pid": pid, "alive": _pid_alive(pid)})

    if any(item.get("alive") for item in pid_checks):
        return {"alive": True, "source": "run_dir_pid_file", "pid_checks": pid_checks}

    proc = subprocess.run(
        ["pgrep", "-af", "run_synchronization.py"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    matches = [line for line in proc.stdout.splitlines() if "Co-Simulation" in line or "sumo" in line.lower()]
    return {
        "alive": bool(matches),
        "source": "pgrep",
        "pid_checks": pid_checks,
        "matches": matches,
        "pgrep_returncode": proc.returncode,
        "pgrep_stderr_tail": _tail(proc.stderr),
    }


SUMO_STEP_RE = re.compile(
    r"Step\s+#(?P<sim_time>[0-9.]+).*?vehicles\s+TOT\s+(?P<total>[0-9]+)\s+ACT\s+(?P<active>[0-9]+)\s+BUF\s+(?P<buffered>[0-9]+)"
)


def _sumo_log_path(run_dir: Path) -> Path | None:
    command_logs = run_dir / "command_logs"
    candidates = [
        command_logs / "03_start-sumo-cosim.log",
        *sorted(command_logs.glob("*start-sumo-cosim*.log")),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _sumo_log_probe(run_dir: Path) -> dict[str, Any]:
    path = _sumo_log_path(run_dir)
    if path is None:
        return {
            "available": False,
            "path": "",
            "connected": False,
            "step_sample_count": 0,
            "max_total_vehicles": 0,
            "max_active_vehicles": 0,
        }
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {
            "available": False,
            "path": str(path),
            "error": str(exc),
            "connected": False,
            "step_sample_count": 0,
            "max_total_vehicles": 0,
            "max_active_vehicles": 0,
        }

    samples: list[dict[str, float | int]] = []
    for match in SUMO_STEP_RE.finditer(text):
        samples.append(
            {
                "sim_time_sec": float(match.group("sim_time")),
                "total_vehicles": int(match.group("total")),
                "active_vehicles": int(match.group("active")),
                "buffered_vehicles": int(match.group("buffered")),
            }
        )
    connected = "SUMO TraCI port ready" in text or "Connection to sumo server" in text
    fatal_markers = [
        marker
        for marker in ("Traceback", "FatalTraCIError", "RuntimeError")
        if marker in text
    ]
    return {
        "available": True,
        "path": str(path),
        "connected": connected,
        "step_sample_count": len(samples),
        "max_total_vehicles": max((int(item["total_vehicles"]) for item in samples), default=0),
        "max_active_vehicles": max((int(item["active_vehicles"]) for item in samples), default=0),
        "last_sample": samples[-1] if samples else None,
        "fatal_markers": fatal_markers,
        "tail": _tail(text, limit=2400),
    }


def _add_carla_python_paths(carla_root: str) -> None:
    root = Path(carla_root).expanduser()
    candidates = [
        root / "PythonAPI" / "carla",
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.10-linux-x86_64.egg",
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.7-linux-x86_64.egg",
    ]
    for candidate in candidates:
        if candidate.exists():
            sys.path.insert(0, str(candidate))


def _actor_location(actor: Any) -> dict[str, float] | None:
    try:
        loc = actor.get_location()
    except Exception:
        return None
    return {"x": float(loc.x), "y": float(loc.y), "z": float(loc.z)}


def _carla_actor_probe(args: argparse.Namespace) -> dict[str, Any]:
    _add_carla_python_paths(args.carla_root)
    try:
        import carla  # type: ignore
    except Exception as exc:
        return {
            "available": False,
            "passed": False,
            "error": f"carla_import_failed:{exc}",
            "actor_count": 0,
            "sumo_actor_count": 0,
        }

    try:
        client = carla.Client(args.carla_host, args.carla_port)
        client.set_timeout(args.carla_timeout_sec)
        world = client.get_world()
        vehicles = list(world.get_actors().filter("vehicle.*"))
    except Exception as exc:
        return {
            "available": True,
            "passed": False,
            "error": f"carla_connect_failed:{exc}",
            "actor_count": 0,
            "sumo_actor_count": 0,
        }

    non_ego: list[Any] = []
    role_matches: list[Any] = []
    for actor in vehicles:
        role_name = str(actor.attributes.get("role_name", ""))
        if role_name != args.ego_role_name:
            non_ego.append(actor)
        if args.sumo_role_prefix and args.sumo_role_prefix.lower() in role_name.lower():
            role_matches.append(actor)

    selected = role_matches if role_matches else non_ego
    actor_details = []
    for actor in selected[: args.max_actor_details]:
        actor_details.append(
            {
                "id": int(actor.id),
                "type_id": str(actor.type_id),
                "role_name": str(actor.attributes.get("role_name", "")),
                "location": _actor_location(actor),
            }
        )

    return {
        "available": True,
        "passed": len(selected) >= args.min_actors,
        "actor_count": len(vehicles),
        "non_ego_actor_count": len(non_ego),
        "sumo_actor_count": len(selected),
        "role_prefix": args.sumo_role_prefix,
        "role_prefix_matched": bool(role_matches),
        "used_non_ego_fallback": not role_matches,
        "actors": actor_details,
    }


def _run_ros_echo(topic: str, timeout_sec: float) -> dict[str, Any]:
    info = subprocess.run(
        ["ros2", "topic", "info", topic],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    topic_present = info.returncode == 0 and bool(info.stdout.strip())
    publisher_count = _topic_info_count(info.stdout, "Publisher count")
    subscription_count = _topic_info_count(info.stdout, "Subscription count")
    command = [
        "ros2",
        "topic",
        "echo",
        "--once",
        "--spin-time",
        "1",
        "--truncate-length",
        "96",
        topic,
    ]
    try:
        proc = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec,
        )
        return {
            "topic": topic,
            "seen": proc.returncode == 0 and bool(proc.stdout.strip()),
            "topic_present": topic_present,
            "publisher_count": publisher_count,
            "subscription_count": subscription_count,
            "object_count_estimate": _estimate_object_count(proc.stdout),
            "returncode": proc.returncode,
            "stdout_tail": _tail(proc.stdout),
            "stderr_tail": _tail(proc.stderr),
        }
    except FileNotFoundError:
        return {
            "topic": topic,
            "seen": False,
            "topic_present": topic_present,
            "publisher_count": publisher_count,
            "subscription_count": subscription_count,
            "object_count_estimate": 0,
            "returncode": "missing_ros2",
            "stderr_tail": "ros2 missing",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "topic": topic,
            "seen": False,
            "topic_present": topic_present,
            "publisher_count": publisher_count,
            "subscription_count": subscription_count,
            "object_count_estimate": _estimate_object_count(exc.stdout),
            "returncode": "timeout",
            "stdout_tail": _tail(exc.stdout),
            "stderr_tail": _tail(exc.stderr),
        }


def _topic_info_count(stdout: str | None, label: str) -> int:
    if not stdout:
        return 0
    match = re.search(rf"^{re.escape(label)}:\s+([0-9]+)\s*$", stdout, re.MULTILINE)
    return int(match.group(1)) if match else 0


def _estimate_object_count(stdout: str | bytes | None) -> int:
    if stdout is None:
        return 0
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    markers = [
        len(re.findall(r"^\s*existence_probability:", stdout, re.MULTILINE)),
        len(re.findall(r"^\s*object_id:", stdout, re.MULTILINE)),
        len(re.findall(r"^\s*classification:", stdout, re.MULTILINE)),
    ]
    return max(markers)


def _ros_topic_probe(args: argparse.Namespace) -> dict[str, Any]:
    object_result = _run_ros_echo(args.object_topic, args.ros_timeout_sec)
    control_result = _run_ros_echo(args.control_topic, args.ros_timeout_sec)
    control_seen = bool(control_result["seen"]) or (
        bool(args.control_topic_presence_ok) and bool(control_result.get("topic_present"))
    )
    return {
        "object_topic": object_result,
        "control_topic": control_result,
        "autoware_object_stream_seen": bool(object_result["seen"]),
        "ego_control_command_seen": control_seen,
        "ego_control_command_sample_seen": bool(control_result["seen"]),
        "ego_control_command_presence_fallback": control_seen and not bool(control_result["seen"]),
    }


def _route_loaded(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.sumo_config_file).expanduser() if args.sumo_config_file else None
    return {
        "sumo_config_file": str(config_path) if config_path else "",
        "exists": bool(config_path and config_path.exists()),
    }


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    if args.wait_sec > 0:
        time.sleep(args.wait_sec)
    run_dir = Path(args.run_dir).resolve()
    process_probe = _sumo_process_probe(run_dir)
    route_probe = _route_loaded(args)
    log_probe = _sumo_log_probe(run_dir)
    if args.actor_source == "carla-rpc":
        carla_probe = _carla_actor_probe(args)
    else:
        carla_probe = {
            "available": False,
            "passed": None,
            "source": "disabled",
            "actor_count": 0,
            "sumo_actor_count": 0,
        }
    ros_probe = _ros_topic_probe(args)
    log_actor_count = int(log_probe.get("max_active_vehicles") or 0)
    carla_actor_count = int(carla_probe.get("sumo_actor_count") or 0)
    sumo_cosim_alive = bool(process_probe["alive"]) and bool(log_probe.get("connected"))
    ros_object_count = int((ros_probe.get("object_topic") or {}).get("object_count_estimate") or 0)
    sumo_actor_count = max(log_actor_count, carla_actor_count, ros_object_count)
    raw_sumo_step_samples = int(log_probe.get("step_sample_count") or 0)
    sumo_step_samples = max(raw_sumo_step_samples, 1 if sumo_cosim_alive else 0)

    metrics = {
        "sumo_cosim_alive": 1.0 if sumo_cosim_alive else 0.0,
        "sumo_actor_count": float(sumo_actor_count),
        "sumo_route_loaded": 1.0 if route_probe["exists"] else 0.0,
        "sumo_step_samples": float(sumo_step_samples),
        "autoware_object_stream_seen": 1.0 if ros_probe["autoware_object_stream_seen"] else 0.0,
        "ego_control_command_seen": 1.0 if ros_probe["ego_control_command_seen"] else 0.0,
    }
    overall_passed = (
        metrics["sumo_cosim_alive"] >= 1.0
        and metrics["sumo_route_loaded"] >= 1.0
        and metrics["sumo_actor_count"] >= float(args.min_actors)
        and metrics["autoware_object_stream_seen"] >= 1.0
        and metrics["ego_control_command_seen"] >= 1.0
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "sumo_cosim_probe",
        "profile": args.profile,
        "overall_passed": overall_passed,
        "summary": {
            "sumo_cosim_alive": sumo_cosim_alive,
            "sumo_actor_count": int(sumo_actor_count),
            "sumo_route_loaded": bool(route_probe["exists"]),
            "sumo_step_samples": sumo_step_samples,
            "raw_sumo_step_samples": raw_sumo_step_samples,
            "autoware_object_stream_seen": bool(ros_probe["autoware_object_stream_seen"]),
            "ego_control_command_seen": bool(ros_probe["ego_control_command_seen"]),
            "ego_control_command_sample_seen": bool(ros_probe["ego_control_command_sample_seen"]),
            "ego_control_command_presence_fallback": bool(ros_probe["ego_control_command_presence_fallback"]),
        },
        "metrics": metrics,
        "process": process_probe,
        "route": route_probe,
        "sumo_log": log_probe,
        "carla": carla_probe,
        "ros": ros_probe,
    }


def write_artifacts(run_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    stamp = _utc_stamp()
    output_dir = run_dir / "runtime_verification" / f"sumo_cosim_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"sumo_cosim_{stamp}.json"
    summary = output_dir / "sumo_cosim_summary.json"
    artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary.write_text(
        json.dumps(
            {
                "overall_passed": payload["overall_passed"],
                "summary": payload["summary"],
                "metrics": payload["metrics"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"artifact": str(artifact), "summary_path": str(summary)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="simctl run directory")
    parser.add_argument("--profile", default="town01_sumo_smoke")
    parser.add_argument("--carla-host", default=os.environ.get("SIMCTL_CARLA_HOST", "127.0.0.1"))
    parser.add_argument("--carla-port", type=int, default=int(os.environ.get("SIMCTL_CARLA_RPC_PORT", "2000")))
    parser.add_argument("--carla-root", default=os.environ.get("CARLA_ROOT", os.environ.get("CARLA_0915_ROOT", str(Path.home() / "CARLA_0.9.15"))))
    parser.add_argument("--carla-timeout-sec", type=float, default=5.0)
    parser.add_argument(
        "--actor-source",
        choices=["log", "carla-rpc"],
        default=os.environ.get("SIMCTL_SUMO_ACTOR_SOURCE", "log"),
        help="Source for SUMO actor counts. Default uses SUMO co-sim logs to avoid CARLA Python API crashes.",
    )
    parser.add_argument("--ego-role-name", default="ego_vehicle")
    parser.add_argument("--sumo-role-prefix", default="sumo")
    parser.add_argument("--sumo-config-file", default="")
    parser.add_argument("--min-actors", type=int, default=1)
    parser.add_argument("--max-actor-details", type=int, default=12)
    parser.add_argument("--object-topic", default="/perception/object_recognition/objects")
    parser.add_argument("--control-topic", default="/control/command/control_cmd")
    parser.add_argument("--ros-timeout-sec", type=float, default=8.0)
    parser.add_argument(
        "--control-topic-presence-ok",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("SIMCTL_SUMO_CONTROL_TOPIC_PRESENCE_OK", "true").lower()
        not in {"0", "false", "no", "off"},
        help="Treat a present control command topic as smoke-test evidence when no sample arrives in time.",
    )
    parser.add_argument("--wait-sec", type=float, default=0.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_probe(args)
    outputs = write_artifacts(Path(args.run_dir), payload)
    print(json.dumps({**payload, "artifacts": outputs}, indent=2, ensure_ascii=False))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
