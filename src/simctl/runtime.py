from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .config import dump_json, ensure_dir, find_repo_root, interpolate, load_yaml, to_wsl_path
from .models import AlgorithmProfile, CommandStep, RuntimeSlot, ScenarioConfig, SensorProfile, StackProfile


class SafeDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


BACKGROUND_STARTUP_TIMEOUT_SEC = 0.2
_BACKGROUND_PROCESSES: list[subprocess.Popen[str]] = []


def load_stack_profile(stack_id: str, repo_root: Path | None = None) -> StackProfile:
    root = repo_root or find_repo_root()
    profile_path = root / "stack" / "profiles" / f"{stack_id}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Unable to locate stack profile '{stack_id}'")
    payload = interpolate(load_yaml(profile_path), {"REPO_ROOT": str(root)})
    return StackProfile.from_dict(payload, where=str(profile_path))


def build_context(
    repo_root: Path,
    run_dir: Path | None,
    scenario: ScenarioConfig | None,
    asset_root: Path,
    asset_bundle_id: str = "",
    sensor_profile: SensorProfile | None = None,
    algorithm_profile: AlgorithmProfile | None = None,
    slot: RuntimeSlot | None = None,
    execute: bool = False,
) -> dict[str, str]:
    scenario_path = getattr(scenario, "scenario_path", None) if scenario else None
    scenario_id = getattr(scenario, "scenario_id", "") if scenario else ""
    map_id = getattr(scenario, "map_id", "") if scenario else ""
    scenario_sensor_profile = getattr(scenario, "sensor_profile", "") if scenario else ""
    scenario_algorithm_profile = getattr(scenario, "algorithm_profile", "") if scenario else ""
    execution = getattr(scenario, "execution", {}) if scenario else {}
    stable_runtime = execution.get("stable_runtime", {}) if isinstance(execution, dict) else {}
    if not isinstance(stable_runtime, dict):
        stable_runtime = {}

    def runtime_option(key: str, default: str = "") -> str:
        env_key = f"SIMCTL_{key.upper()}"
        if env_key in os.environ:
            return os.environ[env_key]
        value = stable_runtime.get(key, execution.get(key, default) if isinstance(execution, dict) else default)
        if value is None:
            return ""
        return str(value)

    autoware_ws = runtime_option("autoware_ws")
    autoware_bridge_ws = runtime_option("autoware_bridge_ws", autoware_ws)

    context = {
        "repo_root": str(repo_root),
        "repo_root_wsl": to_wsl_path(repo_root),
        "asset_root": str(asset_root),
        "asset_root_wsl": to_wsl_path(asset_root),
        "run_dir": str(run_dir) if run_dir else "",
        "run_dir_wsl": to_wsl_path(run_dir) if run_dir else "",
        "scenario_id": scenario_id,
        "scenario_path": str(scenario_path) if scenario_path else "",
        "scenario_path_wsl": to_wsl_path(scenario_path) if scenario_path else "",
        "map_id": map_id,
        "asset_bundle_id": asset_bundle_id,
        "sensor_profile_id": sensor_profile.profile_id if sensor_profile else scenario_sensor_profile,
        "sensor_truth_mode": (sensor_profile.truth_mode or "") if sensor_profile else "",
        "algorithm_profile_id": algorithm_profile.profile_id if algorithm_profile else scenario_algorithm_profile,
        "algorithm_profile_type": algorithm_profile.profile_type if algorithm_profile else "",
        "slot_id": slot.slot_id if slot else "",
        "carla_rpc_port": str(slot.carla_rpc_port) if slot else "",
        "traffic_manager_port": str(slot.traffic_manager_port) if slot else "",
        "ros_domain_id": str(slot.ros_domain_id) if slot else "",
        "ros_rmw_implementation": runtime_option("ros_rmw_implementation"),
        "runtime_namespace": slot.runtime_namespace if slot else "",
        "gpu_id": slot.gpu_id if slot else "",
        "cpu_affinity": slot.cpu_affinity or "" if slot else "",
        "execute_flag": "-Execute" if execute else "",
        "autoware_ws": autoware_ws,
        "autoware_bridge_ws": autoware_bridge_ws,
        "autoware_bridge_underlay_ws": runtime_option("autoware_bridge_underlay_ws"),
        "autoware_map_path": runtime_option("autoware_map_path"),
        "autoware_vehicle_model": runtime_option("autoware_vehicle_model"),
        "autoware_sensor_model": runtime_option("autoware_sensor_model"),
        "autoware_lidar_type": runtime_option("autoware_lidar_type"),
        "autoware_rviz": runtime_option("autoware_rviz"),
        "carla_map": runtime_option("carla_map", map_id),
        "carla_vehicle_type": runtime_option("carla_vehicle_type", "vehicle.toyota.prius"),
        "carla_spawn_point": runtime_option("carla_spawn_point"),
        "carla_ego_vehicle_role_name": runtime_option("carla_ego_vehicle_role_name", "ego_vehicle"),
        "carla_sensor_kit_name": runtime_option("carla_sensor_kit_name"),
        "carla_sensor_mapping_file": runtime_option("carla_sensor_mapping_file"),
        "carla_sensor_kit_calibration_file": runtime_option("carla_sensor_kit_calibration_file"),
        "carla_objects_definition_file": runtime_option("carla_objects_definition_file"),
        "carla_use_traffic_manager": runtime_option("carla_use_traffic_manager", "False"),
        "carla_render_mode": runtime_option("carla_render_mode"),
        "carla_res_x": runtime_option("carla_res_x"),
        "carla_res_y": runtime_option("carla_res_y"),
        "carla_quality_level": runtime_option("carla_quality_level"),
        "carla_extra_args": runtime_option("carla_extra_args"),
        "carla_display": runtime_option("carla_display"),
        "carla_xauthority": runtime_option("carla_xauthority"),
        "visual_screenshot_wait_sec": runtime_option("visual_screenshot_wait_sec", "8"),
        "carla_localization_bridge_kill_simple_sim": runtime_option(
            "carla_localization_bridge_kill_simple_sim",
            "true",
        ),
        "carla_localization_bridge_wait_sec": runtime_option(
            "carla_localization_bridge_wait_sec",
            "60",
        ),
        "carla_localization_bridge_kill_monitor_sec": runtime_option(
            "carla_localization_bridge_kill_monitor_sec",
            "45",
        ),
    }
    return context


def render_step(step: CommandStep, context: dict[str, str]) -> dict[str, Any]:
    return {
        "name": step.name,
        "runner": step.runner,
        "background": step.background,
        "cwd": step.cwd.format_map(SafeDict(context)) if step.cwd else None,
        "command": step.command.format_map(SafeDict(context)),
        "env": {key: value.format_map(SafeDict(context)) for key, value in step.env.items()},
    }


def render_action(profile: StackProfile, action: str, context: dict[str, str]) -> dict[str, Any]:
    steps = getattr(profile, action)
    return {
        "stack_id": profile.stack_id,
        "description": profile.description,
        "action": action,
        "software_versions": profile.software_versions,
        "steps": [render_step(step, context) for step in steps],
    }


def _step_env(step: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env.update({str(key): str(value) for key, value in step.get("env", {}).items()})
    return env


def _log_header(step: dict[str, Any]) -> str:
    lines = [f"[runner] {step['runner']}", f"[command] {step['command']}"]
    if step.get("cwd"):
        lines.append(f"[cwd] {step['cwd']}")
    return "\n".join(lines) + "\n\n"


def _prune_background_processes() -> None:
    alive: list[subprocess.Popen[str]] = []
    for process in _BACKGROUND_PROCESSES:
        if process.poll() is None:
            alive.append(process)
    _BACKGROUND_PROCESSES[:] = alive


def execute_plan(plan: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    _prune_background_processes()
    logs: list[dict[str, Any]] = []
    command_dir = ensure_dir(run_dir / "command_logs")
    pid_dir = ensure_dir(run_dir / "pids")
    for index, step in enumerate(plan["steps"], start=1):
        log_path = command_dir / f"{index:02d}_{step['name'].replace(' ', '_')}.log"
        command = step["command"]
        step_env = _step_env(step)
        if step["background"]:
            with log_path.open("w", encoding="utf-8") as log_stream:
                log_stream.write(_log_header(step))
                log_stream.flush()
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=step["cwd"] or None,
                    stdout=log_stream,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=step_env,
                    start_new_session=True,
                )
                try:
                    returncode = process.wait(timeout=BACKGROUND_STARTUP_TIMEOUT_SEC)
                except subprocess.TimeoutExpired:
                    _BACKGROUND_PROCESSES.append(process)
                    pid_file = pid_dir / f"{index:02d}_{step['name'].replace(' ', '_')}.pid"
                    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
                    logs.append(
                        {
                            "step": step["name"],
                            "status": "started",
                            "pid": process.pid,
                            "pid_file": str(pid_file),
                            "log_path": str(log_path),
                        }
                    )
                else:
                    logs.append(
                        {
                            "step": step["name"],
                            "status": "completed" if returncode == 0 else "failed",
                            "pid": process.pid,
                            "returncode": returncode,
                            "log_path": str(log_path),
                        }
                    )
                    if returncode != 0:
                        break
            continue

        completed = subprocess.run(
            command,
            shell=True,
            cwd=step["cwd"] or None,
            capture_output=True,
            text=True,
            env=step_env,
        )
        output = _log_header(step) + (completed.stdout or "") + (completed.stderr or "")
        log_path.write_text(output, encoding="utf-8")
        logs.append(
            {
                "step": step["name"],
                "status": "completed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "log_path": str(log_path),
            }
        )
        if completed.returncode != 0:
            break
    return logs


def persist_plan(run_dir: Path, action: str, plan: dict[str, Any]) -> Path:
    plan_path = run_dir / f"{action}_plan.json"
    dump_json(plan_path, plan)
    return plan_path
