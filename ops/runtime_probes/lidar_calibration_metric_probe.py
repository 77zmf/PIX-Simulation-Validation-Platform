#!/usr/bin/env python3
"""Convert lidar calibration results into simctl metric-probe evidence.

Run this after an external lidar calibration program has written
`calibration_result.json` into the run directory. The probe does not run the
calibration algorithm and does not fabricate calibration quality metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CALIBRATION_RESULT = (
    "runtime_verification/calibration/lidar_sensor_kit_extrinsic/calibration_result.json"
)
REQUIRED_METRICS = (
    "lidar_extrinsic_translation_error_m",
    "lidar_extrinsic_rotation_error_deg",
    "lidar_pairwise_registration_rmse_m",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _resolve_result_file(run_dir: Path, result_file: str | None) -> Path:
    candidate = Path(result_file or DEFAULT_CALIBRATION_RESULT)
    return candidate if candidate.is_absolute() else run_dir / candidate


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "missing_calibration_result"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"unreadable_calibration_result:{exc}"
    if not isinstance(payload, dict):
        return None, "calibration_result_not_object"
    return payload, None


def _numeric_metrics(payload: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    raw_metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    metrics: dict[str, float] = {}
    non_numeric: list[str] = []
    for name, value in raw_metrics.items():
        if isinstance(value, bool):
            non_numeric.append(str(name))
            continue
        try:
            metrics[str(name)] = float(value)
        except (TypeError, ValueError):
            non_numeric.append(str(name))
    return metrics, non_numeric


def _estimated_transform_count(payload: dict[str, Any]) -> int:
    transforms = payload.get("estimated_transforms")
    return len(transforms) if isinstance(transforms, list) else 0


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir).resolve()
    result_path = _resolve_result_file(run_dir, args.calibration_result)
    calibration_result, blocker = _read_json(result_path)

    metrics: dict[str, float] = {}
    non_numeric_metrics: list[str] = []
    missing_metrics = list(REQUIRED_METRICS)
    transform_count = 0
    status = None
    calibration_type = None

    if calibration_result is not None:
        status = calibration_result.get("status")
        calibration_type = calibration_result.get("calibration_type")
        metrics, non_numeric_metrics = _numeric_metrics(calibration_result)
        transform_count = _estimated_transform_count(calibration_result)
        metrics.setdefault("calibrated_lidar_count", float(transform_count))
        metrics["calibration_converged"] = 1.0 if status == "converged" else 0.0
        missing_metrics = [name for name in REQUIRED_METRICS if name not in metrics]
        if missing_metrics:
            blocker = "missing_required_metrics"

    required_transform_count = int(args.require_transform_count)
    if blocker is None and transform_count < required_transform_count:
        blocker = "missing_required_transforms"

    overall_passed = blocker is None and status == "converged"
    if status != "converged" and blocker is None:
        blocker = "calibration_not_converged"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": args.profile,
        "overall_passed": overall_passed,
        "blocked_reason": blocker,
        "calibration_result": str(result_path),
        "calibration_type": calibration_type,
        "status": status,
        "require_transform_count": required_transform_count,
        "estimated_transform_count": transform_count,
        "missing_metrics": missing_metrics,
        "non_numeric_metrics": non_numeric_metrics,
        "missing_topics": [],
        "sample_missing_topics": [],
        "metrics_file": str(result_path),
        "metrics": metrics,
    }


def write_artifacts(run_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    stamp = _utc_stamp()
    output_dir = run_dir / "runtime_verification" / f"metric_probe_lidar_sensor_kit_extrinsic_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"metric_probe_lidar_sensor_kit_extrinsic_{stamp}.json"
    summary = output_dir / "metric_probe_lidar_sensor_kit_extrinsic_summary.json"
    artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary.write_text(
        json.dumps(
            {
                "overall_passed": payload["overall_passed"],
                "blocked_reason": payload["blocked_reason"],
                "missing_metrics": payload["missing_metrics"],
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
    parser.add_argument("--profile", default="lidar_sensor_kit_extrinsic")
    parser.add_argument(
        "--calibration-result",
        help=f"Calibration result JSON path, default: <run-dir>/{DEFAULT_CALIBRATION_RESULT}",
    )
    parser.add_argument("--require-transform-count", type=int, default=5)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir).resolve()
    payload = run_probe(args)
    paths = write_artifacts(run_dir, payload)
    payload.update(paths)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
