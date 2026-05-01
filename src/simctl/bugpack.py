from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import dump_json, ensure_dir, utc_now
from .reporting import discover_run_results, load_run_result


PLANNING_CONTROL_METRICS = {
    "route_completion",
    "route_goal_lateral_error_m",
    "lateral_error_m",
    "longitudinal_error_m",
    "jerk_mps3",
    "collision_count",
    "min_ttc_sec",
    "dynamic_actor_response",
    "yield_response_count",
    "pedestrian_clearance_m",
    "red_light_violations",
    "stop_line_overshoot_m",
    "ego_control_command_seen",
    "planning_validator_invalid_count",
    "trajectory_jump_max_m",
    "trajectory_silence_sec",
    "route_empty_count",
    "control_emergency_true_count",
    "brake_takeover_count",
    "lateral_shift_m",
    "max_lateral_jerk_mps3",
    "planner_container_crash_count",
}

METRIC_OWNERSHIP = {
    "route_completion": ("planning", "control"),
    "route_goal_lateral_error_m": ("planning", "control"),
    "lateral_error_m": ("control", "planning"),
    "longitudinal_error_m": ("control", "planning"),
    "jerk_mps3": ("control", "planning"),
    "collision_count": ("planning", "perception/actor_bridge"),
    "min_ttc_sec": ("planning", "control"),
    "dynamic_actor_response": ("planning", "perception/actor_bridge"),
    "yield_response_count": ("planning", "control"),
    "pedestrian_clearance_m": ("planning", "control"),
    "red_light_violations": ("planning", "control"),
    "stop_line_overshoot_m": ("planning", "control"),
    "ego_control_command_seen": ("control", "autoware_carla_bridge"),
    "planning_validator_invalid_count": ("planning", "planning_validator"),
    "trajectory_jump_max_m": ("planning", "planning_validator"),
    "trajectory_silence_sec": ("planning", "behavior_planning"),
    "route_empty_count": ("planning", "route_handler"),
    "control_emergency_true_count": ("control", "vehicle_cmd_gate"),
    "brake_takeover_count": ("control", "vehicle_interface"),
    "lateral_shift_m": ("planning", "planning_validator"),
    "max_lateral_jerk_mps3": ("planning", "control"),
    "planner_container_crash_count": ("planning", "runtime"),
    "actor_count_observed": ("perception/actor_bridge", "scenario"),
    "sensor_topic_coverage": ("sensor_bridge", "runtime"),
    "sensor_sample_coverage": ("sensor_bridge", "runtime"),
    "sumo_cosim_alive": ("sumo_carla_cosim", "runtime"),
    "sumo_actor_count": ("sumo_carla_cosim", "actor_bridge"),
    "autoware_object_stream_seen": ("perception/actor_bridge", "planning"),
}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()
    return slug or "run"


def _scenario_labels(result: dict[str, Any]) -> set[str]:
    params = result.get("scenario_params") if isinstance(result.get("scenario_params"), dict) else {}
    labels = params.get("labels", [])
    if not isinstance(labels, list):
        labels = []
    return {str(item) for item in labels}


def _algorithm_profile_id(result: dict[str, Any]) -> str:
    profiles = result.get("resolved_profiles") if isinstance(result.get("resolved_profiles"), dict) else {}
    algorithm = profiles.get("algorithm") if isinstance(profiles.get("algorithm"), dict) else {}
    return str(algorithm.get("profile_id") or result.get("algorithm_profile") or "")


def _gate_id(result: dict[str, Any]) -> str:
    gate = result.get("gate") if isinstance(result.get("gate"), dict) else {}
    return str(gate.get("gate_id") or result.get("kpi_gate") or "")


def _is_planning_control_scope(result: dict[str, Any]) -> bool:
    labels = _scenario_labels(result)
    profile_id = _algorithm_profile_id(result)
    gate_id = _gate_id(result)
    return (
        "planning_control" in labels
        or "planning_control" in profile_id
        or "planning_control" in gate_id
    )


def _violations(result: dict[str, Any]) -> list[dict[str, Any]]:
    gate = result.get("gate") if isinstance(result.get("gate"), dict) else {}
    violations = gate.get("violations", [])
    return violations if isinstance(violations, list) else []


def _runtime_health_passed(result: dict[str, Any]) -> bool | None:
    runtime_health = result.get("runtime_health")
    if not isinstance(runtime_health, dict):
        return None
    return bool(runtime_health.get("passed", False))


def _runtime_evidence(result: dict[str, Any]) -> dict[str, Any]:
    inline = result.get("runtime_evidence")
    if isinstance(inline, dict):
        return inline
    artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), dict) else {}
    evidence_path = artifacts.get("runtime_evidence_summary") or result.get("runtime_evidence_path")
    if not evidence_path:
        return {}
    try:
        payload = json.loads(Path(str(evidence_path)).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _has_runtime_service_call_failure(result: dict[str, Any]) -> bool:
    evidence = _runtime_evidence(result)
    ignored = evidence.get("ignored_dynamic_probe_attempts")
    if not isinstance(ignored, list):
        return False
    return any(
        isinstance(item, dict) and item.get("reason") == "service_call_failed"
        for item in ignored
    )


def _severity(violations: list[dict[str, Any]], status: str) -> str:
    metrics = {str(item.get("metric")) for item in violations}
    if status == "launch_failed":
        return "P1"
    if "collision_count" in metrics:
        return "P0"
    if {"min_ttc_sec", "yield_response_count", "dynamic_actor_response"} & metrics:
        return "P1"
    if {"route_completion", "route_goal_lateral_error_m"} & metrics:
        return "P1"
    if {"jerk_mps3", "lateral_error_m", "longitudinal_error_m"} & metrics:
        return "P2"
    return "P2"


def _primary_modules(violations: list[dict[str, Any]]) -> list[str]:
    modules: list[str] = []
    for violation in violations:
        metric = str(violation.get("metric") or "")
        primary = METRIC_OWNERSHIP.get(metric, ("planning_control",))[0]
        if primary not in modules:
            modules.append(primary)
    return modules or ["planning_control"]


def _format_violation(violation: dict[str, Any]) -> str:
    metric = str(violation.get("metric") or "unknown_metric")
    reason = str(violation.get("reason") or "unknown")
    if reason == "missing":
        return f"`{metric}` missing, expected `{violation.get('op')} {violation.get('threshold')}`"
    if reason == "threshold_violation":
        return (
            f"`{metric}` actual `{violation.get('actual')}` "
            f"expected `{violation.get('op')} {violation.get('threshold')}`"
        )
    return f"`{metric}` {reason}"


def _primary_symptom(result: dict[str, Any], violations: list[dict[str, Any]]) -> str:
    if violations:
        return _format_violation(violations[0]).replace("`", "")
    status = str(result.get("status") or "unknown")
    return f"run ended with status {status}"


def classify_run_result(result: dict[str, Any], run_result_path: Path) -> dict[str, Any]:
    status = str(result.get("status") or "unknown")
    violations = _violations(result)
    planning_control_scope = _is_planning_control_scope(result)
    runtime_health_passed = _runtime_health_passed(result)
    gate = result.get("gate") if isinstance(result.get("gate"), dict) else {}
    gate_passed = bool(gate.get("passed", False))

    if status == "passed" and gate_passed:
        classification = "passed"
    elif status in {"planned", "launch_submitted"}:
        classification = "incomplete"
    elif status == "launch_failed" or runtime_health_passed is False:
        classification = "runtime_blocker"
    elif _has_runtime_service_call_failure(result):
        classification = "integration_blocker"
    elif not planning_control_scope:
        classification = "out_of_scope"
    elif not violations:
        classification = "needs_triage"
    elif any(str(item.get("metric")) in PLANNING_CONTROL_METRICS for item in violations):
        classification = "planning_control_bug_candidate"
    else:
        classification = "integration_blocker"

    return {
        "classification": classification,
        "run_id": str(result.get("run_id") or run_result_path.parent.name),
        "scenario_id": str(result.get("scenario_id") or "unknown_scenario"),
        "scenario_path": str(result.get("scenario_path") or ""),
        "run_result": str(run_result_path),
        "status": status,
        "gate_id": _gate_id(result),
        "gate_passed": gate_passed,
        "runtime_health_passed": runtime_health_passed,
        "planning_control_scope": planning_control_scope,
        "violations": violations,
        "severity": _severity(violations, status),
        "suspected_modules": _primary_modules(violations),
        "symptom": _primary_symptom(result, violations),
    }


def _artifact_lines(result: dict[str, Any], run_result_path: Path) -> list[str]:
    artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), dict) else {}
    lines = [f"- run_result: `{run_result_path}`"]
    for key in (
        "runtime_evidence_summary",
        "health_report",
        "visual_screenshot",
        "host_bom",
        "preflight_report",
        "rosbag2",
        "carla_recorder",
        "report_dir",
    ):
        value = artifacts.get(key)
        if value:
            lines.append(f"- {key}: `{value}`")
    validation_log = run_result_path.parent / "validation_logs" / "validation_command.log"
    if validation_log.exists():
        lines.append(f"- validation_log: `{validation_log}`")
    route_summary = run_result_path.parent / "runtime_verification" / "closed_loop_route_sync_summary.json"
    if route_summary.exists():
        lines.append(f"- closed_loop_route_summary: `{route_summary}`")
        payload = _read_json_dict(route_summary)
        camera_video = payload.get("camera_video") if isinstance(payload, dict) else None
        if isinstance(camera_video, dict) and camera_video.get("path"):
            lines.append(f"- camera_video: `{camera_video['path']}`")
    return lines


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest_closed_loop_artifact(run_result_path: Path) -> Path | None:
    runtime_dir = run_result_path.parent / "runtime_verification"
    candidates = [
        path
        for path in runtime_dir.glob("closed_loop_route_sync_*.json")
        if path.name != "closed_loop_route_sync_summary.json"
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def _one_line(value: Any, *, limit: int = 420) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text[:limit]


def _closed_loop_probe_diagnosis_lines(run_result_path: Path) -> list[str]:
    artifact = _latest_closed_loop_artifact(run_result_path)
    if artifact is None:
        return []
    payload = _read_json_dict(artifact)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    verdict = payload.get("verdict") if isinstance(payload.get("verdict"), dict) else {}
    lines = [
        "- closed-loop route probe: "
        f"overall=`{verdict.get('overall_passed')}`, "
        f"movement=`{verdict.get('movement_passed')}`, "
        f"route_service_calls=`{summary.get('route_service_calls_successful')}`, "
        f"all_service_calls=`{summary.get('all_service_calls_successful')}`, "
        f"max_speed_mps=`{summary.get('max_speed_mps')}`, "
        f"total_delta_m=`{summary.get('total_delta_m')}`, "
        f"stopped_before_goal=`{summary.get('stopped_before_goal')}`."
    ]

    tail_stats = summary.get("ros_telemetry", {}).get("tail_stats", {}) if isinstance(summary, dict) else {}
    if isinstance(tail_stats, dict):
        brake = tail_stats.get("tail_actuation_brake_cmd")
        accel = tail_stats.get("tail_control_acceleration_mps2")
        velocity = tail_stats.get("tail_vehicle_velocity_mps")
        if brake or accel or velocity:
            lines.append(
                "- closed-loop tail control/status: "
                f"brake_cmd=`{brake}`, acceleration_mps2=`{accel}`, vehicle_velocity_mps=`{velocity}`."
            )

    for check in payload.get("setup_checks", []):
        if not isinstance(check, dict) or check.get("passed") is not False:
            continue
        lines.append(
            "- closed-loop setup blocker: "
            f"step=`{check.get('step')}`, attempts=`{check.get('attempt_count')}`, "
            f"topic=`{check.get('topic')}`."
        )
        topics = check.get("blocker_snapshot", {}).get("topics", {})
        if not isinstance(topics, dict):
            continue
        for key in (
            "operation_mode_state",
            "operation_mode_availability",
            "fail_safe_mrm_state",
            "vehicle_velocity_status",
            "vehicle_steering_status",
            "imu_raw",
            "diagnostics",
        ):
            item = topics.get(key)
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- blocker snapshot `{key}`: "
                f"sample=`{item.get('sample_received')}`, rc=`{item.get('returncode')}`, "
                f"tail=`{_one_line(item.get('output_tail'))}`."
            )

    for call in payload.get("service_calls", []):
        if not isinstance(call, dict) or not call.get("service_failure_reason"):
            continue
        lines.append(
            "- closed-loop service failure: "
            f"step=`{call.get('step')}`, attempt=`{call.get('attempt')}`, "
            f"reason=`{call.get('service_failure_reason')}`, "
            f"message=`{call.get('service_failure_message')}`."
        )

    stack_log = run_result_path.parent / "command_logs" / "06_start-autoware-stack.log"
    if stack_log.exists():
        text = stack_log.read_text(encoding="utf-8", errors="replace")
        signals = {
            "aeb_waiting_for_imu": text.count("waiting for imu message"),
            "aeb_missing_path": text.count("At least one path (IMU or predicted trajectory) is required for operation"),
            "vehicle_status_timeout": text.count("topic is timeout"),
            "vehicle_status_rate_warn": text.count("topic rate has dropped"),
            "vehicle_cmd_gate_emergency": text.count("Emergency!"),
        }
        if any(signals.values()):
            lines.append(f"- Autoware stack log signals: `{signals}`.")
    return lines


def _runtime_probe_diagnosis_lines(result: dict[str, Any], run_result_path: Path) -> list[str]:
    evidence = _runtime_evidence(result)
    lines: list[str] = []
    lines.extend(_closed_loop_probe_diagnosis_lines(run_result_path))
    if not evidence and not lines:
        return ["- Runtime evidence summary is not available in `run_result.json`."]
    dynamic_attempts = evidence.get("dynamic_probe_attempts")
    if isinstance(dynamic_attempts, list) and dynamic_attempts:
        for attempt in dynamic_attempts:
            if not isinstance(attempt, dict):
                continue
            lines.append(
                "- dynamic probe "
                f"`{attempt.get('kind', 'unknown')}`: "
                f"overall=`{attempt.get('overall_passed')}`, "
                f"safety=`{attempt.get('safety_passed')}`, "
                f"response=`{attempt.get('autoware_dynamic_actor_response_passed')}`, "
                f"moved=`{attempt.get('moved')}`, "
                f"reaction=`{attempt.get('reaction_reason')}`, "
                f"objects=`{attempt.get('actor_count_observed')}/{attempt.get('actor_count_spawned')}`, "
                f"max_speed_mps=`{attempt.get('max_speed_mps')}`, "
                f"min_speed_after_target_in_lane_mps=`{attempt.get('min_speed_after_target_in_lane_mps')}`, "
                f"total_delta_m=`{attempt.get('total_delta_m')}`."
            )
            failure_reasons = attempt.get("failure_reasons")
            if failure_reasons:
                lines.append(f"- dynamic probe failure reasons: `{failure_reasons}`.")
    ignored_route_attempts = evidence.get("ignored_attempts")
    route_service_failures = (
        [
            item
            for item in ignored_route_attempts
            if isinstance(item, dict) and item.get("reason") == "service_call_failed"
        ]
        if isinstance(ignored_route_attempts, list)
        else []
    )
    for item in route_service_failures:
        lines.append(
            "- ignored closed-loop route probe due to service setup failure: "
            f"path=`{item.get('path')}`, invalid_steps=`{item.get('invalid_steps')}`."
        )
        service_calls = item.get("service_calls")
        if isinstance(service_calls, list):
            for call in service_calls:
                if not isinstance(call, dict):
                    continue
                lines.append(
                    "- route service failure detail: "
                    f"step=`{call.get('step')}`, returncode=`{call.get('returncode')}`, "
                    f"output=`{call.get('output_summary')}`."
                )

    ignored_dynamic = evidence.get("ignored_dynamic_probe_attempts")
    dynamic_service_failures = (
        [
            item
            for item in ignored_dynamic
            if isinstance(item, dict) and item.get("reason") == "service_call_failed"
        ]
        if isinstance(ignored_dynamic, list)
        else []
    )
    for item in dynamic_service_failures:
        lines.append(
            "- ignored dynamic probe due to service setup failure: "
            f"path=`{item.get('path')}`, invalid_steps=`{item.get('invalid_steps')}`."
        )
    if not lines:
        lines.append("- No runtime probe diagnosis was collected.")
    return lines


def _reproduction_lines(result: dict[str, Any], run_result_path: Path) -> list[str]:
    scenario_path = str(result.get("scenario_path") or "")
    run_root = str(run_result_path.parent.parent)
    slot_id = str(result.get("slot_id") or "stable-slot-01")
    lines = [
        "```bash",
        f"python3 -m simctl.cli run --scenario {scenario_path} --run-root {run_root} --slot {slot_id} --execute",
        f"python3 -m simctl.cli validate --run-dir {run_result_path.parent} --execute --finalize --report",
        "```",
    ]
    return lines


def render_issue_markdown(
    result: dict[str, Any],
    triage: dict[str, Any],
    *,
    run_result_path: Path,
    owner: str,
) -> str:
    scenario_id = triage["scenario_id"]
    severity = triage["severity"]
    modules = ", ".join(triage["suspected_modules"])
    title = f"[Simulation][PlanningControl][{severity}] {scenario_id}: {triage['symptom']}"
    expected = result.get("scenario_params", {}).get("goal") if isinstance(result.get("scenario_params"), dict) else {}
    software_versions = result.get("software_versions") if isinstance(result.get("software_versions"), dict) else {}
    kpis = result.get("kpis") if isinstance(result.get("kpis"), dict) else {}
    violations = triage["violations"]

    lines = [
        f"# {title}",
        "",
        "## Phenomenon / symptom",
        f"- `{scenario_id}` failed the stable planning/control KPI gate.",
        f"- Primary symptom: {triage['symptom']}.",
        "",
        "## Expected behavior",
        f"- Scenario should satisfy the configured KPI gate `{triage['gate_id']}`.",
        f"- Goal / route expectation: `{expected}`.",
        "",
        "## Actual behavior",
    ]
    if violations:
        lines.extend(f"- {_format_violation(item)}" for item in violations)
    else:
        lines.append(f"- Run status is `{triage['status']}` without a final KPI violation list.")
    if kpis:
        lines.append(f"- Observed KPI snapshot: `{kpis}`.")

    lines.extend(
        [
            "",
            "## Runtime probe diagnosis",
            *_runtime_probe_diagnosis_lines(result, run_result_path),
            "",
            "## Reproduction conditions",
            *_reproduction_lines(result, run_result_path),
            "",
            "## Time / vehicle / map / environment",
            f"- run_id: `{triage['run_id']}`",
            f"- scenario_path: `{triage['scenario_path']}`",
            f"- stack: `{result.get('stack', 'stable')}`",
            f"- map: `{result.get('scenario_params', {}).get('map_id', 'unknown') if isinstance(result.get('scenario_params'), dict) else 'unknown'}`",
            f"- vehicle/sensor profile: `{result.get('resolved_profiles', {}).get('sensor', {}).get('profile_id', 'unknown') if isinstance(result.get('resolved_profiles'), dict) else 'unknown'}`",
            "",
            "## Software version",
        ]
    )
    if software_versions:
        lines.extend(f"- {key}: `{value}`" for key, value in software_versions.items())
    else:
        lines.append("- Software version not recorded in run_result.")

    lines.extend(
        [
            "",
            "## Evidence attached",
            *_artifact_lines(result, run_result_path),
            "",
            "## Suspected module / ownership",
            f"- Primary owner: `{owner}`",
            f"- Suspected module(s): `{modules}`",
            "- This is a test handoff. Do not patch the test harness unless reproduction evidence is wrong.",
            "",
            "## Severity / impact",
            f"- Severity: `{severity}`",
            "- Impact: blocks stable planning/control regression acceptance for this scenario.",
            "",
            "## Recommended next action",
            "- Reproduce with the commands above on the company Ubuntu runtime host.",
            "- Inspect the listed runtime evidence and KPI violations before changing planning/control code.",
            "- After fixing, rerun the same scenario and close this issue only when the KPI gate passes.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_index(output_dir: Path, summary: dict[str, Any]) -> Path:
    lines = [
        "# PIX Planning/Control Bugpack",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- scanned_runs: `{summary['scanned_count']}`",
        f"- issue_count: `{summary['issue_count']}`",
        f"- blocked_count: `{summary['blocked_count']}`",
        f"- passed_count: `{summary['passed_count']}`",
        "",
        "## Issue Drafts",
    ]
    if summary["issues"]:
        for issue in summary["issues"]:
            rel = f"issues/{Path(issue['issue_path']).name}"
            lines.append(f"- [{issue['severity']} {issue['scenario_id']}]({rel}) `{issue['classification']}`")
    else:
        lines.append("- No planning/control bug candidates found.")

    if summary["blocked"]:
        lines.extend(["", "## Blocked / Non-Bug Results"])
        for item in summary["blocked"]:
            lines.append(f"- `{item['scenario_id']}` `{item['classification']}` `{item['status']}`")

    path = output_dir / "index.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_bugpack(
    *,
    run_result_paths: list[Path],
    output_dir: Path,
    owner: str = "planning-control",
    include_passed: bool = False,
    include_infra: bool = False,
) -> dict[str, Any]:
    output_dir = ensure_dir(output_dir)
    issues_dir = ensure_dir(output_dir / "issues")
    for stale_issue in issues_dir.glob("*.md"):
        stale_issue.unlink()
    issues: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    passed: list[dict[str, Any]] = []

    for run_result_path in sorted(run_result_paths):
        result = load_run_result(run_result_path)
        triage = classify_run_result(result, run_result_path)
        classification = triage["classification"]
        if classification == "passed":
            passed.append(triage)
            if not include_passed:
                continue
        if classification == "planning_control_bug_candidate" or (
            include_infra and classification in {"runtime_blocker", "integration_blocker", "needs_triage"}
        ):
            issue_name = f"{triage['severity'].lower()}-{_slug(triage['scenario_id'])}-{_slug(triage['run_id'])}.md"
            issue_path = issues_dir / issue_name
            issue_path.write_text(
                render_issue_markdown(result, triage, run_result_path=run_result_path, owner=owner),
                encoding="utf-8",
            )
            triage = {**triage, "issue_path": str(issue_path)}
            issues.append(triage)
        elif classification != "passed":
            blocked.append(triage)

    summary: dict[str, Any] = {
        "generated_at": utc_now(),
        "output_dir": str(output_dir),
        "owner": owner,
        "scanned_count": len(run_result_paths),
        "issue_count": len(issues),
        "blocked_count": len(blocked),
        "passed_count": len(passed),
        "issues": issues,
        "blocked": blocked,
        "passed": passed,
    }
    index_path = _write_index(output_dir, summary)
    summary["index"] = str(index_path)
    summary["summary"] = str(output_dir / "summary.json")
    dump_json(output_dir / "summary.json", summary)
    return summary


def run_result_paths_from_inputs(run_root: Path | None, run_results: list[str] | None) -> list[Path]:
    paths: list[Path] = []
    if run_root is not None:
        paths.extend(discover_run_results(run_root))
    for item in run_results or []:
        paths.append(Path(item).resolve())
    deduped: dict[str, Path] = {}
    for path in paths:
        deduped[str(path.resolve())] = path.resolve()
    return sorted(deduped.values())
