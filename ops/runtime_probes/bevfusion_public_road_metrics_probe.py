#!/usr/bin/env python3
"""Normalize BEVFusion public-road KPI metrics for simctl finalization.

The probe is fail-closed by design. If the real BEVFusion evaluator has not
written a complete metrics JSON yet, callers may pass ``--fail-closed-if-missing``
to emit conservative failure values. That keeps the run auditable through the
normal KPI gate without pretending topic presence is perception quality.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_METRICS = (
    "detection_recall",
    "false_positive_per_frame",
    "tracking_id_switches",
    "occupancy_iou",
    "lane_topology_recall",
    "latency_ms",
    "planner_interface_disagreement_rate",
)
DEFAULT_OUTPUT = "runtime_verification/perception_metrics/bevfusion_public_road_metrics.json"

FAIL_CLOSED_METRICS: dict[str, float] = {
    "detection_recall": 0.0,
    "false_positive_per_frame": 999.0,
    "tracking_id_switches": 999.0,
    "occupancy_iou": 0.0,
    "lane_topology_recall": 0.0,
    "latency_ms": 999.0,
    "planner_interface_disagreement_rate": 1.0,
}


def _resolve_path(run_dir: Path, value: str | None, default: str | None = None) -> Path | None:
    raw = value or default
    if raw is None:
        return None
    path = Path(raw)
    return path if path.is_absolute() else run_dir / path


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _coerce_metrics(payload: dict[str, Any]) -> tuple[dict[str, float], list[str], list[str]]:
    raw_metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else payload
    metrics: dict[str, float] = {}
    missing: list[str] = []
    non_numeric: list[str] = []
    for name in REQUIRED_METRICS:
        value = raw_metrics.get(name) if isinstance(raw_metrics, dict) else None
        if isinstance(value, bool) or value is None:
            missing.append(name)
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            non_numeric.append(name)
            continue
        if math.isnan(number) or math.isinf(number):
            non_numeric.append(name)
            continue
        metrics[name] = number
    return metrics, missing, non_numeric


def _latest_probe_summary(run_dir: Path, pattern: str, summary_name: str) -> dict[str, Any] | None:
    runtime_dir = run_dir / "runtime_verification"
    candidates = sorted(runtime_dir.glob(pattern)) if runtime_dir.exists() else []
    for directory in reversed(candidates):
        payload = _read_json(directory / summary_name)
        if payload is not None:
            return payload
    return None


def _observations(run_dir: Path) -> dict[str, Any]:
    return {
        "sensor_topics": _latest_probe_summary(run_dir, "sensor_topics_*", "sensor_topics_summary.json"),
        "perception_readiness": _latest_probe_summary(
            run_dir,
            "perception_readiness_*",
            "perception_readiness_summary.json",
        ),
    }


def build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    run_dir = Path(args.run_dir).resolve()
    source_path = _resolve_path(run_dir, args.source_metrics)
    output_path = _resolve_path(run_dir, args.output, DEFAULT_OUTPUT)
    assert output_path is not None

    source_payload = _read_json(source_path) if source_path is not None else None
    metrics: dict[str, float] = {}
    missing: list[str] = list(REQUIRED_METRICS)
    non_numeric: list[str] = []
    source_status = "missing_source_metrics"

    if source_payload is not None:
        metrics, missing, non_numeric = _coerce_metrics(source_payload)
        source_status = "complete_source_metrics" if not missing and not non_numeric else "incomplete_source_metrics"

    fail_closed = bool(args.fail_closed_if_missing and (missing or non_numeric or source_payload is None))
    if fail_closed:
        metrics = dict(FAIL_CLOSED_METRICS)
        missing = []
        non_numeric = []
        source_status = "fail_closed_missing_bevfusion_quality_source"

    complete = not missing and not non_numeric
    quality_ready = complete and not fail_closed
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": args.profile,
        "metrics_schema": "bevfusion_public_road_metrics_v1",
        "metrics": metrics,
        "source_metrics": str(source_path) if source_path is not None else None,
        "output": str(output_path),
        "complete": complete,
        "quality_ready": quality_ready,
        "source_status": source_status,
        "fail_closed": fail_closed,
        "missing_metrics": missing,
        "non_numeric_metrics": non_numeric,
        "blockers": [] if quality_ready else ["bevfusion_quality_metrics_not_ready"],
        "observations": _observations(run_dir),
        "notes": [
            "fail_closed values are conservative failure sentinels, not BEVFusion quality measurements"
        ]
        if fail_closed
        else [],
    }
    return payload, 0 if complete else 1


def write_payload(payload: dict[str, Any]) -> Path:
    output = Path(str(payload["output"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="simctl run directory")
    parser.add_argument("--profile", default="bevfusion_public_road")
    parser.add_argument("--source-metrics", help="Evaluator-produced metrics JSON to normalize")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Output path, default: <run-dir>/{DEFAULT_OUTPUT}")
    parser.add_argument(
        "--fail-closed-if-missing",
        action="store_true",
        help="Write conservative failure metrics when the evaluator source is missing or incomplete",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload, rc = build_payload(args)
    write_payload(payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
