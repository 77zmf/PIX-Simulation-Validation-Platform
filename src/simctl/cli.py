from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .adapters import AdapterContext, load_reconstruction_adapter
from .assets import asset_snapshot, inspect_asset_bundle, load_asset_bundle
from .config import dump_json, dump_yaml, ensure_dir, find_repo_root, load_yaml, make_run_id, to_wsl_path, utc_now
from .dingtalk import (
    build_markdown_payload,
    load_markdown,
    redact_webhook,
    resolve_secret,
    resolve_webhook,
    send_dingtalk_markdown,
)
from .evaluation import evaluate_metrics, load_kpi_gate, synthetic_metrics
from .health import probe_runtime_health
from .profiles import (
    algorithm_profile_snapshot,
    load_algorithm_profile,
    load_sensor_profile,
    sensor_profile_snapshot,
)
from .project_ops import (
    load_project_automation_config,
    load_project_items,
    load_run_summary,
    render_digest_html,
    render_digest_markdown,
    summarize_items,
    write_digest_outputs,
)
from .reporting import aggregate_run_results, discover_run_results, load_run_result, write_report
from .runtime import build_context, execute_plan, load_stack_profile, persist_plan, render_action
from .runtime_evidence import collect_runtime_evidence, write_runtime_evidence_summary
from .scenarios import load_scenario
from .slots import acquire_slot_lock, get_slot_by_id, list_available_slots, load_slot_catalog, release_slot_lock
from .subagents import list_subagent_specs, load_subagent_spec


def _repo_root(explicit: str | None) -> Path:
    return Path(explicit).resolve() if explicit else find_repo_root()


def _asset_root(repo_root: Path, explicit: str | None) -> Path:
    return Path(explicit).resolve() if explicit else (repo_root / "artifacts" / "assets")


def _print_json(payload: dict[str, Any] | list[Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _resolve_slot(repo_root: Path, stack_id: str, requested_slot: str | None) -> Any:
    slots = load_slot_catalog(stack_id, repo_root)
    if requested_slot:
        return get_slot_by_id(slots, requested_slot)
    return slots[0]


def _load_run_slot(repo_root: Path, run_dir: Path, stack_id: str) -> Any | None:
    result_path = run_dir / "run_result.json"
    if not result_path.exists():
        return None
    result = load_run_result(result_path)
    slot_id = result.get("slot_id")
    if not slot_id:
        return None
    return _resolve_slot(repo_root, stack_id, str(slot_id))


def _slot_payload(slot: Any | None) -> dict[str, Any]:
    if slot is None:
        return {
            "slot_id": None,
            "carla_rpc_port": None,
            "traffic_manager_port": None,
            "ros_domain_id": None,
            "runtime_namespace": None,
            "gpu_id": None,
        }
    return {
        "slot_id": slot.slot_id,
        "carla_rpc_port": slot.carla_rpc_port,
        "traffic_manager_port": slot.traffic_manager_port,
        "ros_domain_id": slot.ros_domain_id,
        "runtime_namespace": slot.runtime_namespace,
        "gpu_id": slot.gpu_id,
    }


def _scenario_stable_runtime_value(scenario: Any, key: str) -> Any:
    execution = scenario.execution if scenario else {}
    stable_runtime = execution.get("stable_runtime", {}) if isinstance(execution, dict) else {}
    if not isinstance(stable_runtime, dict):
        stable_runtime = {}
    return stable_runtime.get(key, execution.get(key))


def _scenario_expected_ros_topics(scenario: Any) -> list[str] | None:
    value = _scenario_stable_runtime_value(scenario, "ros_expected_topics")
    if value is None:
        return None
    if isinstance(value, str):
        topics = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        topics = [str(item).strip() for item in value]
    else:
        topics = [str(value).strip()]
    return [topic for topic in topics if topic]


def _scenario_rmw_implementation(scenario: Any) -> str:
    value = _scenario_stable_runtime_value(scenario, "ros_rmw_implementation")
    return "" if value is None else str(value)


def _scenario_metadata(scenario: Any) -> dict[str, Any]:
    payload = load_yaml(scenario.scenario_path)
    metadata = payload.get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _scenario_validation_command(scenario: Any) -> str | None:
    metadata = _scenario_metadata(scenario)
    command = metadata.get("validation_command")
    if command is None:
        command = _scenario_stable_runtime_value(scenario, "validation_command")
    if command is None:
        return None
    return str(command).strip() or None


def _validation_command_with_run_dir(command: str, run_dir: Path) -> str:
    run_dir_arg = shlex.quote(str(run_dir))
    return command.replace("<run_dir>", run_dir_arg).replace("{run_dir}", run_dir_arg)


def _validation_shell_command(
    *,
    repo_root: Path,
    scenario: Any,
    run_dir: Path,
    command: str,
    run_result: dict[str, Any] | None = None,
) -> str:
    autoware_ws = str(_scenario_stable_runtime_value(scenario, "autoware_ws") or "")
    autoware_bridge_ws = str(_scenario_stable_runtime_value(scenario, "autoware_bridge_ws") or "")
    run_result = run_result or {}
    ros_domain_id = str(_scenario_stable_runtime_value(scenario, "ros_domain_id") or run_result.get("ros_domain_id") or "")
    rmw_implementation = _scenario_rmw_implementation(scenario)
    if not rmw_implementation:
        runtime_health = run_result.get("runtime_health") if isinstance(run_result.get("runtime_health"), dict) else {}
        rmw_implementation = str(runtime_health.get("rmw_implementation") or "")
    carla_root = str(_scenario_stable_runtime_value(scenario, "carla_root") or "$HOME/CARLA_0.9.15")
    resolved_command = _validation_command_with_run_dir(command, run_dir)

    lines = [
        "set -eo pipefail",
        f"cd {shlex.quote(str(repo_root))}",
        "if [ -f /opt/ros/humble/setup.bash ]; then source /opt/ros/humble/setup.bash; fi",
    ]
    if autoware_ws:
        lines.append(
            f"if [ -f {shlex.quote(autoware_ws + '/install/setup.bash')} ]; "
            f"then source {shlex.quote(autoware_ws + '/install/setup.bash')}; fi"
        )
    if autoware_bridge_ws and autoware_bridge_ws != autoware_ws:
        lines.append(
            f"if [ -f {shlex.quote(autoware_bridge_ws + '/install/setup.bash')} ]; "
            f"then source {shlex.quote(autoware_bridge_ws + '/install/setup.bash')}; fi"
        )
    if ros_domain_id:
        lines.append(f"export ROS_DOMAIN_ID={shlex.quote(ros_domain_id)}")
    if run_result.get("carla_rpc_port") is not None:
        lines.append(f"export SIMCTL_CARLA_RPC_PORT={shlex.quote(str(run_result['carla_rpc_port']))}")
    if run_result.get("traffic_manager_port") is not None:
        lines.append(
            f"export SIMCTL_TRAFFIC_MANAGER_PORT={shlex.quote(str(run_result['traffic_manager_port']))}"
        )
    sumo_traci_port = _scenario_stable_runtime_value(scenario, "sumo_traci_port")
    if sumo_traci_port is None and run_result.get("traffic_manager_port") is not None:
        try:
            sumo_traci_port = int(run_result["traffic_manager_port"]) + 1000
        except (TypeError, ValueError):
            sumo_traci_port = None
    if sumo_traci_port is not None:
        lines.append(f"export SIMCTL_SUMO_TRACI_PORT={shlex.quote(str(sumo_traci_port))}")
    if rmw_implementation:
        lines.append(f"export RMW_IMPLEMENTATION={shlex.quote(rmw_implementation)}")
    lines.extend(
        [
            f"CARLA_ROOT={carla_root}",
            'export PYTHONPATH="$CARLA_ROOT/PythonAPI/carla/dist/carla-0.9.15-py3.10-linux-x86_64.egg:$CARLA_ROOT/PythonAPI/carla:${PYTHONPATH:-}"',
            resolved_command,
        ]
    )
    return "\n".join(lines)


def handle_bootstrap(args: argparse.Namespace) -> int:
    repo_root = _repo_root(args.repo_root)
    asset_root = _asset_root(repo_root, args.asset_root)
    profile = load_stack_profile(args.stack, repo_root)
    context = build_context(repo_root, None, None, asset_root, execute=args.execute)
    plan = render_action(profile, "bootstrap", context)
    if args.execute:
        output_dir = ensure_dir(repo_root / "artifacts" / "bootstrap" / args.stack)
        logs = execute_plan(plan, output_dir)
        dump_json(output_dir / "bootstrap_logs.json", logs)
    _print_json(plan)
    return 0


def handle_asset_check(args: argparse.Namespace) -> int:
    repo_root = _repo_root(args.repo_root)
    asset_root = _asset_root(repo_root, args.asset_root)
    bundle = load_asset_bundle(args.bundle, repo_root, asset_root)
    payload = inspect_asset_bundle(bundle)
    payload["asset_root"] = str(asset_root)
    _print_json(payload)
    return 0


def _create_run_context(args: argparse.Namespace) -> tuple[Path, Path, Any, Any, Any, Any, Any, Path, Any]:
    repo_root = _repo_root(args.repo_root)
    asset_root = _asset_root(repo_root, args.asset_root)
    scenario = load_scenario(args.scenario, repo_root)
    bundle = load_asset_bundle(scenario.asset_bundle, repo_root, asset_root)
    gate = load_kpi_gate(scenario.kpi_gate, repo_root)
    sensor_profile = load_sensor_profile(scenario.sensor_profile, repo_root)
    algorithm_profile = load_algorithm_profile(scenario.algorithm_profile, repo_root)
    run_root = Path(args.run_root).resolve() if args.run_root else (repo_root / "runs")
    run_dir = ensure_dir(run_root / make_run_id(scenario.scenario_id))
    slot = _resolve_slot(repo_root, scenario.stack, getattr(args, "slot", None))
    return repo_root, asset_root, scenario, bundle, gate, sensor_profile, algorithm_profile, run_dir, slot


def _artifact_paths(run_dir: Path, recording: dict[str, Any]) -> dict[str, str]:
    artifacts = {
        "run_dir": str(run_dir),
        "scenario_snapshot": str(run_dir / "scenario_snapshot.yaml"),
        "asset_snapshot": str(run_dir / "asset_snapshot.json"),
        "sensor_profile_snapshot": str(run_dir / "sensor_profile_snapshot.json"),
        "algorithm_profile_snapshot": str(run_dir / "algorithm_profile_snapshot.json"),
        "launch_plan": str(run_dir / "start_plan.json"),
        "health_report": str(run_dir / "health.json"),
        "run_result": str(run_dir / "run_result.json"),
        "report_dir": str(run_dir / "report"),
    }
    rosbag_cfg = recording.get("rosbag2", {})
    if rosbag_cfg.get("enabled", False):
        rosbag_rel = rosbag_cfg.get("path", "rosbags/latest")
        artifacts["rosbag2"] = str(run_dir / Path(rosbag_rel))
    carla_cfg = recording.get("carla_recorder", {})
    if carla_cfg.get("enabled", False):
        carla_rel = carla_cfg.get("path", "carla/latest.log")
        artifacts["carla_recorder"] = str(run_dir / Path(carla_rel))
    visual_screenshot = run_dir / "screenshots" / "visual_startup.png"
    visual_screenshot_metadata = run_dir / "screenshots" / "visual_startup.json"
    if visual_screenshot.exists():
        artifacts["visual_screenshot"] = str(visual_screenshot)
    if visual_screenshot_metadata.exists():
        artifacts["visual_screenshot_metadata"] = str(visual_screenshot_metadata)
    return artifacts


def _scenario_snapshot(scenario: Any) -> dict[str, Any]:
    return {
        "scenario_id": scenario.scenario_id,
        "stack": scenario.stack,
        "map_id": scenario.map_id,
        "asset_bundle": scenario.asset_bundle,
        "ego_init": scenario.ego_init,
        "goal": scenario.goal,
        "traffic_profile": scenario.traffic_profile,
        "weather_profile": scenario.weather_profile,
        "sensor_profile": scenario.sensor_profile,
        "algorithm_profile": scenario.algorithm_profile,
        "seed": scenario.seed,
        "recording": scenario.recording,
        "kpi_gate": scenario.kpi_gate,
        "labels": scenario.labels,
        "execution": scenario.execution,
        "scenario_path": str(scenario.scenario_path),
    }


def _algorithm_execution_snapshot(
    *,
    scenario: Any,
    run_dir: Path,
    algorithm_profile: Any,
) -> dict[str, Any] | None:
    if algorithm_profile.profile_type != "reconstruction":
        return None
    adapter = load_reconstruction_adapter(algorithm_profile.profile_id)
    context = AdapterContext(
        run_id=run_dir.name,
        scenario_id=scenario.scenario_id,
        stack=scenario.stack,
        sensor_profile=scenario.sensor_profile,
        algorithm_profile=algorithm_profile.profile_id,
        metadata={
            "run_dir": str(run_dir),
            "map_id": scenario.map_id,
            "asset_bundle": scenario.asset_bundle,
        },
    )
    output = adapter.reconstruct(context)
    return {
        "profile_id": algorithm_profile.profile_id,
        "profile_type": algorithm_profile.profile_type,
        "source": output.source,
        "family": output.family,
        "stage": output.stage,
        "artifacts": output.artifacts,
        "notes": output.notes,
    }


def _launch_gate_eval(
    logs: list[dict[str, Any]],
    runtime_health: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    failed_step = next((entry for entry in logs if entry.get("status") == "failed"), None)
    if failed_step:
        return "launch_failed", {
            "passed": False,
            "violations": [
                {
                    "metric": "execution",
                    "reason": "launch_step_failed",
                    "step": failed_step.get("step"),
                    "returncode": failed_step.get("returncode"),
                    "log_path": failed_step.get("log_path"),
                }
            ],
            "failure_labels": ["launch_failed"],
        }
    if runtime_health is not None and not runtime_health.get("passed", False):
        return "launch_failed", {
            "passed": False,
            "violations": [
                {
                    "metric": "execution",
                    "reason": "runtime_health_check_failed",
                    "failed_checks": runtime_health.get("failed_checks", []),
                    "health_report": runtime_health.get("report_path"),
                }
            ],
            "failure_labels": ["launch_failed", "runtime_health_check_failed"],
        }
    return "launch_submitted", {
        "passed": False,
        "violations": [{"metric": "execution", "reason": "awaiting_runtime_results"}],
        "failure_labels": [],
    }


def _build_run_result(
    *,
    scenario: Any,
    profile: Any,
    gate: Any,
    run_dir: Path,
    artifacts: dict[str, str],
    metrics: dict[str, float],
    gate_eval: dict[str, Any],
    status: str,
    logs: list[dict[str, Any]] | None,
    sensor_profile: Any,
    algorithm_profile: Any,
    algorithm_execution: dict[str, Any] | None,
    runtime_health: dict[str, Any] | None,
    slot: Any | None,
) -> dict[str, Any]:
    slot_fields = _slot_payload(slot)
    return {
        "run_id": run_dir.name,
        "scenario_id": scenario.scenario_id,
        "stack": scenario.stack,
        "status": status,
        "started_at": utc_now(),
        "finished_at": utc_now(),
        "software_versions": profile.software_versions,
        "scenario_path": str(scenario.scenario_path),
        "scenario_params": {
            "map_id": scenario.map_id,
            "asset_bundle": scenario.asset_bundle,
            "ego_init": scenario.ego_init,
            "goal": scenario.goal,
            "traffic_profile": scenario.traffic_profile,
            "weather_profile": scenario.weather_profile,
            "sensor_profile": scenario.sensor_profile,
            "algorithm_profile": scenario.algorithm_profile,
            "seed": scenario.seed,
            "labels": scenario.labels,
        },
        "kpis": metrics,
        "gate": {"gate_id": gate.gate_id, **gate_eval},
        "failure_labels": gate_eval.get("failure_labels", []),
        "resolved_profiles": {
            "sensor": sensor_profile_snapshot(sensor_profile),
            "algorithm": algorithm_profile_snapshot(algorithm_profile),
        },
        "algorithm_execution": algorithm_execution,
        "runtime_health": runtime_health,
        "artifacts": artifacts,
        "replay": {
            "stack": scenario.stack,
            "rosbag2": artifacts.get("rosbag2"),
            "carla_recorder": artifacts.get("carla_recorder"),
        },
        "execution_logs": logs or [],
        "notes": [
            f"execution_mode={scenario.execution.get('mode', 'external')}",
            f"recording_enabled={bool(artifacts.get('rosbag2') or artifacts.get('carla_recorder'))}",
        ],
        **slot_fields,
    }


def _worker_env(repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    src_root = str(repo_root / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_root if not existing else os.pathsep.join([src_root, existing])
    return env


def _build_worker_command(
    *,
    repo_root: Path,
    asset_root: str | None,
    scenario_path: Path,
    run_root: Path,
    slot_id: str,
    execute: bool,
    mock_result: str | None,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "simctl.cli",
        "--repo-root",
        str(repo_root),
    ]
    if asset_root:
        command.extend(["--asset-root", str(Path(asset_root).resolve())])
    command.extend(
        [
            "run",
            "--scenario",
            str(scenario_path),
            "--run-root",
            str(run_root),
            "--slot",
            slot_id,
        ]
    )
    if execute:
        command.append("--execute")
    if mock_result:
        command.extend(["--mock-result", mock_result])
    return command


def _default_slot_id_for_scenario(repo_root: Path, scenario: Any) -> str:
    return load_slot_catalog(scenario.stack, repo_root)[0].slot_id


def _parse_worker_result(stdout: str, stderr: str, scenario_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Unable to parse worker output for {scenario_path}: {exc}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        ) from exc
    artifacts = payload.get("artifacts", {})
    run_result_path = artifacts.get("run_result")
    if not run_result_path:
        raise RuntimeError(f"Worker for {scenario_path} did not return artifacts.run_result")
    return payload


def _parse_json_command_output(stdout: str, stderr: str, command: list[str]) -> dict[str, Any]:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        rendered_command = " ".join(shlex.quote(part) for part in command)
        raise RuntimeError(
            f"Unable to parse JSON output from command: {rendered_command}\n"
            f"{exc}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        ) from exc


def _run_worker(
    *,
    repo_root: Path,
    asset_root: str | None,
    scenario_path: Path,
    run_root: Path,
    slot_id: str,
    execute: bool,
    mock_result: str | None,
    validate: bool = False,
    finalize: bool = False,
    down_on_complete: bool = False,
    require_validation: bool = False,
) -> dict[str, Any]:
    scenario = load_scenario(str(scenario_path), repo_root)
    validation_command = _scenario_validation_command(scenario)
    if require_validation and not validation_command:
        raise RuntimeError(f"Scenario {scenario_path} does not define metadata.validation_command")

    command = _build_worker_command(
        repo_root=repo_root,
        asset_root=asset_root,
        scenario_path=scenario_path,
        run_root=run_root,
        slot_id=slot_id,
        execute=execute,
        mock_result=mock_result,
    )
    completed = subprocess.run(
        command,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=_worker_env(repo_root),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Batch worker failed for {scenario_path} on {slot_id} with return code {completed.returncode}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    payload = _parse_worker_result(completed.stdout.strip(), completed.stderr.strip(), scenario_path)
    record: dict[str, Any] = {
        "scenario": str(scenario_path),
        "slot_id": payload.get("slot_id"),
        "status": payload.get("status"),
        "run_result": str(payload["artifacts"]["run_result"]),
        "run_dir": str(payload["artifacts"].get("run_dir") or Path(payload["artifacts"]["run_result"]).parent),
    }
    run_dir = Path(record["run_dir"])
    validation_error: RuntimeError | None = None
    try:
        if validate and validation_command:
            validation_completed, validation_payload = _run_campaign_command(
                repo_root,
                _campaign_validate_command(repo_root, run_dir, execute=execute, finalize=finalize),
            )
            record["validation_returncode"] = validation_completed.returncode
            record["validation_result"] = validation_payload
            if validation_payload:
                finalize_result = validation_payload.get("finalize_result", {})
                if finalize_result:
                    record["status"] = finalize_result.get("status", record["status"])
                    record["gate"] = finalize_result.get("gate")
                    record["kpis"] = finalize_result.get("kpis")
            if validation_completed.returncode != 0:
                validation_error = RuntimeError(
                    f"Validation failed for {scenario_path} with return code {validation_completed.returncode}\n"
                    f"STDOUT:\n{validation_completed.stdout}\nSTDERR:\n{validation_completed.stderr}"
                )
        elif validate:
            record["validation_result"] = {"status": "skipped", "reason": "missing_validation_command"}
    finally:
        if down_on_complete:
            down_completed, down_payload = _run_campaign_command(
                repo_root,
                _campaign_down_command(repo_root, scenario.stack, run_dir, execute=execute),
            )
            record["down_returncode"] = down_completed.returncode
            record["down_result"] = down_payload or {"stdout": down_completed.stdout.strip()}
            if down_completed.returncode != 0 and validation_error is None:
                validation_error = RuntimeError(
                    f"Down failed for {scenario_path} with return code {down_completed.returncode}\n"
                    f"STDOUT:\n{down_completed.stdout}\nSTDERR:\n{down_completed.stderr}"
                )
    if validation_error is not None:
        raise validation_error
    return record


def _resolve_campaign_path(repo_root: Path, config_ref: str) -> Path:
    candidate = Path(config_ref)
    if candidate.exists():
        return candidate.resolve()
    repo_candidate = repo_root / config_ref
    if repo_candidate.exists():
        return repo_candidate.resolve()
    raise FileNotFoundError(f"Unable to locate campaign config '{config_ref}'")


def _resolve_campaign_run_root(repo_root: Path, config: dict[str, Any], override: str | None) -> Path:
    raw = override or config.get("default_run_root") or "runs/campaign"
    path = Path(str(raw))
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _campaign_slot(config: dict[str, Any], override: str | None) -> str:
    return str(override or config.get("default_slot") or "stable-slot-01")


def _campaign_scenario_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw_entries = config.get("scenarios", [])
    if not isinstance(raw_entries, list) or not raw_entries:
        raise SystemExit("campaign config requires a non-empty scenarios list")
    entries: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(raw_entries, start=1):
        if isinstance(raw_entry, str):
            entries.append({"id": Path(raw_entry).stem, "path": raw_entry})
            continue
        if not isinstance(raw_entry, dict):
            raise SystemExit(f"campaign scenario entry #{index} must be a mapping or string")
        if not raw_entry.get("path"):
            raise SystemExit(f"campaign scenario entry #{index} requires path")
        entries.append(raw_entry)
    return entries


def _campaign_scenario_path(repo_root: Path, entry: dict[str, Any]) -> Path:
    raw_path = Path(str(entry["path"]))
    if raw_path.exists():
        return raw_path.resolve()
    candidate = repo_root / raw_path
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError(f"Unable to locate campaign scenario '{entry['path']}'")


def _campaign_base_command(repo_root: Path) -> list[str]:
    return [sys.executable, "-m", "simctl.cli", "--repo-root", str(repo_root)]


def _campaign_validate_command(repo_root: Path, run_dir: str | Path, *, execute: bool, finalize: bool) -> list[str]:
    command = _campaign_base_command(repo_root) + ["validate", "--run-dir", str(run_dir)]
    if execute:
        command.append("--execute")
    if finalize:
        command.append("--finalize")
    return command


def _campaign_down_command(repo_root: Path, stack: str, run_dir: str | Path, *, execute: bool) -> list[str]:
    command = _campaign_base_command(repo_root) + ["down", "--stack", stack, "--run-dir", str(run_dir)]
    if execute:
        command.append("--execute")
    return command


def _campaign_report_command(repo_root: Path, run_root: Path) -> list[str]:
    return _campaign_base_command(repo_root) + ["report", "--run-root", str(run_root)]


def _run_campaign_command(repo_root: Path, command: list[str]) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None]:
    completed = subprocess.run(
        command,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=_worker_env(repo_root),
    )
    payload = None
    if completed.stdout.strip().startswith(("{", "[")):
        payload = _parse_json_command_output(completed.stdout.strip(), completed.stderr.strip(), command)
    return completed, payload


def _render_campaign_plan(
    *,
    repo_root: Path,
    config_path: Path,
    config: dict[str, Any],
    run_root: Path,
    slot_id: str,
    execute: bool,
    mock_result: str | None,
    stop_after_each: bool,
    pre_down_run_dir: str | None,
    report: bool,
) -> dict[str, Any]:
    entries = _campaign_scenario_entries(config)
    scenario_plans: list[dict[str, Any]] = []
    if pre_down_run_dir:
        scenario_plans.append(
            {
                "step": "pre_down",
                "run_dir": str(Path(pre_down_run_dir).expanduser()),
                "command": _campaign_down_command(repo_root, "stable", pre_down_run_dir, execute=execute),
            }
        )

    for entry in entries:
        scenario_path = _campaign_scenario_path(repo_root, entry)
        scenario = load_scenario(str(scenario_path), repo_root)
        scenario_execute = bool(entry.get("execute", True)) and execute
        validate = bool(entry.get("validation", entry.get("validate", True)))
        finalize = bool(entry.get("finalize", True))
        run_command = _build_worker_command(
            repo_root=repo_root,
            asset_root=None,
            scenario_path=scenario_path,
            run_root=run_root,
            slot_id=slot_id,
            execute=scenario_execute,
            mock_result=str(entry.get("mock_result") or mock_result or "") or None,
        )
        commands: list[dict[str, Any]] = [{"step": "run", "command": run_command}]
        if validate:
            commands.append(
                {
                    "step": "validate",
                    "command": _campaign_validate_command(
                        repo_root,
                        "<run_dir_from_run_result>",
                        execute=execute,
                        finalize=finalize,
                    ),
                }
            )
        if stop_after_each:
            commands.append(
                {
                    "step": "down",
                    "command": _campaign_down_command(
                        repo_root,
                        scenario.stack,
                        "<run_dir_from_run_result>",
                        execute=execute,
                    ),
                }
            )
        scenario_plans.append(
            {
                "id": str(entry.get("id") or scenario.scenario_id),
                "scenario_id": scenario.scenario_id,
                "scenario_path": str(scenario_path),
                "stack": scenario.stack,
                "tags": entry.get("tags", []),
                "validation": validate,
                "finalize": finalize,
                "execute": scenario_execute,
                "commands": commands,
                "expected_observables": entry.get("expected_observables", []),
            }
        )

    payload: dict[str, Any] = {
        "campaign_id": str(config.get("campaign_id") or config_path.stem),
        "config": str(config_path),
        "execute": execute,
        "run_root": str(run_root),
        "slot_id": slot_id,
        "stop_after_each": stop_after_each,
        "report": report,
        "scenarios": scenario_plans,
    }
    if report:
        payload["report_command"] = _campaign_report_command(repo_root, run_root)
    return payload


def handle_campaign(args: argparse.Namespace) -> int:
    repo_root = _repo_root(args.repo_root)
    config_path = _resolve_campaign_path(repo_root, args.config)
    config = load_yaml(config_path)
    run_root = _resolve_campaign_run_root(repo_root, config, args.run_root)
    slot_id = _campaign_slot(config, args.slot)
    stop_after_each = bool(args.stop_after_each or config.get("stop_after_each", False))
    report_enabled = not args.no_report and bool(config.get("report", True))
    plan = _render_campaign_plan(
        repo_root=repo_root,
        config_path=config_path,
        config=config,
        run_root=run_root,
        slot_id=slot_id,
        execute=bool(args.execute),
        mock_result=args.mock_result,
        stop_after_each=stop_after_each,
        pre_down_run_dir=args.pre_down_run_dir,
        report=report_enabled,
    )
    if not args.execute:
        _print_json(plan)
        return 0

    ensure_dir(run_root)
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    if args.pre_down_run_dir:
        command = _campaign_down_command(repo_root, "stable", args.pre_down_run_dir, execute=True)
        completed, payload = _run_campaign_command(repo_root, command)
        pre_down_record = {
            "step": "pre_down",
            "run_dir": str(Path(args.pre_down_run_dir).expanduser()),
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
            "payload": payload,
        }
        records.append(pre_down_record)
        if completed.returncode != 0:
            failures.append({"step": "pre_down", "returncode": completed.returncode})
            if not args.keep_going:
                result = {
                    **plan,
                    "status": "failed",
                    "records": records,
                    "failures": failures,
                }
                result_path = run_root / "campaign_result.json"
                dump_json(result_path, result)
                result["result_path"] = str(result_path)
                _print_json(result)
                return 1

    for entry in _campaign_scenario_entries(config):
        scenario_path = _campaign_scenario_path(repo_root, entry)
        scenario = load_scenario(str(scenario_path), repo_root)
        scenario_id = str(entry.get("id") or scenario.scenario_id)
        scenario_execute = bool(entry.get("execute", True))
        validate = bool(entry.get("validation", entry.get("validate", True)))
        finalize = bool(entry.get("finalize", True))
        mock_result = str(entry.get("mock_result") or args.mock_result or "") or None
        run_command = _build_worker_command(
            repo_root=repo_root,
            asset_root=args.asset_root,
            scenario_path=scenario_path,
            run_root=run_root,
            slot_id=slot_id,
            execute=scenario_execute,
            mock_result=mock_result,
        )
        record: dict[str, Any] = {
            "scenario": scenario_id,
            "scenario_id": scenario.scenario_id,
            "scenario_path": str(scenario_path),
            "commands": [{"step": "run", "command": run_command}],
        }
        completed, run_payload = _run_campaign_command(repo_root, run_command)
        record["run_returncode"] = completed.returncode
        record["run_stdout_tail"] = completed.stdout[-2000:]
        record["run_stderr_tail"] = completed.stderr[-2000:]
        record["run_payload"] = run_payload
        if completed.returncode != 0 or run_payload is None:
            failures.append({"scenario": scenario_id, "step": "run", "returncode": completed.returncode})
            record["status"] = "failed"
            records.append(record)
            if not args.keep_going:
                break
            continue

        artifacts = run_payload.get("artifacts", {}) if isinstance(run_payload.get("artifacts"), dict) else {}
        run_result_path = artifacts.get("run_result")
        run_dir = artifacts.get("run_dir") or (str(Path(run_result_path).parent) if run_result_path else "")
        record["run_dir"] = run_dir
        record["run_result"] = run_result_path
        record["slot_id"] = run_payload.get("slot_id")
        record["run_status"] = run_payload.get("status")

        if completed.returncode == 0 and validate and run_dir:
            validate_command = _campaign_validate_command(repo_root, run_dir, execute=True, finalize=finalize)
            record["commands"].append({"step": "validate", "command": validate_command})
            validation_completed, validation_payload = _run_campaign_command(repo_root, validate_command)
            record["validation_returncode"] = validation_completed.returncode
            record["validation_stdout_tail"] = validation_completed.stdout[-2000:]
            record["validation_stderr_tail"] = validation_completed.stderr[-2000:]
            record["validation_payload"] = validation_payload
            if validation_payload:
                validation = validation_payload.get("validation", {})
                finalize_result = validation_payload.get("finalize_result", {})
                record["validation_status"] = validation.get("status")
                record["final_status"] = finalize_result.get("status")
                record["gate"] = finalize_result.get("gate")
                record["kpis"] = finalize_result.get("kpis")
            if validation_completed.returncode != 0:
                failures.append(
                    {
                        "scenario": scenario_id,
                        "step": "validate",
                        "returncode": validation_completed.returncode,
                    }
                )

        if stop_after_each and run_dir:
            down_command = _campaign_down_command(repo_root, scenario.stack, run_dir, execute=True)
            record["commands"].append({"step": "down", "command": down_command})
            down_completed, down_payload = _run_campaign_command(repo_root, down_command)
            record["down_returncode"] = down_completed.returncode
            record["down_stdout_tail"] = down_completed.stdout[-2000:]
            record["down_stderr_tail"] = down_completed.stderr[-2000:]
            record["down_payload"] = down_payload
            if down_completed.returncode != 0:
                failures.append({"scenario": scenario_id, "step": "down", "returncode": down_completed.returncode})

        final_status = record.get("final_status") or record.get("run_status")
        if final_status != "passed":
            failures.append({"scenario": scenario_id, "step": "result", "status": final_status})
        record["status"] = "failed" if any(item.get("scenario") == scenario_id for item in failures) else str(final_status)
        records.append(record)
        if record["status"] == "failed" and not args.keep_going:
            break

    report_outputs: dict[str, Any] | None = None
    if report_enabled:
        report_command = _campaign_report_command(repo_root, run_root)
        report_completed, report_payload = _run_campaign_command(repo_root, report_command)
        report_outputs = report_payload
        if report_completed.returncode != 0:
            failures.append({"step": "report", "returncode": report_completed.returncode})

    status = "failed" if failures else "passed"
    result: dict[str, Any] = {
        **plan,
        "status": status,
        "records": records,
        "failures": failures,
        "report_outputs": report_outputs,
    }
    result_path = run_root / "campaign_result.json"
    dump_json(result_path, result)
    result["result_path"] = str(result_path)
    _print_json(result)
    return 0 if status == "passed" else 1


def handle_up_or_down(args: argparse.Namespace, action: str) -> int:
    repo_root = _repo_root(args.repo_root)
    asset_root = _asset_root(repo_root, args.asset_root)
    if action == "up" and args.execute:
        if not args.scenario:
            raise SystemExit("up --execute requires --scenario")
        if not args.run_dir:
            raise SystemExit("up --execute requires --run-dir")
    if action == "down" and args.execute and not args.run_dir:
        raise SystemExit("down --execute requires --run-dir")

    scenario = load_scenario(args.scenario, repo_root) if args.scenario else None
    run_dir = Path(args.run_dir).resolve() if args.run_dir else None
    asset_bundle_id = scenario.asset_bundle if scenario else ""
    sensor_profile = load_sensor_profile(scenario.sensor_profile, repo_root) if scenario else None
    algorithm_profile = load_algorithm_profile(scenario.algorithm_profile, repo_root) if scenario else None
    slot = None
    if scenario:
        slot = _resolve_slot(repo_root, scenario.stack, getattr(args, "slot", None))
    elif run_dir:
        slot = _load_run_slot(repo_root, run_dir, args.stack)
    profile = load_stack_profile(args.stack, repo_root)
    output_dir = ensure_dir(run_dir) if run_dir else ensure_dir(repo_root / "artifacts" / "plans" / args.stack)
    context = build_context(
        repo_root,
        output_dir,
        scenario,
        asset_root,
        asset_bundle_id=asset_bundle_id,
        sensor_profile=sensor_profile,
        algorithm_profile=algorithm_profile,
        slot=slot,
        execute=args.execute,
    )
    plan = render_action(profile, "start" if action == "up" else "stop", context)
    plan_path = persist_plan(output_dir, action, plan)
    if args.execute:
        logs = execute_plan(plan, output_dir)
        dump_json(output_dir / f"{action}_logs.json", logs)
        if action == "down" and slot is not None:
            release_slot_lock(repo_root, args.stack, slot.slot_id)
    print(str(plan_path))
    return 0


def handle_run(args: argparse.Namespace) -> int:
    repo_root, asset_root, scenario, bundle, gate, sensor_profile, algorithm_profile, run_dir, slot = _create_run_context(args)
    profile = load_stack_profile(scenario.stack, repo_root)
    context = build_context(
        repo_root,
        run_dir,
        scenario,
        asset_root,
        asset_bundle_id=bundle.bundle_id,
        sensor_profile=sensor_profile,
        algorithm_profile=algorithm_profile,
        slot=slot,
        execute=args.execute,
    )
    plan = render_action(profile, "start", context)
    persist_plan(run_dir, "start", plan)
    dump_yaml(run_dir / "scenario_snapshot.yaml", {"scenario": _scenario_snapshot(scenario)})
    dump_json(run_dir / "asset_snapshot.json", asset_snapshot(bundle))
    dump_json(run_dir / "sensor_profile_snapshot.json", sensor_profile_snapshot(sensor_profile))
    dump_json(run_dir / "algorithm_profile_snapshot.json", algorithm_profile_snapshot(algorithm_profile))
    algorithm_execution = _algorithm_execution_snapshot(
        scenario=scenario,
        run_dir=run_dir,
        algorithm_profile=algorithm_profile,
    )

    logs: list[dict[str, Any]] = []
    runtime_health: dict[str, Any] | None = None
    mode = str(scenario.execution.get("mode", "external"))
    slot_lock_held = False
    try:
        if args.execute and mode != "stub":
            acquire_slot_lock(repo_root, scenario.stack, slot, run_dir=run_dir, scenario_id=scenario.scenario_id)
            slot_lock_held = True
            logs = execute_plan(plan, run_dir)
            metrics: dict[str, float] = {}
            runtime_health = None
            if not any(entry.get("status") == "failed" for entry in logs):
                runtime_health = probe_runtime_health(
                    run_dir=run_dir,
                    slot=slot,
                    logs=logs,
                    runtime_namespace=slot.runtime_namespace,
                    expected_process_steps=["start-carla-server"] if scenario.stack == "novadrive" else None,
                    expected_ros_topics=[] if scenario.stack == "novadrive" else _scenario_expected_ros_topics(scenario),
                    rmw_implementation=_scenario_rmw_implementation(scenario),
                )
            status, gate_eval = _launch_gate_eval(logs, runtime_health)
            if status == "launch_failed":
                release_slot_lock(repo_root, scenario.stack, slot.slot_id)
                slot_lock_held = False
        else:
            outcome = args.mock_result or scenario.execution.get("stub_outcome")
            if mode == "stub" and outcome is None:
                outcome = "passed"
            if outcome:
                metrics = synthetic_metrics(gate, outcome)
                gate_eval = evaluate_metrics(metrics, gate)
                status = "passed" if gate_eval["passed"] else "failed"
            else:
                metrics = {}
                gate_eval = {
                    "passed": False,
                    "violations": [{"metric": "execution", "reason": "planned_only"}],
                    "failure_labels": [],
                }
                status = "planned"
    except Exception:
        if slot_lock_held:
            release_slot_lock(repo_root, scenario.stack, slot.slot_id)
        raise

    artifacts = _artifact_paths(run_dir, scenario.recording)
    result = _build_run_result(
        scenario=scenario,
        profile=profile,
        gate=gate,
        run_dir=run_dir,
        artifacts=artifacts,
        metrics=metrics,
        gate_eval=gate_eval,
        status=status,
        logs=logs,
        sensor_profile=sensor_profile,
        algorithm_profile=algorithm_profile,
        algorithm_execution=algorithm_execution,
        runtime_health=runtime_health,
        slot=slot,
    )
    dump_json(run_dir / "run_result.json", result)
    _print_json(result)
    return 0


def handle_batch(args: argparse.Namespace) -> int:
    repo_root = _repo_root(args.repo_root)
    run_root = Path(args.run_root).resolve() if args.run_root else (repo_root / "runs")
    scenario_paths = [Path(path) for path in args.scenarios]
    if args.glob:
        scenario_paths.extend(sorted(repo_root.glob(args.glob)))
    if args.scenario_dir:
        scenario_paths.extend(sorted(Path(args.scenario_dir).resolve().glob("*.yaml")))
    if not scenario_paths:
        raise SystemExit("batch requires at least one scenario, --glob, or --scenario-dir")

    scenarios = [load_scenario(str(path), repo_root) for path in scenario_paths]
    parallel = max(1, int(args.parallel or 1))
    requires_persistent_slots = args.execute and any(str(scenario.execution.get("mode", "external")) != "stub" for scenario in scenarios)
    stack_ids = {scenario.stack for scenario in scenarios}
    mixed_stack_batch = len(stack_ids) != 1
    if mixed_stack_batch and requires_persistent_slots:
        raise SystemExit(f"batch --execute requires one stack per batch, got {sorted(stack_ids)}")
    if mixed_stack_batch:
        active_slots = [None] * parallel
    else:
        batch_stack = next(iter(stack_ids))
        slot_catalog = load_slot_catalog(batch_stack, repo_root)
        if parallel > len(slot_catalog):
            raise SystemExit(f"batch --parallel {parallel} exceeds configured slot count {len(slot_catalog)}")
        candidate_slots = list_available_slots(repo_root, batch_stack, slot_catalog) if requires_persistent_slots else slot_catalog
        if parallel > len(candidate_slots):
            raise SystemExit(
                f"batch --parallel {parallel} exceeds available {batch_stack} slots {len(candidate_slots)}"
            )
        active_slots = candidate_slots[:parallel]

    if requires_persistent_slots and not args.down_on_complete:
        if len(scenarios) > parallel:
            raise SystemExit(
                "batch --execute with long-running external scenarios currently supports at most --parallel scenarios; "
                "use --down-on-complete to release slots between scenarios"
            )

    batch_records = []
    pending = list(scenarios)

    with ThreadPoolExecutor(max_workers=len(active_slots)) as executor:
        active: dict[Future[dict[str, Any]], Any] = {}

        while pending and len(active) < len(active_slots):
            slot = active_slots[len(active)]
            scenario = pending.pop(0)
            future = executor.submit(
                _run_worker,
                repo_root=repo_root,
                asset_root=args.asset_root,
                scenario_path=scenario.scenario_path,
                run_root=run_root,
                slot_id=slot.slot_id if slot is not None else _default_slot_id_for_scenario(repo_root, scenario),
                execute=args.execute,
                mock_result=args.mock_result,
                validate=args.validate,
                finalize=args.finalize,
                down_on_complete=args.down_on_complete,
                require_validation=args.require_validation,
            )
            active[future] = slot

        while active:
            done, _ = wait(active.keys(), return_when=FIRST_COMPLETED)
            for future in done:
                slot = active.pop(future)
                batch_records.append(future.result())
                if pending:
                    scenario = pending.pop(0)
                    next_future = executor.submit(
                        _run_worker,
                        repo_root=repo_root,
                        asset_root=args.asset_root,
                        scenario_path=scenario.scenario_path,
                        run_root=run_root,
                        slot_id=slot.slot_id if slot is not None else _default_slot_id_for_scenario(repo_root, scenario),
                        execute=args.execute,
                        mock_result=args.mock_result,
                        validate=args.validate,
                        finalize=args.finalize,
                        down_on_complete=args.down_on_complete,
                        require_validation=args.require_validation,
                    )
                    active[next_future] = slot

    batch_index = {
        "generated_at": utc_now(),
        "parallel": parallel,
        "slot_ids": [slot.slot_id for slot in active_slots if slot is not None]
        or sorted({str(record.get("slot_id")) for record in batch_records if record.get("slot_id")}),
        "records": batch_records,
    }
    batch_dir = ensure_dir(run_root / make_run_id("batch"))
    if args.report:
        results = [load_run_result(path) for path in discover_run_results(run_root)]
        batch_index["report_outputs"] = write_report(run_root / "report", aggregate_run_results(results))
    dump_json(batch_dir / "batch_index.json", batch_index)
    print(str(batch_dir / "batch_index.json"))
    return 0


def _to_bash_path(path_value: str | None) -> str:
    if not path_value:
        return ""
    raw = str(path_value)
    if "\\" in raw or (len(raw) >= 2 and raw[1] == ":"):
        return to_wsl_path(raw)
    return raw


def handle_replay(args: argparse.Namespace) -> int:
    run_result_path = Path(args.run_result).resolve()
    result = load_run_result(run_result_path)
    repo_root = _repo_root(args.repo_root)
    asset_root = _asset_root(repo_root, args.asset_root)
    profile = load_stack_profile(result["stack"], repo_root)
    scenario_params = result.get("scenario_params", {})
    resolved_profiles = result.get("resolved_profiles", {})
    sensor_profile_id = str(
        scenario_params.get("sensor_profile")
        or resolved_profiles.get("sensor", {}).get("profile_id")
        or ""
    )
    algorithm_profile_id = str(
        scenario_params.get("algorithm_profile")
        or resolved_profiles.get("algorithm", {}).get("profile_id")
        or ""
    )
    asset_bundle_id = str(scenario_params.get("asset_bundle", ""))
    fake_scenario = type(
        "ReplayScenario",
        (),
        {
            "scenario_path": Path(result["scenario_path"]),
            "scenario_id": result["scenario_id"],
            "sensor_profile": sensor_profile_id,
            "algorithm_profile": algorithm_profile_id,
        },
    )()
    context = build_context(
        repo_root,
        Path(result["artifacts"]["run_dir"]),
        fake_scenario,
        asset_root,
        asset_bundle_id=asset_bundle_id,
        execute=False,
    )
    rosbag_path = result["artifacts"].get("rosbag2")
    carla_recorder_path = result["artifacts"].get("carla_recorder")
    context.update(
        {
            "rosbag_path": _to_bash_path(rosbag_path),
            "rosbag_path_wsl": _to_bash_path(rosbag_path),
            "carla_recorder_path": _to_bash_path(carla_recorder_path),
        }
    )
    plan = render_action(profile, "replay", context)
    _print_json(plan)
    return 0


def handle_report(args: argparse.Namespace) -> int:
    repo_root = _repo_root(args.repo_root)
    run_root = Path(args.run_root).resolve() if args.run_root else (repo_root / "runs")
    if args.batch_index:
        batch = json.loads(Path(args.batch_index).read_text(encoding="utf-8"))
        run_result_paths = [Path(item["run_result"]).resolve() for item in batch["records"]]
    else:
        run_result_paths = discover_run_results(run_root)
    results = [load_run_result(path) for path in run_result_paths]
    summary = aggregate_run_results(results)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (run_root / "report")
    outputs = write_report(output_dir, summary)
    _print_json(outputs)
    return 0


def _finalize_goal_status(runtime_evidence: dict[str, Any]) -> str:
    if runtime_evidence.get("novadrive_attempt_count"):
        return "novadrive_passed" if runtime_evidence.get("successful_novadrive_count") else "novadrive_failed"
    if runtime_evidence.get("attempt_count"):
        return "reached" if runtime_evidence.get("successful_attempt_count") else "not_reached"
    if runtime_evidence.get("dynamic_probe_attempt_count"):
        return (
            "dynamic_probe_passed"
            if runtime_evidence.get("successful_dynamic_probe_count")
            else "dynamic_probe_failed"
        )
    if runtime_evidence.get("sumo_cosim_attempt_count"):
        return "sumo_cosim_passed" if runtime_evidence.get("successful_sumo_cosim_count") else "sumo_cosim_failed"
    if runtime_evidence.get("metric_probe_attempt_count") or runtime_evidence.get("sensor_probe_attempt_count"):
        return "evidence_collected"
    return "no_runtime_evidence"


def _artifact_completeness(
    *,
    artifacts: dict[str, Any],
    missing_artifacts: dict[str, str],
) -> dict[str, Any]:
    required = ["runtime_evidence_summary"]
    optional = [
        "rosbag2",
        "carla_recorder",
        "visual_screenshot",
        "host_bom",
        "preflight_report",
    ]
    present_keys = set(required + optional)
    present = {
        key: str(value)
        for key, value in artifacts.items()
        if key in present_keys and value
    }
    missing = dict(missing_artifacts)
    for key in required:
        if key not in present:
            missing[key] = str(artifacts.get(key) or "")
    return {
        "required": required,
        "optional": optional,
        "present": present,
        "missing": missing,
        "present_count": len(present),
        "missing_count": len(missing),
    }


def _finalize_run(repo_root: Path, run_dir: Path, run_result_path: Path) -> dict[str, Any]:
    if not run_result_path.exists():
        raise SystemExit(f"run_result.json not found: {run_result_path}")

    result = load_run_result(run_result_path)
    gate_id = str(result.get("gate", {}).get("gate_id") or result.get("kpi_gate") or "")
    if not gate_id:
        raise SystemExit("run_result does not contain gate.gate_id")
    gate = load_kpi_gate(gate_id, repo_root)
    runtime_evidence = collect_runtime_evidence(run_dir, result)
    summary_path = write_runtime_evidence_summary(run_dir, runtime_evidence)
    metrics = runtime_evidence.get("metrics", {})
    gate_eval = evaluate_metrics(metrics, gate)
    finalized_at = utc_now()

    result["runtime_evidence"] = runtime_evidence
    result["kpis"] = metrics
    result["gate"] = {"gate_id": gate.gate_id, **gate_eval}
    result["failure_labels"] = gate_eval.get("failure_labels", [])
    result["status"] = "passed" if gate_eval["passed"] else "failed"
    result["finished_at"] = finalized_at
    result["finalized_at"] = finalized_at
    result["finalized_by"] = "simctl finalize"
    artifacts = result.setdefault("artifacts", {})
    artifacts["runtime_evidence_summary"] = str(summary_path)
    result["runtime_evidence_path"] = str(summary_path)

    host_bom_path = run_dir / "host_bom.json"
    preflight_report_path = run_dir / "preflight_report.json"
    if host_bom_path.exists():
        artifacts["host_bom"] = str(host_bom_path)
        result["host_bom_path"] = str(host_bom_path)
    else:
        result["host_bom_path"] = None
    if preflight_report_path.exists():
        artifacts["preflight_report"] = str(preflight_report_path)
        result["preflight_report_path"] = str(preflight_report_path)
    else:
        result["preflight_report_path"] = None

    missing_artifacts: dict[str, str] = {}
    for key in ("rosbag2", "carla_recorder"):
        artifact_path = artifacts.get(key)
        if artifact_path and not Path(str(artifact_path)).exists():
            missing_artifacts[key] = str(artifact_path)
            artifacts.pop(key, None)
    if missing_artifacts:
        result["missing_artifacts"] = missing_artifacts
    result["goal_status"] = _finalize_goal_status(runtime_evidence)
    result["termination_reason"] = "kpi_gate_passed" if gate_eval["passed"] else "kpi_gate_failed"
    result["artifact_completeness"] = _artifact_completeness(
        artifacts=artifacts,
        missing_artifacts=missing_artifacts,
    )
    dump_json(run_result_path, result)
    return result


def handle_finalize(args: argparse.Namespace) -> int:
    repo_root = _repo_root(args.repo_root)
    if args.run_result:
        run_result_path = Path(args.run_result).resolve()
        run_dir = run_result_path.parent
    elif args.run_dir:
        run_dir = Path(args.run_dir).resolve()
        run_result_path = run_dir / "run_result.json"
    else:
        raise SystemExit("finalize requires --run-dir or --run-result")
    result = _finalize_run(repo_root, run_dir, run_result_path)
    _print_json(result)
    return 0


def _run_validation_command(
    *,
    repo_root: Path,
    run_dir: Path,
    scenario: Any,
    command: str,
    run_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation_dir = ensure_dir(run_dir / "validation_logs")
    shell_command = _validation_shell_command(
        repo_root=repo_root,
        scenario=scenario,
        run_dir=run_dir,
        command=command,
        run_result=run_result,
    )
    script_path = validation_dir / "validation_command.sh"
    script_path.write_text(shell_command + "\n", encoding="utf-8")
    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    log_path = validation_dir / "validation_command.log"
    log_path.write_text(
        "\n".join(
            [
                "[command]",
                _validation_command_with_run_dir(command, run_dir),
                "",
                "[stdout]",
                completed.stdout,
                "",
                "[stderr]",
                completed.stderr,
                "",
                f"[returncode] {completed.returncode}",
            ]
        ),
        encoding="utf-8",
    )
    result = {
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "command": _validation_command_with_run_dir(command, run_dir),
        "script": str(script_path),
        "log_path": str(log_path),
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }
    dump_json(validation_dir / "validation_result.json", result)
    return result


def handle_validate(args: argparse.Namespace) -> int:
    repo_root = _repo_root(args.repo_root)
    run_dir = Path(args.run_dir).resolve()
    run_result_path = run_dir / "run_result.json"
    if not run_result_path.exists():
        raise SystemExit(f"run_result.json not found: {run_result_path}")
    run_result = load_run_result(run_result_path)
    scenario_ref = args.scenario or run_result.get("scenario_path")
    if not scenario_ref:
        raise SystemExit("validate requires --scenario when run_result.scenario_path is missing")
    scenario = load_scenario(str(scenario_ref), repo_root)
    command = args.command or _scenario_validation_command(scenario)

    plan = {
        "run_dir": str(run_dir),
        "run_result": str(run_result_path),
        "scenario_id": scenario.scenario_id,
        "scenario_path": str(scenario.scenario_path),
        "validation_available": command is not None,
        "execute": bool(args.execute),
        "finalize": bool(args.finalize),
        "report": bool(args.report),
    }
    if command:
        plan["command"] = _validation_command_with_run_dir(command, run_dir)
        plan["shell_command"] = _validation_shell_command(
            repo_root=repo_root,
            scenario=scenario,
            run_dir=run_dir,
            command=command,
            run_result=run_result,
        )

    if not args.execute:
        _print_json(plan)
        return 0
    if not command:
        raise SystemExit(f"No validation_command found for scenario {scenario.scenario_id}")

    validation_result = _run_validation_command(
        repo_root=repo_root,
        run_dir=run_dir,
        scenario=scenario,
        command=command,
        run_result=run_result,
    )
    payload: dict[str, Any] = {**plan, "validation": validation_result}
    exit_code = int(validation_result["returncode"])

    finalized_result: dict[str, Any] | None = None
    if args.finalize:
        finalized_result = _finalize_run(repo_root, run_dir, run_result_path)
        payload["finalize_result"] = {
            "run_result": str(run_result_path),
            "status": finalized_result.get("status"),
            "gate": finalized_result.get("gate"),
            "kpis": finalized_result.get("kpis"),
            "runtime_evidence_summary": finalized_result.get("artifacts", {}).get("runtime_evidence_summary"),
        }
        if finalized_result.get("status") != "passed":
            exit_code = exit_code or 1

    if args.report:
        run_root = run_dir.parent
        results = [load_run_result(path) for path in discover_run_results(run_root)]
        outputs = write_report(run_root / "report", aggregate_run_results(results))
        payload["report_outputs"] = outputs

    _print_json(payload)
    return exit_code


def handle_digest(args: argparse.Namespace) -> int:
    repo_root = _repo_root(args.repo_root)
    config_path = Path(args.config).resolve() if args.config else (repo_root / "ops" / "project_automation.yaml")
    config = load_project_automation_config(config_path)

    timezone_name = str(config.get("timezone", "Asia/Shanghai"))
    try:
        today = datetime.now(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError:
        today = datetime.now().date()
    due_soon_days = int(config.get("reporting", {}).get("due_soon_days", 3))

    task_cfg = config["projects"]["tasks"]
    scenario_cfg = config["projects"]["scenarios"]
    task_items = load_project_items(
        owner=str(task_cfg.get("owner", "")),
        number=int(task_cfg.get("number", 0) or 0),
        json_override=args.tasks_json,
        provider=str(task_cfg.get("provider", "github_project")),
        source_name="tasks",
    )
    scenario_items = load_project_items(
        owner=str(scenario_cfg.get("owner", "")),
        number=int(scenario_cfg.get("number", 0) or 0),
        json_override=args.scenarios_json,
        provider=str(scenario_cfg.get("provider", "github_project")),
        source_name="scenarios",
    )

    task_summary = summarize_items(task_items, today=today, due_soon_days=due_soon_days)
    scenario_summary = summarize_items(scenario_items, today=today, due_soon_days=due_soon_days)
    run_root = Path(args.run_root).resolve() if args.run_root else (repo_root / "runs")
    run_summary = load_run_summary(run_root)

    markdown_text = render_digest_markdown(
        config=config,
        today=today,
        task_summary=task_summary,
        scenario_summary=scenario_summary,
        run_summary=run_summary,
    )
    html_text = render_digest_html(markdown_text)

    payload = {
        "generated_on": today.isoformat(),
        "timezone": timezone_name,
        "project_provider": "github_project",
        "task_summary": {
            "total": task_summary["total"],
            "active": task_summary["active"],
            "statuses": task_summary["statuses"],
            "tracks": task_summary["tracks"],
            "priorities": task_summary["priorities"],
            "overdue_titles": [item.title for item in task_summary["overdue"]],
            "due_soon_titles": [item.title for item in task_summary["due_soon"]],
            "blocked_titles": [item.title for item in task_summary["blocked"]],
        },
        "scenario_summary": {
            "total": scenario_summary["total"],
            "active": scenario_summary["active"],
            "statuses": scenario_summary["statuses"],
            "tracks": scenario_summary["tracks"],
            "priorities": scenario_summary["priorities"],
            "overdue_titles": [item.title for item in scenario_summary["overdue"]],
            "due_soon_titles": [item.title for item in scenario_summary["due_soon"]],
        },
        "run_summary_available": run_summary is not None,
    }
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (repo_root / "artifacts" / "project_digest")
    outputs = write_digest_outputs(
        output_dir=output_dir,
        markdown_text=markdown_text,
        html_text=html_text,
        payload=payload,
    )
    _print_json(outputs)
    return 0


def handle_ding_notify(args: argparse.Namespace) -> int:
    markdown = load_markdown(args.markdown, args.markdown_file, args.run_result)
    payload = build_markdown_payload(args.title, markdown, args.at_mobile or [])
    if not args.execute:
        _print_json(
            {
                "mode": "dry-run",
                "execute": False,
                "title": args.title,
                "payload": payload,
                "note": "Add --execute to send this message to DingTalk.",
            }
        )
        return 0
    webhook = resolve_webhook(args.webhook, args.webhook_env)
    secret = resolve_secret(args.secret, args.secret_env)
    result = send_dingtalk_markdown(webhook, secret, payload, timeout=args.timeout)
    _print_json(
        {
            "mode": "sent",
            "webhook": redact_webhook(webhook),
            "signed": bool(secret),
            "result": result,
        }
    )
    return 0


def handle_subagent_spec(args: argparse.Namespace) -> int:
    repo_root = _repo_root(args.repo_root)
    if args.list:
        _print_json(
            {
                "specs": [
                    {
                        "spec_id": spec.spec_id,
                        "name": spec.name,
                        "description": spec.description,
                        "agent_type": spec.agent_type,
                        "model": spec.model,
                        "reasoning_effort": spec.reasoning_effort,
                        "spec_path": str(spec.spec_path),
                    }
                    for spec in list_subagent_specs(repo_root)
                ]
            }
        )
        return 0

    if not args.name:
        raise SystemExit("subagent-spec requires --name or --list")

    spec = load_subagent_spec(args.name, repo_root)
    if args.format == "prompt":
        print(spec.render_message(repo_root))
    elif args.format == "spawn_json":
        _print_json(spec.spawn_agent_payload(repo_root))
    else:
        _print_json(spec.as_payload(repo_root))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simctl", description="Simulation control-plane CLI")
    parser.add_argument("--repo-root", help="Override repository root")
    parser.add_argument("--asset-root", help="Override extracted asset root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    asset_check = subparsers.add_parser("asset-check", help="Validate one asset bundle against the local asset root")
    asset_check.add_argument("--bundle", required=True, help="Bundle id or manifest path")
    asset_check.set_defaults(func=handle_asset_check)

    bootstrap = subparsers.add_parser("bootstrap", help="Prepare host, WSL, or remote nodes")
    bootstrap.add_argument("--stack", choices=["stable", "novadrive"], required=True)
    bootstrap.add_argument("--execute", action="store_true")
    bootstrap.set_defaults(func=handle_bootstrap)

    up = subparsers.add_parser("up", help="Render or execute stack startup plan")
    up.add_argument("--stack", choices=["stable", "novadrive"], required=True)
    up.add_argument("--scenario")
    up.add_argument("--run-dir")
    up.add_argument("--slot")
    up.add_argument("--execute", action="store_true")
    up.set_defaults(func=lambda args: handle_up_or_down(args, "up"))

    down = subparsers.add_parser("down", help="Render or execute stack shutdown plan")
    down.add_argument("--stack", choices=["stable", "novadrive"], required=True)
    down.add_argument("--scenario")
    down.add_argument("--run-dir")
    down.add_argument("--slot")
    down.add_argument("--execute", action="store_true")
    down.set_defaults(func=lambda args: handle_up_or_down(args, "down"))

    run = subparsers.add_parser("run", help="Create one run directory and run_result.json")
    run.add_argument("--scenario", required=True)
    run.add_argument("--run-root")
    run.add_argument("--slot")
    run.add_argument("--execute", action="store_true")
    run.add_argument("--mock-result", choices=["passed", "failed"])
    run.set_defaults(func=handle_run)

    batch = subparsers.add_parser("batch", help="Run a scenario list or glob")
    batch.add_argument("scenarios", nargs="*")
    batch.add_argument("--glob")
    batch.add_argument("--scenario-dir")
    batch.add_argument("--run-root")
    batch.add_argument("--parallel", type=int, default=1)
    batch.add_argument("--execute", action="store_true")
    batch.add_argument("--mock-result", choices=["passed", "failed"])
    batch.add_argument("--validate", action="store_true", help="Run each scenario validation_command after run")
    batch.add_argument("--finalize", action="store_true", help="Fold validation evidence into run_result.json")
    batch.add_argument("--report", action="store_true", help="Regenerate the run-root report after the batch")
    batch.add_argument("--down-on-complete", action="store_true", help="Run simctl down after each scenario")
    batch.add_argument(
        "--require-validation",
        action="store_true",
        help="Fail scenarios that do not define metadata.validation_command",
    )
    batch.set_defaults(func=handle_batch)

    campaign = subparsers.add_parser("campaign", help="Run a validation campaign with run/validate/report closure")
    campaign.add_argument("--config", required=True, help="Path to a campaign YAML config")
    campaign.add_argument("--run-root", help="Override campaign run root")
    campaign.add_argument("--slot", help="Override stable slot id")
    campaign.add_argument("--execute", action="store_true", help="Execute run and validation commands")
    campaign.add_argument("--mock-result", choices=["passed", "failed"], help="Pass a mock result to campaign runs")
    campaign.add_argument("--keep-going", action="store_true", help="Continue after failed scenarios")
    campaign.add_argument("--stop-after-each", action="store_true", help="Run simctl down after each scenario")
    campaign.add_argument("--pre-down-run-dir", help="Run simctl down for an existing run directory before the campaign")
    campaign.add_argument("--no-report", action="store_true", help="Skip final report generation")
    campaign.set_defaults(func=handle_campaign)

    replay = subparsers.add_parser("replay", help="Render replay commands for one run_result.json")
    replay.add_argument("--run-result", required=True)
    replay.set_defaults(func=handle_replay)

    report = subparsers.add_parser("report", help="Aggregate run results into Markdown/HTML")
    report.add_argument("--run-root")
    report.add_argument("--batch-index")
    report.add_argument("--output-dir")
    report.set_defaults(func=handle_report)

    finalize = subparsers.add_parser("finalize", help="Fold runtime evidence back into run_result.json and KPI gate")
    finalize.add_argument("--run-dir")
    finalize.add_argument("--run-result")
    finalize.set_defaults(func=handle_finalize)

    validate = subparsers.add_parser("validate", help="Run a scenario validation command for an existing runtime run")
    validate.add_argument("--run-dir", required=True)
    validate.add_argument("--scenario", help="Override scenario path instead of run_result.scenario_path")
    validate.add_argument("--command", help="Override the scenario metadata.validation_command")
    validate.add_argument("--execute", action="store_true")
    validate.add_argument("--finalize", action="store_true", help="Fold validation evidence into run_result.json")
    validate.add_argument("--report", action="store_true", help="Regenerate the parent run-root report")
    validate.set_defaults(func=handle_validate)

    digest = subparsers.add_parser("digest", help="Generate a GitHub Project digest and issue-ready outputs")
    digest.add_argument("--config", help="Path to project automation config YAML")
    digest.add_argument("--output-dir")
    digest.add_argument("--run-root")
    digest.add_argument("--tasks-json", help="Use a local GitHub Project JSON export for task items")
    digest.add_argument("--scenarios-json", help="Use a local GitHub Project JSON export for scenario items")
    digest.set_defaults(func=handle_digest)

    ding_notify = subparsers.add_parser("ding-notify", help="Render or send a DingTalk robot markdown message")
    ding_notify.add_argument("--title", default="PIX 仿真验证结果")
    ding_notify.add_argument("--markdown", help="Markdown text to send")
    ding_notify.add_argument("--markdown-file", help="Path to a markdown file to send")
    ding_notify.add_argument("--run-result", help="Build a validation summary from run_result.json")
    ding_notify.add_argument("--at-mobile", action="append", help="Mobile number to mention; can be repeated")
    ding_notify.add_argument("--webhook", help="DingTalk robot webhook URL. Prefer env vars for secrets.")
    ding_notify.add_argument("--webhook-env", default="DINGTALK_WEBHOOK")
    ding_notify.add_argument("--secret", help="DingTalk robot signing secret. Prefer env vars for secrets.")
    ding_notify.add_argument("--secret-env", default="DINGTALK_SECRET")
    ding_notify.add_argument("--timeout", type=int, default=10)
    ding_notify.add_argument("--execute", action="store_true", help="Actually send the message")
    ding_notify.set_defaults(func=handle_ding_notify)

    subagent_spec = subparsers.add_parser("subagent-spec", help="Render reusable Codex subagent definitions")
    subagent_spec.add_argument("--name", help="Subagent spec id")
    subagent_spec.add_argument("--list", action="store_true", help="List available subagent specs")
    subagent_spec.add_argument("--format", choices=["json", "prompt", "spawn_json"], default="json")
    subagent_spec.set_defaults(func=handle_subagent_spec)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
