from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


CAMERA_ALIASES = (
    "front_3mm",
    "front_left",
    "front_right",
    "rear_3mm",
    "rear_left",
    "rear_right",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _camera_alias(value: str) -> str:
    for alias in CAMERA_ALIASES:
        if f"/{alias}/" in value or alias in value:
            return alias
    return value.strip("/")


def _median(values: Iterable[Optional[float]]) -> Optional[float]:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return float(statistics.median(numeric))


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return float(statistics.fmean(numeric))


def _min(values: Iterable[Optional[float]]) -> Optional[float]:
    numeric = [float(value) for value in values if value is not None]
    return min(numeric) if numeric else None


def _max(values: Iterable[Optional[float]]) -> Optional[float]:
    numeric = [float(value) for value in values if value is not None]
    return max(numeric) if numeric else None


def _stats(samples: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [sample.get(field) for sample in samples]
    numeric = [float(value) for value in values if value is not None]
    return {
        "count": len(numeric),
        "min": _min(numeric),
        "median": _median(numeric),
        "mean": _mean(numeric),
        "max": _max(numeric),
    }


def _mask_coverage(mask_path: str) -> Optional[float]:
    if not mask_path:
        return None
    path = Path(mask_path)
    if not path.exists():
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(path) as image:
        gray = image.convert("L")
        histogram = gray.histogram()
        total = gray.width * gray.height
    if total <= 0:
        return None
    return float(sum(histogram[1:]) / total)


def load_frame_index(frame_index_csv: Path) -> dict[tuple[str, str], dict[str, str]]:
    index: dict[tuple[str, str], dict[str, str]] = {}
    with frame_index_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            camera = _camera_alias(row.get("topic", ""))
            image_name = Path(row.get("image_path", "")).name
            if camera and image_name:
                index[(camera, image_name)] = row
    return index


def _sample_from_item(item: dict[str, Any], row: Optional[dict[str, str]]) -> dict[str, Any]:
    camera = str(item.get("camera") or _camera_alias(str(item.get("image", ""))))
    image_name = Path(str(item.get("image", ""))).name
    sample = {
        "camera": camera,
        "image": str(item.get("image")),
        "image_name": image_name,
        "psnr": _to_float(item.get("psnr")),
        "valid_pixels": _to_float(item.get("valid_pixels")),
        "has_frame_index": row is not None,
    }
    if row:
        dt = _to_float(row.get("dt_sec"))
        sample.update(
            {
                "dt_abs_sec": abs(dt) if dt is not None else None,
                "laplacian_variance": _to_float(row.get("laplacian_variance")),
                "brightness_mean": _to_float(row.get("brightness_mean")),
                "nearest_dynamic_distance_m": _to_float(row.get("nearest_dynamic_distance_m")),
                "dynamic_mask_candidate_count": _to_float(row.get("dynamic_mask_candidate_count")),
                "mask_coverage_ratio": _mask_coverage(row.get("mask_path", "")),
            }
        )
    return sample


def _warnings(stats_by_field: dict[str, dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    psnr_median = stats_by_field["psnr"]["median"]
    dt_max = stats_by_field["dt_abs_sec"]["max"]
    blur_median = stats_by_field["laplacian_variance"]["median"]
    mask_median = stats_by_field["mask_coverage_ratio"]["median"]
    mask_max = stats_by_field["mask_coverage_ratio"]["max"]
    if psnr_median is not None and psnr_median < 15.0:
        warnings.append("low_psnr")
    if dt_max is not None and dt_max > 0.08:
        warnings.append("sync_offset_review")
    if blur_median is not None and blur_median < 1000.0:
        warnings.append("blur_review")
    if mask_median is not None and mask_median > 0.20:
        warnings.append("heavy_dynamic_mask_review")
    if mask_max is not None and mask_max > 0.50:
        warnings.append("local_heavy_dynamic_mask")
    return warnings


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "psnr",
        "dt_abs_sec",
        "laplacian_variance",
        "brightness_mean",
        "mask_coverage_ratio",
        "dynamic_mask_candidate_count",
        "nearest_dynamic_distance_m",
        "valid_pixels",
    ]
    stats_by_field = {field: _stats(samples, field) for field in fields}
    return {
        "sample_count": len(samples),
        "stats": stats_by_field,
        "warnings": _warnings(stats_by_field),
        "missing_frame_index_count": sum(1 for sample in samples if not sample.get("has_frame_index")),
    }


def _summarize_manifest(manifest_path: Path, frame_index: dict[tuple[str, str], dict[str, str]]) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    final_eval = manifest.get("final_eval", {}) or {}
    samples_by_camera: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in final_eval.get("items", []) or []:
        camera = str(item.get("camera") or _camera_alias(str(item.get("image", ""))))
        image_name = Path(str(item.get("image", ""))).name
        row = frame_index.get((camera, image_name))
        samples_by_camera[camera].append(_sample_from_item(item, row))

    camera_summary = {
        camera: summarize_samples(samples)
        for camera, samples in sorted(samples_by_camera.items())
    }
    worst_camera = None
    if camera_summary:
        worst_camera = min(
            camera_summary,
            key=lambda camera: camera_summary[camera]["stats"]["psnr"]["median"]
            if camera_summary[camera]["stats"]["psnr"]["median"] is not None
            else float("inf"),
        )
    return {
        "segment_id": manifest_path.parent.name,
        "manifest": str(manifest_path),
        "camera_summary": camera_summary,
        "camera_samples": {camera: samples for camera, samples in sorted(samples_by_camera.items())},
        "worst_camera": worst_camera,
    }


def _aggregate_segment_summaries(segments: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for segment in segments:
        for camera, samples in segment.get("camera_samples", {}).items():
            aggregate_samples[camera].extend(samples)
    camera_summary = {
        camera: summarize_samples(samples)
        for camera, samples in sorted(aggregate_samples.items())
    }
    worst_camera = None
    if camera_summary:
        worst_camera = min(
            camera_summary,
            key=lambda camera: camera_summary[camera]["stats"]["psnr"]["median"]
            if camera_summary[camera]["stats"]["psnr"]["median"] is not None
            else float("inf"),
        )
    return {
        "worst_camera": worst_camera,
        "camera_summary": camera_summary,
    }


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Reconstruction Camera Diagnostics",
        "",
        f"- generated: `{report['generated_at_utc']}`",
        f"- frame index: `{report['frame_index_csv']}`",
        f"- segment count: `{len(report['segments'])}`",
        f"- aggregate worst camera: `{report['aggregate']['worst_camera']}`",
        "",
        "## Aggregate",
        "",
        "| camera | psnr median | dt max sec | laplacian median | brightness median | mask median | warnings |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for camera, summary in report["aggregate"]["camera_summary"].items():
        stats = summary["stats"]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{camera}`",
                    _fmt(stats["psnr"]["median"]),
                    _fmt(stats["dt_abs_sec"]["max"]),
                    _fmt(stats["laplacian_variance"]["median"]),
                    _fmt(stats["brightness_mean"]["median"]),
                    _fmt(stats["mask_coverage_ratio"]["median"]),
                    ", ".join(summary["warnings"]) or "-",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Segments", ""])
    for segment in report["segments"]:
        lines.extend(
            [
                f"### `{segment['segment_id']}`",
                "",
                f"- worst camera: `{segment['worst_camera']}`",
                "",
                "| camera | psnr median | dt max sec | laplacian median | brightness median | mask median | warnings |",
                "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for camera, summary in segment["camera_summary"].items():
            stats = summary["stats"]
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{camera}`",
                        _fmt(stats["psnr"]["median"]),
                        _fmt(stats["dt_abs_sec"]["max"]),
                        _fmt(stats["laplacian_variance"]["median"]),
                        _fmt(stats["brightness_mean"]["median"]),
                        _fmt(stats["mask_coverage_ratio"]["median"]),
                        ", ".join(summary["warnings"]) or "-",
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines)


def build_camera_diagnostics(
    frame_index_csv: Path,
    segment_manifests: list[Path],
    output_dir: Path,
) -> dict[str, Any]:
    frame_index = load_frame_index(frame_index_csv)
    segments = [_summarize_manifest(path, frame_index) for path in segment_manifests]
    report = {
        "generated_at_utc": utc_now(),
        "frame_index_csv": str(frame_index_csv),
        "segments": segments,
        "aggregate": _aggregate_segment_summaries(segments),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "reconstruction_camera_diagnostics.json", report)
    (output_dir / "reconstruction_camera_diagnostics.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-index-csv", type=Path, required=True)
    parser.add_argument("--segment-manifest", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build_camera_diagnostics(
        frame_index_csv=args.frame_index_csv,
        segment_manifests=args.segment_manifest,
        output_dir=args.output_dir,
    )
    print(json.dumps({"output_dir": str(args.output_dir), "worst_camera": report["aggregate"]["worst_camera"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
