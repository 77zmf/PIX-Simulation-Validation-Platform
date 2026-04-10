from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .adapters import AdapterContext, load_reconstruction_adapter
from .assets import asset_snapshot, load_asset_bundle
from .config import dump_json, dump_yaml, ensure_dir, find_repo_root, make_run_id, to_wsl_path, utc_now
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


def _run_worker(
    *,
    repo_root: Path,
    asset_root: str | None,
    scenario_path: Path,
    run_root: Path,
    slot_id: str,
    execute: bool,
    mock_result: str | None,
) -> dict[str, Any]:
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
    return {
        "scenario": str(scenario_path),
        "slot_id": payload.get("slot_id"),
        "status": payload.get("status"),
        "run_result": str(payload["artifacts"]["run_result"]),
    }


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
    for scenario in scenarios:
        if scenario.stack != "stable":
            raise SystemExit(f"batch parallel execution only supports stable scenarios, got '{scenario.stack}'")

    parallel = max(1, int(args.parallel or 1))
    slot_catalog = load_slot_catalog("stable", repo_root)
    if parallel > len(slot_catalog):
        raise SystemExit(f"batch --parallel {parallel} exceeds configured slot count {len(slot_catalog)}")
    requires_persistent_slots = args.execute and any(str(scenario.execution.get("mode", "external")) != "stub" for scenario in scenarios)
    candidate_slots = list_available_slots(repo_root, "stable", slot_catalog) if requires_persistent_slots else slot_catalog
    if parallel > len(candidate_slots):
        raise SystemExit(
            f"batch --parallel {parallel} exceeds available stable slots {len(candidate_slots)}"
        )
    active_slots = candidate_slots[:parallel]

    if requires_persistent_slots:
        if len(scenarios) > parallel:
            raise SystemExit(
                "batch --execute with long-running external scenarios currently supports at most --parallel scenarios; "
                "running slots are released by explicit down, not automatic completion"
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
                slot_id=slot.slot_id,
                execute=args.execute,
                mock_result=args.mock_result,
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
                        slot_id=slot.slot_id,
                        execute=args.execute,
                        mock_result=args.mock_result,
                    )
                    active[next_future] = slot

    batch_index = {
        "generated_at": utc_now(),
        "parallel": parallel,
        "slot_ids": [slot.slot_id for slot in active_slots],
        "records": batch_records,
    }
    batch_dir = ensure_dir(run_root / make_run_id("batch"))
    dump_json(batch_dir / "batch_index.json", batch_index)
    print(str(batch_dir / "batch_index.json"))
    return 0


def handle_replay(args: argparse.Namespace) -> int:
    run_result_path = Path(args.run_result).resolve()
    result = load_run_result(run_result_path)
    repo_root = _repo_root(args.repo_root)
    asset_root = _asset_root(repo_root, args.asset_root)
    profile = load_stack_profile(result["stack"], repo_root)
    fake_scenario = type(
        "ReplayScenario",
        (),
        {"scenario_path": Path(result["scenario_path"]), "scenario_id": result["scenario_id"]},
    )()
    context = build_context(repo_root, Path(result["artifacts"]["run_dir"]), fake_scenario, asset_root, execute=False)
    context.update(
        {
            "rosbag_path_wsl": to_wsl_path(result["artifacts"]["rosbag2"]) if result["artifacts"].get("rosbag2") else "",
            "carla_recorder_path": result["artifacts"].get("carla_recorder", ""),
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

    bootstrap = subparsers.add_parser("bootstrap", help="Prepare host, WSL, or remote nodes")
    bootstrap.add_argument("--stack", choices=["stable"], required=True)
    bootstrap.add_argument("--execute", action="store_true")
    bootstrap.set_defaults(func=handle_bootstrap)

    up = subparsers.add_parser("up", help="Render or execute stack startup plan")
    up.add_argument("--stack", choices=["stable"], required=True)
    up.add_argument("--scenario")
    up.add_argument("--run-dir")
    up.add_argument("--slot")
    up.add_argument("--execute", action="store_true")
    up.set_defaults(func=lambda args: handle_up_or_down(args, "up"))

    down = subparsers.add_parser("down", help="Render or execute stack shutdown plan")
    down.add_argument("--stack", choices=["stable"], required=True)
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
    batch.set_defaults(func=handle_batch)

    replay = subparsers.add_parser("replay", help="Render replay commands for one run_result.json")
    replay.add_argument("--run-result", required=True)
    replay.set_defaults(func=handle_replay)

    report = subparsers.add_parser("report", help="Aggregate run results into Markdown/HTML")
    report.add_argument("--run-root")
    report.add_argument("--batch-index")
    report.add_argument("--output-dir")
    report.set_defaults(func=handle_report)

    digest = subparsers.add_parser("digest", help="Generate a GitHub Project digest and issue-ready outputs")
    digest.add_argument("--config", help="Path to project automation config YAML")
    digest.add_argument("--output-dir")
    digest.add_argument("--run-root")
    digest.add_argument("--tasks-json", help="Use a local GitHub Project JSON export for task items")
    digest.add_argument("--scenarios-json", help="Use a local GitHub Project JSON export for scenario items")
    digest.set_defaults(func=handle_digest)

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
