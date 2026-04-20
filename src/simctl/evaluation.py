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
        "failure_labels": gate.failure_labels if violations else [],
    }


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
