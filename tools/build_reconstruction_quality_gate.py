from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


SEGMENT_MANIFEST_NAME = "masked_lidar_gsplat_smoke_manifest.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def summarize_image_pack(manifest: dict[str, Any]) -> dict[str, Any]:
    expected = _to_int(manifest.get("expected_image_count"))
    actual = _to_int(manifest.get("image_count"), _to_int(manifest.get("actual_image_count")))
    if actual == 0:
        actual = sum(_to_int(summary.get("image_count")) for summary in manifest.get("camera_topics", {}).values())
    missing = _to_int(manifest.get("missing_image_count"), max(expected - actual, 0))
    missing_ratio = (missing / expected) if expected > 0 else 1.0

    camera_topics = manifest.get("camera_topics", {}) or {}
    complete_camera_count = sum(1 for summary in camera_topics.values() if _to_int(summary.get("missing_count")) == 0)

    masking = manifest.get("masking", {}) or {}
    mask_job_count = _to_int(masking.get("mask_job_count"))
    projected_box_count = _to_int(masking.get("projected_box_count"))
    projection_status = masking.get("camera_projection_status", {}) or {}
    projection_counts = dict(Counter(str(value) for value in projection_status.values()))
    mask_job_ratio = (mask_job_count / actual) if actual > 0 else 0.0

    image_status = "pass"
    image_reasons: list[str] = []
    if expected <= 0 or actual <= 0:
        image_status = "fail"
        image_reasons.append("missing_image_counts")
    if missing_ratio > 0.01:
        image_status = "fail"
        image_reasons.append("too_many_missing_images")
    if len(camera_topics) < 6:
        image_status = "fail"
        image_reasons.append("camera_topic_count_below_6")

    mask_status = "pass"
    mask_reasons: list[str] = []
    if mask_job_count <= 0:
        mask_status = "fail"
        mask_reasons.append("missing_dynamic_masks")
    elif mask_job_ratio < 0.98:
        mask_status = "fail"
        mask_reasons.append("mask_job_count_below_image_count")
    if projected_box_count <= 0:
        mask_status = "fail"
        mask_reasons.append("no_projected_dynamic_boxes")
    if projection_status and any(value != "projected" for value in projection_status.values()):
        mask_status = "review"
        mask_reasons.append("some_cameras_not_projected")

    status = "pass" if image_status == "pass" and mask_status == "pass" else "fail"
    if "review" in {image_status, mask_status}:
        status = "review"

    return {
        "status": status,
        "source_bag": manifest.get("source_bag"),
        "keyframe_count": _to_int(manifest.get("keyframe_count")),
        "expected_image_count": expected,
        "image_count": actual,
        "missing_image_count": missing,
        "missing_image_ratio": missing_ratio,
        "camera_topic_count": len(camera_topics),
        "complete_camera_count": complete_camera_count,
        "masking": {
            "status": mask_status,
            "reasons": mask_reasons,
            "mask_job_count": mask_job_count,
            "mask_job_ratio": mask_job_ratio,
            "projected_box_count": projected_box_count,
            "projection_status_counts": projection_counts,
        },
        "image_reasons": image_reasons,
    }


def parse_pose_prior_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise ValueError(f"pose prior must use name=path: {spec}")
    name, raw_path = spec.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"pose prior name is empty: {spec}")
    return name, Path(raw_path).expanduser()


def _stats_metrics(stats: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {
        f"{prefix}_rmse_m": _to_float(stats.get("rmse")),
        f"{prefix}_p50_m": _to_float(stats.get("p50")),
        f"{prefix}_p95_m": _to_float(stats.get("p95")),
        f"{prefix}_max_m": _to_float(stats.get("max")),
    }


def extract_pose_metrics(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if "xy_similarity" in data:
        xy = data.get("xy_similarity", {}) or {}
        z = data.get("z_affine", {}) or {}
        route = data.get("route", {}) or {}
        return (
            "gnss_constrained_reconstruction_pose_prior",
            {
                "xy_p95_m": _to_float(xy.get("residual_p95_m")),
                "xy_median_m": _to_float(xy.get("residual_median_m")),
                "xy_max_m": _to_float(xy.get("residual_max_m")),
                "z_rmse_m": _to_float(z.get("residual_rmse_m")),
                "route_length_m": _to_float(route.get("constrained_route_length_m")),
                "keyframe_count": _to_int(route.get("keyframe_count")),
            },
        )
    if "backend_constraint" in data:
        backend = data.get("backend_constraint", {}) or {}
        metrics = {}
        metrics.update(_stats_metrics(backend.get("xy_error_m", {}) or {}, "xy"))
        metrics.update(_stats_metrics(backend.get("z_abs_error_m", {}) or {}, "z"))
        metrics["route_length_m"] = _to_float(backend.get("path_length_xy_m"))
        metrics["sample_count"] = _to_int((backend.get("xy_error_m", {}) or {}).get("count"))
        return "fast_lio2_gnss_backend", metrics
    if "direct_xy_error_m" in data:
        metrics = {}
        metrics.update(_stats_metrics(data.get("direct_xy_error_m", {}) or {}, "xy"))
        metrics.update(_stats_metrics(data.get("direct_z_abs_error_m", {}) or {}, "z"))
        metrics["route_length_m"] = _to_float(data.get("slam_path_length_xy_m"))
        metrics["sample_count"] = _to_int(data.get("paired_count"))
        return "lio_rf_gps_factor", metrics
    return str(data.get("mode") or "unknown_pose_prior"), {}


def pose_quality_status(metrics: dict[str, Any]) -> str:
    xy_p95 = _to_float(metrics.get("xy_p95_m"))
    z_rmse = _to_float(metrics.get("z_rmse_m"))
    if xy_p95 is None and z_rmse is None:
        return "review"
    if xy_p95 is not None and xy_p95 > 2.5:
        return "fail"
    if z_rmse is not None and z_rmse > 0.5:
        return "fail"
    if (xy_p95 is not None and xy_p95 > 0.75) or (z_rmse is not None and z_rmse > 0.25):
        return "review"
    return "pass"


def summarize_pose_prior(name: str, path: Path, source_bag: Optional[str]) -> dict[str, Any]:
    data = read_json(path)
    prior_source = data.get("source_bag") or (data.get("inputs", {}) or {}).get("source_bag")
    schema, metrics = extract_pose_metrics(data)
    same_source = bool(source_bag and prior_source and str(prior_source) == str(source_bag))
    reason = None
    if not prior_source:
        reason = "missing_source_bag"
    elif not source_bag:
        reason = "missing_image_source_bag"
    elif not same_source:
        reason = "source_bag_mismatch"

    return {
        "name": name,
        "path": str(path),
        "schema": schema,
        "source_bag": prior_source,
        "same_source": same_source,
        "accepted": same_source,
        "reason": reason,
        "quality_status": pose_quality_status(metrics),
        "metrics": metrics,
    }


def score_segment(manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    final_metric = manifest.get("final_metric", {}) or {}
    final_eval = manifest.get("final_eval", {}) or {}
    point_stats = manifest.get("point_stats", {}) or {}
    psnr = _to_float(final_eval.get("psnr_median"), _to_float(final_metric.get("psnr"), 0.0)) or 0.0
    psnr_source = "final_eval.psnr_median" if "psnr_median" in final_eval else "final_metric.psnr"
    camera_psnr_median = {
        str(camera): float(value)
        for camera, value in (final_eval.get("by_camera_psnr_median", {}) or {}).items()
        if _to_float(value) is not None
    }
    worst_camera = min(camera_psnr_median, key=camera_psnr_median.get) if camera_psnr_median else None
    weak_cameras = sorted(camera for camera, value in camera_psnr_median.items() if value < 15.0)
    loss = _to_float(final_metric.get("loss"))
    valid_pixels = _to_int(final_metric.get("valid_pixels"))
    frame_count = _to_int(manifest.get("frame_count"))
    iterations = _to_int(manifest.get("iterations"))
    colorized_ratio = _to_float(point_stats.get("image_colorized_ratio"), 0.0) or 0.0

    status = "pass"
    reasons: list[str] = []
    if psnr < 15.0:
        status = "fail"
        reasons.append("psnr_below_15")
    elif psnr < 18.0:
        status = "review"
        reasons.append("psnr_below_18")
    if frame_count < 18:
        status = "fail"
        reasons.append("frame_count_below_18")
    elif frame_count < 24 and status == "pass":
        status = "review"
        reasons.append("frame_count_below_24")
    if colorized_ratio < 0.90:
        status = "fail"
        reasons.append("colorized_ratio_below_0_90")
    elif colorized_ratio < 0.95 and status == "pass":
        status = "review"
        reasons.append("colorized_ratio_below_0_95")

    return {
        "segment_id": manifest_path.parent.name,
        "manifest": str(manifest_path),
        "status": status,
        "reasons": reasons,
        "psnr": psnr,
        "psnr_source": psnr_source,
        "camera_psnr_median": camera_psnr_median,
        "worst_camera": worst_camera,
        "weak_cameras": weak_cameras,
        "loss": loss,
        "valid_pixels": valid_pixels,
        "frame_count": frame_count,
        "iterations": iterations,
        "image_colorized_ratio": colorized_ratio,
        "dynamic_mask_policy": manifest.get("dynamic_mask_policy"),
    }


def summarize_camera_diagnostics(items: list[dict[str, Any]]) -> dict[str, Any]:
    values_by_camera: dict[str, list[tuple[str, float]]] = {}
    for item in items:
        for camera, value in item.get("camera_psnr_median", {}).items():
            values_by_camera.setdefault(camera, []).append((str(item["segment_id"]), float(value)))
    diagnostics: dict[str, Any] = {}
    for camera, values in sorted(values_by_camera.items()):
        psnrs = [value for _, value in values]
        diagnostics[camera] = {
            "count": len(psnrs),
            "psnr_min": min(psnrs),
            "psnr_median": statistics.median(psnrs),
            "psnr_mean": statistics.fmean(psnrs),
            "psnr_max": max(psnrs),
            "weak_count": sum(1 for value in psnrs if value < 15.0),
            "worst_segments": [
                {"segment_id": segment_id, "psnr": value}
                for segment_id, value in sorted(values, key=lambda pair: pair[1])[:5]
            ],
        }
    worst_camera = None
    if diagnostics:
        worst_camera = min(diagnostics, key=lambda camera: diagnostics[camera]["psnr_median"])
    return {"worst_camera": worst_camera, "items": diagnostics}


def summarize_segments(segment_results_dir: Optional[Path]) -> dict[str, Any]:
    if segment_results_dir is None:
        return {
            "status": "not_provided",
            "segment_count": 0,
            "status_counts": {},
            "items": [],
            "worst_segments": [],
            "psnr": {},
            "camera_diagnostics": {"worst_camera": None, "items": {}},
        }
    manifests = sorted(segment_results_dir.rglob(SEGMENT_MANIFEST_NAME))
    items = [score_segment(path, read_json(path)) for path in manifests]
    counts = dict(Counter(item["status"] for item in items))
    psnrs = [item["psnr"] for item in items]
    status = "pass"
    if counts.get("fail", 0) > 0:
        status = "fail"
    elif counts.get("review", 0) > 0:
        status = "review"
    if not items:
        status = "not_found"

    return {
        "status": status,
        "segment_results_dir": str(segment_results_dir),
        "segment_count": len(items),
        "status_counts": counts,
        "items": items,
        "worst_segments": sorted(items, key=lambda item: item["psnr"])[:5],
        "camera_diagnostics": summarize_camera_diagnostics(items),
        "psnr": {
            "min": min(psnrs) if psnrs else None,
            "median": statistics.median(psnrs) if psnrs else None,
            "max": max(psnrs) if psnrs else None,
        },
    }


def decide_status(image_pack: dict[str, Any], pose_priors: dict[str, Any], segments: dict[str, Any]) -> tuple[str, list[str]]:
    actions: list[str] = []
    accepted = pose_priors["accepted"]
    excluded = pose_priors["excluded"]

    if segments.get("status") in {"fail", "review"}:
        actions.append("Review or retrain failed/review 3DGS segments before CARLA visual handoff.")
    if image_pack["status"] != "pass":
        actions.append("Fix image extraction or dynamic masks before any static/background Gaussian retraining.")
    if not accepted:
        actions.append("Generate a same-source pose prior for this image pack before training 3DGS.")
    if any(prior["quality_status"] != "pass" for prior in accepted):
        actions.append("Review same-source pose-prior residuals before using it as a camera pose prior.")
    if excluded:
        actions.append("Do not use excluded cross-source pose priors for this image pack; rerun FAST-LIO2/LIO-RF on the same source bag if comparison is needed.")
    if segments.get("status") == "not_provided":
        actions.append("Run segmented 3DGS smoke training, then rerun this quality gate with --segment-results-dir.")

    if image_pack["status"] == "fail" or not accepted:
        return "blocked", actions
    if any(prior["quality_status"] == "fail" for prior in accepted):
        return "blocked", actions
    if segments.get("status") in {"fail", "review"}:
        return "needs_optimization", actions
    if image_pack["status"] == "review" or any(prior["quality_status"] == "review" for prior in accepted):
        return "needs_review", actions
    if segments.get("status") in {"not_found", "not_provided"}:
        return "ready_for_segment_smoke", actions
    return "ready_for_retrain", actions


def render_markdown(report: dict[str, Any]) -> str:
    accepted = report["pose_priors"]["accepted"]
    excluded = report["pose_priors"]["excluded"]
    worst = report["segments"]["worst_segments"]
    lines = [
        "# Reconstruction Quality Gate",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- status: `{report['status']}`",
        f"- target_lane: `{report['target_lane']}`",
        f"- source_bag: `{report['image_pack'].get('source_bag')}`",
        "",
        "## Image Pack",
        "",
        f"- status: `{report['image_pack']['status']}`",
        f"- keyframes: `{report['image_pack']['keyframe_count']}`",
        f"- images: `{report['image_pack']['image_count']}/{report['image_pack']['expected_image_count']}`",
        f"- missing_ratio: `{report['image_pack']['missing_image_ratio']:.6f}`",
        f"- mask_status: `{report['image_pack']['masking']['status']}`",
        f"- projected_boxes: `{report['image_pack']['masking']['projected_box_count']}`",
        "",
        "## Pose Priors",
        "",
    ]
    if accepted:
        lines.append("Accepted same-source priors:")
        for prior in accepted:
            lines.append(f"- `{prior['name']}` schema=`{prior['schema']}` quality=`{prior['quality_status']}`")
    else:
        lines.append("Accepted same-source priors: none")
    if excluded:
        lines.append("")
        lines.append("Excluded priors:")
        for prior in excluded:
            lines.append(f"- `{prior['name']}` reason=`{prior['reason']}` source=`{prior.get('source_bag')}`")
    lines.extend(
        [
            "",
            "## Segments",
            "",
            f"- status: `{report['segments']['status']}`",
            f"- count: `{report['segments']['segment_count']}`",
            f"- status_counts: `{report['segments']['status_counts']}`",
            f"- psnr: `{report['segments']['psnr']}`",
            f"- worst_camera: `{report['segments']['camera_diagnostics']['worst_camera']}`",
            "",
            "Worst segments:",
        ]
    )
    for item in worst:
        lines.append(
            f"- `{item['segment_id']}` status=`{item['status']}` psnr=`{item['psnr']:.3f}` "
            f"worst_camera=`{item.get('worst_camera')}` reasons=`{item['reasons']}`"
        )
    camera_items = report["segments"]["camera_diagnostics"]["items"]
    if camera_items:
        lines.extend(["", "Camera diagnostics:"])
        for camera, summary in camera_items.items():
            lines.append(
                f"- `{camera}` median=`{summary['psnr_median']:.3f}` "
                f"weak_count=`{summary['weak_count']}` min=`{summary['psnr_min']:.3f}`"
            )
    lines.extend(["", "## Next Actions", ""])
    for action in report["next_actions"]:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## CARLA Boundary",
            "",
            "CARLA 0.9.15 import remains `mesh + OpenDRIVE + collision proxy`; Gaussian output is a visual/research layer until a NuRec-capable runtime is installed and smoke-tested.",
            "",
        ]
    )
    return "\n".join(lines)


def build_quality_gate(
    *,
    image_pack_manifest: Path,
    pose_prior_specs: list[str],
    segment_results_dir: Optional[Path],
    output_dir: Path,
    target_lane: str = "hybrid_mesh_opendrive_plus_static_3dgs_visual_layer",
) -> dict[str, Any]:
    image_pack = summarize_image_pack(read_json(image_pack_manifest))
    source_bag = image_pack.get("source_bag")

    prior_items = []
    for spec in pose_prior_specs:
        name, path = parse_pose_prior_spec(spec)
        prior_items.append(summarize_pose_prior(name, path, source_bag))
    pose_priors = {
        "accepted": [item for item in prior_items if item["accepted"]],
        "excluded": [item for item in prior_items if not item["accepted"]],
    }
    segments = summarize_segments(segment_results_dir)
    status, next_actions = decide_status(image_pack, pose_priors, segments)

    report = {
        "generated_at": utc_now(),
        "status": status,
        "target_lane": target_lane,
        "image_pack_manifest": str(image_pack_manifest),
        "image_pack": image_pack,
        "pose_priors": pose_priors,
        "segments": segments,
        "next_actions": next_actions,
        "carla_import_boundary": (
            "CARLA 0.9.15 import remains mesh + OpenDRIVE + collision proxy; "
            "Gaussian output is a visual/research layer until NuRec runtime is available."
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "reconstruction_quality_gate.json", report)
    (output_dir / "reconstruction_quality_gate.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a 3DGS reconstruction quality gate report.")
    parser.add_argument("--image-pack-manifest", required=True, type=Path)
    parser.add_argument("--pose-prior", action="append", default=[], help="Pose prior summary as name=path.")
    parser.add_argument("--segment-results-dir", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--target-lane",
        default="hybrid_mesh_opendrive_plus_static_3dgs_visual_layer",
        help="CARLA/NVIDIA handoff lane recorded in the report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_quality_gate(
        image_pack_manifest=args.image_pack_manifest,
        pose_prior_specs=args.pose_prior,
        segment_results_dir=args.segment_results_dir,
        output_dir=args.output_dir,
        target_lane=args.target_lane,
    )
    print(json.dumps({"status": report["status"], "output_dir": str(args.output_dir)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
