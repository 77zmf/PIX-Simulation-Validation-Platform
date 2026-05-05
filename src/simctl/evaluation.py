from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .config import find_repo_root, load_yaml
from .models import KpiGate


def load_kpi_gate(gate_ref: str, repo_root: Path | None = None) -> KpiGate:
    root = repo_root or find_repo_root()
    candidate = Path(gate_ref)
    if candidate.exists():
        return KpiGate.from_dict(load_yaml(candidate), candidate.resolve())
    gate_path = root / "evaluation" / "kpi_gates" / f"{gate_ref}.yaml"
    if not gate_path.exists():
        raise FileNotFoundError(f"Unable to locate KPI gate '{gate_ref}'")
    return KpiGate.from_dict(load_yaml(gate_path), gate_path)


def _compare(actual: float, op: str, threshold: float) -> bool:
    if op == "<=":
        return actual <= threshold
    if op == ">=":
        return actual >= threshold
    if op == "<":
        return actual < threshold
    if op == ">":
        return actual > threshold
    if op == "==":
        return actual == threshold
    raise ValueError(f"Unsupported threshold operator '{op}'")


def evaluate_metrics(metrics: dict[str, float], gate: KpiGate) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    for name, rule in gate.metrics.items():
        if name not in metrics:
            violations.append(
                {"metric": name, "reason": "missing", "op": rule.get("op"), "threshold": rule.get("value")}
            )
            continue
        actual = float(metrics[name])
        op = str(rule["op"])
        threshold = float(rule["value"])
        if not _compare(actual, op, threshold):
            violations.append(
                {
                    "metric": name,
                    "reason": "threshold_violation",
                    "actual": actual,
                    "op": op,
                    "threshold": threshold,
                }
            )
    return {
        "passed": not violations,
        "violations": violations,
        "failure_labels": _failure_labels_for_violations(gate.failure_labels, violations),
    }


def _failure_labels_for_violations(
    configured_labels: list[str],
    violations: list[dict[str, Any]],
) -> list[str]:
    if not violations:
        return []
    if not configured_labels:
        return []

    labels: list[str] = []
    for violation in violations:
        for label in _labels_for_metric(str(violation.get("metric") or ""), configured_labels):
            if label not in labels:
                labels.append(label)
    return labels or configured_labels


def _labels_for_metric(metric: str, configured_labels: list[str]) -> list[str]:
    label_keywords = _failure_label_keywords(metric)
    for keyword in label_keywords:
        matches: list[str] = []
        for label in configured_labels:
            if keyword in label and label not in matches:
                matches.append(label)
        if matches:
            return matches
    return []


def _failure_label_keywords(metric: str) -> list[str]:
    if metric == "route_completion":
        return ["route_completion", "route"]
    if metric == "collision_count":
        return ["collision"]
    if metric == "min_ttc_sec":
        return ["yield", "planning_control", "collision", "safety"]
    if metric == "dynamic_actor_response":
        return ["yield", "planning_control", "actor_bridge", "perception"]
    if metric in {"actor_count_observed", "actor_count_spawned", "object_pipeline_nonempty_duration_ratio"}:
        return ["actor_bridge", "perception", "pedestrian_perception"]
    if metric in {"sensor_topic_coverage", "sensor_sample_coverage"}:
        return ["sensor", "robobus_sensor_bridge"]
    if metric in {"kinematic_sanity_passed", "min_ego_z_m", "max_abs_pitch_deg", "max_abs_roll_deg"}:
        return ["kinematic_sanity", "control", "planning_control"]
    if metric in {"max_speed_mps", "max_speed_kph"}:
        return ["speed", "kinematic_sanity", "control", "planning_control"]
    if metric in {"lateral_error_m", "route_goal_lateral_error_m", "longitudinal_error_m", "jerk_mps3"}:
        return ["route_completion", "planning_control", "control"]
    if metric in {"robobus_blueprint_found", "robobus_ego_actor_seen", "robobus_actor_type_match"}:
        return ["blueprint", "robobus_blueprint"]
    if metric.startswith("robobus_bbox") or metric == "robobus_pose_height_plausible":
        return ["bbox", "collision", "robobus_bbox"]
    if metric.startswith("robobus_qiyu_spawn"):
        return ["robobus_qiyu_spawn", "robobus_physics_asset", "carla_vehicle_asset"]
    if metric.startswith("robobus_wheel") or metric in {
        "robobus_front_tread_match",
        "robobus_rear_tread_match",
        "robobus_front_steer_limit_match",
        "robobus_rear_steer_limit_match",
    }:
        return ["wheel", "geometry", "steer"]
    if metric.startswith("robobus_attached_"):
        return ["sensor_attachment", "sensor"]
    return [metric]


def synthetic_metrics(gate: KpiGate, outcome: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for name, rule in gate.metrics.items():
        op = str(rule["op"])
        threshold = float(rule["value"])
        if outcome == "passed":
            if op in {"<=", "<"}:
                metrics[name] = round(threshold * 0.8, 4)
            elif op in {">=", ">"}:
                metrics[name] = round(threshold * 1.1, 4)
            else:
                metrics[name] = threshold
        else:
            if op in {"<=", "<"}:
                metrics[name] = round(threshold * 1.2 + 0.001, 4)
            elif op in {">=", ">"}:
                metrics[name] = round(threshold * 0.7, 4)
            else:
                metrics[name] = threshold + 1.0
    return metrics


def cluster_failures(run_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for result in run_results:
        failure_labels = result.get("failure_labels") or []
        if result.get("status") == "passed" and not failure_labels:
            continue
        labels = tuple(sorted(failure_labels or ["unlabeled"]))
        buckets[labels].append(result["run_id"])
    clusters = []
    for labels, run_ids in sorted(buckets.items(), key=lambda item: (-len(item[1]), item[0])):
        clusters.append({"labels": list(labels), "count": len(run_ids), "run_ids": run_ids})
    return clusters


def summarize_statuses(run_results: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(result["status"] for result in run_results))
