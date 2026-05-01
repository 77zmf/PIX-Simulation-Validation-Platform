#!/usr/bin/env python3
"""Run-scoped preflight for stable CARLA/Autoware executions.

The script writes `host_bom.json` and `preflight_report.json` into the current
run directory before the stable stack starts long-running processes.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def read_os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    if not path.exists():
        return {}
    payload: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        payload[key] = value.strip().strip('"')
    return payload


def run_command(command: list[str], timeout_sec: float = 3.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except Exception as exc:
        return {"available": False, "error": str(exc), "command": command}
    return {
        "available": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-1200:],
        "stderr_tail": (completed.stderr or "")[-1200:],
        "command": command,
    }


def collect_host_bom(args: argparse.Namespace) -> dict[str, Any]:
    commands = {
        "python3": run_command(["python3", "--version"]),
        "ros2": run_command(["bash", "-lc", "source /opt/ros/humble/setup.bash >/dev/null 2>&1; ros2 --help >/dev/null && echo ros2_ok"]),
        "sumo": run_command([args.sumo_binary or "sumo", "--version"]) if args.sumo_binary else {"available": False},
        "nvidia_smi": run_command(["nvidia-smi", "-L"]),
    }
    return {
        "generated_at": utc_now(),
        "hostname": platform.node(),
        "user": os.environ.get("USER", ""),
        "cwd": os.getcwd(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "os_release": read_os_release(),
        "paths": {
            "run_dir": str(Path(args.run_dir).resolve()),
            "scenario": args.scenario,
            "carla_root": args.carla_root,
            "carla_map": args.carla_map,
            "autoware_enabled": args.autoware_enabled,
            "autoware_ws": args.autoware_ws,
            "autoware_bridge_ws": args.autoware_bridge_ws,
            "autoware_underlay_ws": args.autoware_underlay_ws,
            "autoware_map_path": args.autoware_map_path,
            "sensor_mapping_file": args.sensor_mapping_file,
            "sensor_kit_calibration_file": args.sensor_kit_calibration_file,
            "objects_definition_file": args.objects_definition_file,
            "sumo_config_file": args.sumo_config_file,
        },
        "ports": {
            "carla_rpc_port": args.carla_port,
            "traffic_manager_port": args.traffic_manager_port,
            "sumo_traci_port": args.sumo_traci_port,
        },
        "commands": commands,
    }


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, severity: str, detail: str, **extra: Any) -> None:
    checks.append(
        {
            "id": check_id,
            "passed": bool(passed),
            "severity": severity,
            "detail": detail,
            **extra,
        }
    )


def check_path(
    checks: list[dict[str, Any]],
    check_id: str,
    raw_path: str,
    *,
    kind: str,
    severity: str,
    skip_if_empty: bool = True,
) -> None:
    if not raw_path:
        if not skip_if_empty:
            add_check(checks, check_id, False, severity, "path is empty")
        return
    path = Path(raw_path).expanduser()
    if kind == "dir":
        passed = path.is_dir()
    elif kind == "file":
        passed = path.is_file()
    elif kind == "executable":
        passed = path.is_file() and os.access(path, os.X_OK)
    else:
        raise ValueError(f"unknown path check kind: {kind}")
    status = "exists" if passed else "missing"
    add_check(checks, check_id, passed, severity, f"{kind} {status}: {path}", path=str(path))


def resolve_sumo_config(args: argparse.Namespace) -> str:
    if args.sumo_config_file:
        return args.sumo_config_file
    if not args.carla_root:
        return ""
    carla_root = Path(args.carla_root).expanduser()
    map_name = args.carla_map or "Town01"
    candidates = [
        carla_root / "Co-Simulation" / "Sumo" / "examples" / f"{map_name}.sumocfg",
        carla_root / "Co-Simulation" / "Sumo" / "examples" / "Town01.sumocfg",
        carla_root / "Co-Simulation" / "Sumo" / "examples" / map_name / f"{map_name}.sumocfg",
        carla_root / "Co-Simulation" / "Sumo" / "examples" / "Town01" / "Town01.sumocfg",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return str(candidates[0])


def resolve_sumo_cosim_script(args: argparse.Namespace) -> str:
    if args.sumo_cosim_script:
        return args.sumo_cosim_script
    if not args.carla_root:
        return ""
    carla_root = Path(args.carla_root).expanduser()
    candidates = [
        carla_root / "Co-Simulation" / "Sumo" / "run_synchronization.py",
        carla_root / "PythonAPI" / "examples" / "sumo" / "run_synchronization.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return str(candidates[0])


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    if port <= 0:
        return True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) != 0


def check_port(checks: list[dict[str, Any]], check_id: str, port_text: str, severity: str) -> None:
    if not port_text:
        return
    try:
        port = int(port_text)
    except ValueError:
        add_check(checks, check_id, False, severity, f"invalid port: {port_text}", port=port_text)
        return
    add_check(checks, check_id, port_is_free(port), severity, f"port is free before launch: {port}", port=port)


def meminfo_gb() -> dict[str, float]:
    path = Path("/proc/meminfo")
    if not path.exists():
        return {}
    values: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            key = parts[0].rstrip(":")
            try:
                values[key] = float(parts[1]) / (1024.0 * 1024.0)
            except ValueError:
                continue
    return {
        "mem_available_gb": values.get("MemAvailable", 0.0),
        "swap_free_gb": values.get("SwapFree", 0.0),
    }


def check_resources(checks: list[dict[str, Any]], args: argparse.Namespace) -> None:
    usage = shutil.disk_usage(Path(args.run_dir).resolve())
    disk_free_gb = usage.free / (1024.0**3)
    add_check(
        checks,
        "disk_free",
        disk_free_gb >= float(args.min_disk_free_gb),
        "hard",
        f"disk free {disk_free_gb:.1f} GiB >= {float(args.min_disk_free_gb):.1f} GiB",
        free_gb=round(disk_free_gb, 3),
        threshold_gb=float(args.min_disk_free_gb),
    )

    memory = meminfo_gb()
    if not memory:
        add_check(checks, "memory_available", True, "warn", "memory data unavailable on this host")
        add_check(checks, "swap_free", True, "warn", "swap data unavailable on this host")
        return
    mem_available = memory.get("mem_available_gb", 0.0)
    swap_free = memory.get("swap_free_gb", 0.0)
    add_check(
        checks,
        "memory_available",
        mem_available >= float(args.min_mem_available_gb),
        "hard",
        f"memory available {mem_available:.1f} GiB >= {float(args.min_mem_available_gb):.1f} GiB",
        available_gb=round(mem_available, 3),
        threshold_gb=float(args.min_mem_available_gb),
    )
    add_check(
        checks,
        "swap_free",
        swap_free >= float(args.min_swap_free_gb),
        "hard",
        f"swap free {swap_free:.1f} GiB >= {float(args.min_swap_free_gb):.1f} GiB",
        free_gb=round(swap_free, 3),
        threshold_gb=float(args.min_swap_free_gb),
    )


def run_preflight(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []

    add_check(checks, "run_dir_writable", os.access(run_dir, os.W_OK), "hard", f"run dir is writable: {run_dir}")
    check_resources(checks, args)
    check_port(checks, "carla_rpc_port_free", args.carla_port, "hard")
    check_port(checks, "traffic_manager_port_free", args.traffic_manager_port, "hard")

    check_path(checks, "carla_root", args.carla_root, kind="dir", severity="hard", skip_if_empty=False)
    if args.carla_root:
        carla_root = Path(args.carla_root).expanduser()
        check_path(checks, "carla_launcher", str(carla_root / "CarlaUE4.sh"), kind="file", severity="hard")
    else:
        check_path(checks, "carla_launcher", "", kind="file", severity="hard", skip_if_empty=False)
    if parse_bool(args.autoware_enabled):
        check_path(
            checks,
            "autoware_ws_setup",
            str(Path(args.autoware_ws) / "install" / "setup.bash") if args.autoware_ws else "",
            kind="file",
            severity="hard",
            skip_if_empty=False,
        )
        check_path(
            checks,
            "autoware_bridge_ws_setup",
            str(Path(args.autoware_bridge_ws) / "install" / "setup.bash") if args.autoware_bridge_ws else "",
            kind="file",
            severity="hard",
            skip_if_empty=False,
        )
        check_path(
            checks,
            "autoware_underlay_ws_setup",
            str(Path(args.autoware_underlay_ws) / "install" / "setup.bash") if args.autoware_underlay_ws else "",
            kind="file",
            severity="hard",
            skip_if_empty=False,
        )
        check_path(checks, "autoware_map_path", args.autoware_map_path, kind="dir", severity="hard", skip_if_empty=False)
        check_path(checks, "sensor_mapping_file", args.sensor_mapping_file, kind="file", severity="hard", skip_if_empty=False)
        check_path(checks, "sensor_kit_calibration_file", args.sensor_kit_calibration_file, kind="file", severity="hard", skip_if_empty=False)
        check_path(checks, "objects_definition_file", args.objects_definition_file, kind="file", severity="hard", skip_if_empty=False)
    else:
        add_check(checks, "autoware_disabled", True, "warn", "Autoware and bridge path checks skipped")

    if parse_bool(args.sumo_enabled):
        check_port(checks, "sumo_traci_port_free", args.sumo_traci_port, "hard")
        sumo_binary = args.sumo_binary or "sumo"
        add_check(
            checks,
            "sumo_binary",
            shutil.which(sumo_binary) is not None,
            "hard",
            f"SUMO binary is available: {sumo_binary}",
            resolved_path=shutil.which(sumo_binary),
        )
        check_path(checks, "sumo_config_file", resolve_sumo_config(args), kind="file", severity="hard", skip_if_empty=False)
        check_path(checks, "sumo_cosim_script", resolve_sumo_cosim_script(args), kind="file", severity="hard", skip_if_empty=False)

    hard_failures = [check for check in checks if check["severity"] == "hard" and not check["passed"]]
    report = {
        "generated_at": utc_now(),
        "kind": "stable_run_preflight",
        "scenario": args.scenario,
        "run_dir": str(run_dir),
        "passed": not hard_failures,
        "strict": parse_bool(args.strict),
        "summary": {
            "check_count": len(checks),
            "hard_failure_count": len(hard_failures),
        },
        "checks": checks,
    }
    (run_dir / "host_bom.json").write_text(json.dumps(collect_host_bom(args), indent=2), encoding="utf-8")
    (run_dir / "preflight_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--scenario", default="")
    parser.add_argument("--carla-root", default="")
    parser.add_argument("--carla-map", default="")
    parser.add_argument("--autoware-enabled", default="true")
    parser.add_argument("--autoware-ws", default="")
    parser.add_argument("--autoware-bridge-ws", default="")
    parser.add_argument("--autoware-underlay-ws", default="")
    parser.add_argument("--autoware-map-path", default="")
    parser.add_argument("--sensor-mapping-file", default="")
    parser.add_argument("--sensor-kit-calibration-file", default="")
    parser.add_argument("--objects-definition-file", default="")
    parser.add_argument("--carla-port", default="")
    parser.add_argument("--traffic-manager-port", default="")
    parser.add_argument("--sumo-enabled", default="false")
    parser.add_argument("--sumo-traci-port", default="")
    parser.add_argument("--sumo-binary", default="sumo")
    parser.add_argument("--sumo-config-file", default="")
    parser.add_argument("--sumo-cosim-script", default="")
    parser.add_argument("--min-disk-free-gb", type=float, default=20.0)
    parser.add_argument("--min-mem-available-gb", type=float, default=1.0)
    parser.add_argument("--min-swap-free-gb", type=float, default=2.0)
    parser.add_argument("--strict", default="true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_preflight(args)
    print(json.dumps(report, indent=2))
    if parse_bool(args.strict) and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
