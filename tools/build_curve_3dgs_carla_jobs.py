from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import yaml


CAMERA_IMAGE_TYPES = {
    "sensor_msgs/msg/CompressedImage",
    "sensor_msgs/msg/Image",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def wrap_angle_rad(angle: float) -> float:
    while angle <= -math.pi:
        angle += 2.0 * math.pi
    while angle > math.pi:
        angle -= 2.0 * math.pi
    return angle


def distance_xy(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def expand_bbox(bbox: list[float], margin_m: float) -> list[float]:
    return [bbox[0] - margin_m, bbox[1] - margin_m, bbox[2] + margin_m, bbox[3] + margin_m]


@dataclass(frozen=True)
class XodrGeometry:
    road_id: str
    road_name: str
    s: float
    x: float
    y: float
    hdg: float
    length: float
    geom_type: str
    curvature: float = 0.0


@dataclass(frozen=True)
class CurveCandidate:
    road_id: str
    road_name: str
    geometry_count: int
    length_m: float
    cumulative_abs_turn_deg: float
    signed_turn_deg: float
    max_step_turn_deg: float
    bbox_xy_m: list[float]
    center_xy_m: tuple[float, float]
    start_xy_m: tuple[float, float]
    end_xy_m: tuple[float, float]

    @property
    def direction(self) -> str:
        if self.signed_turn_deg > 0:
            return "left"
        if self.signed_turn_deg < 0:
            return "right"
        return "mixed"


def geometry_end_xy(geometry: XodrGeometry) -> tuple[float, float]:
    if geometry.geom_type == "arc" and abs(geometry.curvature) > 1e-9:
        radius = 1.0 / geometry.curvature
        delta = geometry.curvature * geometry.length
        cx = geometry.x - radius * math.sin(geometry.hdg)
        cy = geometry.y + radius * math.cos(geometry.hdg)
        end_hdg = geometry.hdg + delta
        return cx + radius * math.sin(end_hdg), cy - radius * math.cos(end_hdg)
    return geometry.x + math.cos(geometry.hdg) * geometry.length, geometry.y + math.sin(geometry.hdg) * geometry.length


def parse_xodr_geometries(xodr_path: Path) -> list[list[XodrGeometry]]:
    root = ET.parse(xodr_path).getroot()
    roads: list[list[XodrGeometry]] = []
    for road in root.findall("road"):
        plan_view = road.find("planView")
        if plan_view is None:
            continue
        road_id = road.get("id") or ""
        road_name = road.get("name") or ""
        geometries: list[XodrGeometry] = []
        for geometry in plan_view.findall("geometry"):
            geom_type = "line"
            curvature = 0.0
            if geometry.find("arc") is not None:
                geom_type = "arc"
                curvature = float(geometry.find("arc").get("curvature") or 0.0)
            elif geometry.find("spiral") is not None:
                geom_type = "spiral"
            elif geometry.find("poly3") is not None:
                geom_type = "poly3"
            elif geometry.find("paramPoly3") is not None:
                geom_type = "paramPoly3"
            geometries.append(
                XodrGeometry(
                    road_id=road_id,
                    road_name=road_name,
                    s=float(geometry.get("s") or 0.0),
                    x=float(geometry.get("x") or 0.0),
                    y=float(geometry.get("y") or 0.0),
                    hdg=float(geometry.get("hdg") or 0.0),
                    length=float(geometry.get("length") or 0.0),
                    geom_type=geom_type,
                    curvature=curvature,
                )
            )
        if geometries:
            roads.append(sorted(geometries, key=lambda item: item.s))
    return roads


def candidate_from_geometries(geometries: list[XodrGeometry]) -> CurveCandidate | None:
    if not geometries:
        return None
    signed_turn = 0.0
    absolute_turn = 0.0
    max_step = 0.0
    for index, geometry in enumerate(geometries):
        if geometry.geom_type == "arc" and abs(geometry.curvature) > 1e-9:
            delta = geometry.curvature * geometry.length
        elif index + 1 < len(geometries):
            delta = wrap_angle_rad(geometries[index + 1].hdg - geometry.hdg)
        else:
            delta = 0.0
        signed_turn += delta
        absolute_turn += abs(delta)
        max_step = max(max_step, abs(delta))

    points: list[tuple[float, float]] = []
    for geometry in geometries:
        points.append((geometry.x, geometry.y))
    points.append(geometry_end_xy(geometries[-1]))

    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    length_m = sum(geometry.length for geometry in geometries)
    center = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
    return CurveCandidate(
        road_id=geometries[0].road_id,
        road_name=geometries[0].road_name,
        geometry_count=len(geometries),
        length_m=length_m,
        cumulative_abs_turn_deg=math.degrees(absolute_turn),
        signed_turn_deg=math.degrees(signed_turn),
        max_step_turn_deg=math.degrees(max_step),
        bbox_xy_m=[min_x, min_y, max_x, max_y],
        center_xy_m=center,
        start_xy_m=(geometries[0].x, geometries[0].y),
        end_xy_m=geometry_end_xy(geometries[-1]),
    )


def detect_curve_candidates(
    xodr_path: Path,
    min_cumulative_turn_deg: float,
    min_length_m: float,
) -> list[CurveCandidate]:
    candidates: list[CurveCandidate] = []
    for geometries in parse_xodr_geometries(xodr_path):
        candidate = candidate_from_geometries(geometries)
        if candidate is None:
            continue
        if candidate.length_m < min_length_m:
            continue
        if candidate.cumulative_abs_turn_deg < min_cumulative_turn_deg:
            continue
        candidates.append(candidate)
    return candidates


def _direction_compatible(a: str, b: str) -> bool:
    return a == b or "mixed" in {a, b}


def cluster_candidates(candidates: list[CurveCandidate], cluster_radius_m: float) -> list[list[CurveCandidate]]:
    clusters: list[list[CurveCandidate]] = []
    for candidate in sorted(candidates, key=lambda item: (item.center_xy_m[0], item.center_xy_m[1], item.road_id)):
        best_index: int | None = None
        best_distance = float("inf")
        for index, cluster in enumerate(clusters):
            cluster_center = cluster_center_xy(cluster)
            candidate_distance = distance_xy(candidate.center_xy_m, cluster_center)
            if candidate_distance <= cluster_radius_m and _direction_compatible(candidate.direction, cluster_direction(cluster)):
                if candidate_distance < best_distance:
                    best_index = index
                    best_distance = candidate_distance
        if best_index is None:
            clusters.append([candidate])
        else:
            clusters[best_index].append(candidate)
    return clusters


def cluster_center_xy(cluster: list[CurveCandidate]) -> tuple[float, float]:
    total = sum(max(candidate.length_m, 1.0) for candidate in cluster)
    x = sum(candidate.center_xy_m[0] * max(candidate.length_m, 1.0) for candidate in cluster) / total
    y = sum(candidate.center_xy_m[1] * max(candidate.length_m, 1.0) for candidate in cluster) / total
    return x, y


def cluster_direction(cluster: list[CurveCandidate]) -> str:
    signed = sum(candidate.signed_turn_deg for candidate in cluster)
    if signed > 0:
        return "left"
    if signed < 0:
        return "right"
    return "mixed"


def cluster_bbox(cluster: list[CurveCandidate]) -> list[float]:
    return [
        min(candidate.bbox_xy_m[0] for candidate in cluster),
        min(candidate.bbox_xy_m[1] for candidate in cluster),
        max(candidate.bbox_xy_m[2] for candidate in cluster),
        max(candidate.bbox_xy_m[3] for candidate in cluster),
    ]


def load_yaml_file(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def camera_topics_from_metadata(metadata: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    topics = (
        metadata.get("rosbag2_bagfile_information", {})
        .get("topics_with_message_count", [])
    )
    image_topics: list[dict[str, Any]] = []
    camera_info_topics: list[dict[str, Any]] = []
    for item in topics:
        topic_metadata = item.get("topic_metadata", {})
        topic_type = topic_metadata.get("type")
        row = {
            "name": topic_metadata.get("name"),
            "type": topic_type,
            "message_count": item.get("message_count", 0),
        }
        if topic_type in CAMERA_IMAGE_TYPES:
            image_topics.append(row)
        elif topic_type == "sensor_msgs/msg/CameraInfo":
            camera_info_topics.append(row)
    return {
        "image_topics": sorted(image_topics, key=lambda row: row["name"] or ""),
        "camera_info_topics": sorted(camera_info_topics, key=lambda row: row["name"] or ""),
    }


def trajectory_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"path": str(path) if path else None, "status": "missing"}
    with path.open("r", encoding="utf-8") as fh:
        header = fh.readline().strip().split(",")
        first = fh.readline().strip().split(",")
        last = first
        rows = 1 if first and first != [""] else 0
        for line in fh:
            if line.strip():
                last = line.strip().split(",")
                rows += 1
    def row_to_dict(row: list[str]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key, value in zip(header, row):
            try:
                values[key] = float(value)
            except ValueError:
                values[key] = value
        return values
    return {
        "path": str(path),
        "status": "present",
        "sample_count": rows,
        "first_sample": row_to_dict(first) if first and first != [""] else {},
        "last_sample": row_to_dict(last) if last and last != [""] else {},
    }


def build_jobs(
    *,
    xodr_path: Path,
    source_bag: Path | None,
    metadata_path: Path | None,
    pointcloud_ply: Path | None,
    trajectory_csv: Path | None,
    import_manifest: Path | None,
    import_preflight_report: Path | None,
    output_dir: Path,
    min_cumulative_turn_deg: float,
    min_length_m: float,
    cluster_radius_m: float,
    crop_margin_m: float,
    carla_runtime: str,
    map_package: str,
) -> dict[str, Any]:
    candidates = detect_curve_candidates(xodr_path, min_cumulative_turn_deg, min_length_m)
    clusters = cluster_candidates(candidates, cluster_radius_m)
    metadata = load_yaml_file(metadata_path)
    import_manifest_payload = load_yaml_file(import_manifest)
    import_preflight_payload = load_yaml_file(import_preflight_report)
    local_frame = import_preflight_payload.get("local_frame", {})
    origin_map_xyz = local_frame.get("origin_map_xyz_from_input_manifest")
    camera_topics = camera_topics_from_metadata(metadata)
    image_topic_count = sum(topic.get("message_count", 0) for topic in camera_topics["image_topics"])
    extraction_status = "ready_for_frame_pose_extraction" if image_topic_count > 0 else "blocked_no_camera_image_topics"

    job_rows: list[dict[str, Any]] = []
    for index, cluster in enumerate(clusters, start=1):
        curve_id = f"qiyu_curve_{index:03d}"
        bbox = cluster_bbox(cluster)
        center = cluster_center_xy(cluster)
        job_dir = output_dir / "jobs" / curve_id
        crop_bbox = expand_bbox(bbox, crop_margin_m)
        source_map_crop_bbox = None
        if isinstance(origin_map_xyz, list) and len(origin_map_xyz) >= 2:
            source_map_crop_bbox = [
                crop_bbox[0] + float(origin_map_xyz[0]),
                crop_bbox[1] + float(origin_map_xyz[1]),
                crop_bbox[2] + float(origin_map_xyz[0]),
                crop_bbox[3] + float(origin_map_xyz[1]),
            ]
        job_rows.append(
            {
                "curve_id": curve_id,
                "status": extraction_status,
                "turn_direction": cluster_direction(cluster),
                "center_xy_m": [center[0], center[1]],
                "bbox_xy_m": bbox,
                "crop_bbox_xy_m": crop_bbox,
                "source_map_crop_bbox_xy_m": source_map_crop_bbox,
                "member_count": len(cluster),
                "member_road_ids": [candidate.road_id for candidate in cluster],
                "member_road_names": [candidate.road_name for candidate in cluster],
                "total_member_length_m": sum(candidate.length_m for candidate in cluster),
                "max_member_cumulative_turn_deg": max(candidate.cumulative_abs_turn_deg for candidate in cluster),
                "max_step_turn_deg": max(candidate.max_step_turn_deg for candidate in cluster),
                "expected_outputs": {
                    "frames_dir": str(job_dir / "frames"),
                    "camera_poses": str(job_dir / "camera_poses.json"),
                    "colmap_sparse": str(job_dir / "colmap" / "sparse"),
                    "static_gaussian": str(job_dir / "3dgs" / "point_cloud.ply"),
                    "preview": str(job_dir / "previews"),
                    "carla_mesh_proxy": str(job_dir / "carla" / "curve_visual_proxy.fbx"),
                    "carla_xodr_reference": str(xodr_path),
                    "handoff_manifest": str(job_dir / "curve_handoff_manifest.json"),
                },
                "carla_import_contract": {
                    "runtime_target": carla_runtime,
                    "map_package": map_package,
                    "drivable_import_asset": "mesh_plus_opendrive",
                    "visual_research_asset": "static_3dgs_or_nurec_layer",
                    "note": "Do not treat Gaussian splats as a direct CARLA 0.9.15 drivable map; keep mesh/XODR/collision as the import path.",
                },
            }
        )

    return {
        "manifest_id": "qiyu_loop_all_curves_3dgs_carla_jobs",
        "generated_at": utc_now(),
        "status": extraction_status if job_rows else "blocked_no_curve_candidates",
        "objective": "3DGS-first visual reconstruction for every detected Qiyu loop curve with CARLA-importable mesh/OpenDRIVE handoff boundaries",
        "source_assets": {
            "xodr": str(xodr_path),
            "source_bag": str(source_bag) if source_bag else None,
            "metadata": str(metadata_path) if metadata_path else None,
            "pointcloud_ply": str(pointcloud_ply) if pointcloud_ply else None,
            "trajectory_csv": trajectory_summary(trajectory_csv),
            "carla_import_manifest": str(import_manifest) if import_manifest else None,
            "carla_import_preflight_report": str(import_preflight_report) if import_preflight_report else None,
            "alignment": import_manifest_payload.get("alignment", {}),
            "map_to_local_frame": local_frame,
        },
        "thresholds": {
            "min_cumulative_turn_deg": min_cumulative_turn_deg,
            "min_length_m": min_length_m,
            "cluster_radius_m": cluster_radius_m,
            "crop_margin_m": crop_margin_m,
        },
        "camera_topics": camera_topics,
        "summary": {
            "curve_candidate_count": len(candidates),
            "curve_cluster_count": len(job_rows),
            "camera_image_topic_count": len(camera_topics["image_topics"]),
            "camera_image_message_count": image_topic_count,
            "camera_info_topic_count": len(camera_topics["camera_info_topics"]),
        },
        "next_gates": [
            "extract curve-scoped compressed camera frames from MCAP",
            "derive camera poses from /tf plus camera extrinsics for each frame",
            "run COLMAP or pose-prior sparse smoke per curve",
            "train static 3DGS per curve outside Git",
            "export CARLA handoff with mesh/OpenDRIVE/collision proxy plus optional Gaussian visual layer",
        ],
        "jobs": job_rows,
    }


def render_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# Qiyu Curve 3DGS CARLA Jobs",
        "",
        f"- status: `{manifest['status']}`",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- curve_candidates: `{manifest['summary']['curve_candidate_count']}`",
        f"- curve_clusters: `{manifest['summary']['curve_cluster_count']}`",
        f"- camera_image_topics: `{manifest['summary']['camera_image_topic_count']}`",
        f"- camera_image_messages: `{manifest['summary']['camera_image_message_count']}`",
        "",
        "## CARLA Import Contract",
        "",
        "3DGS is the visual reconstruction track. CARLA 0.9.15 import readiness still requires mesh plus OpenDRIVE plus collision proxy.",
        "",
        "## Jobs",
        "",
        "| curve_id | direction | members | max_turn_deg | bbox_xy_m | status |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for job in manifest["jobs"]:
        bbox = ", ".join(f"{value:.2f}" for value in job["bbox_xy_m"])
        lines.append(
            f"| `{job['curve_id']}` | {job['turn_direction']} | {job['member_count']} | "
            f"{job['max_member_cumulative_turn_deg']:.1f} | `{bbox}` | `{job['status']}` |"
        )
    lines.extend(["", "## Next Gates", ""])
    for gate in manifest["next_gates"]:
        lines.append(f"- {gate}")
    lines.append("")
    return "\n".join(lines)


def write_outputs(output_dir: Path, manifest: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "curve_3dgs_carla_jobs.json"
    markdown_path = output_dir / "curve_3dgs_carla_jobs.md"
    json_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(manifest), encoding="utf-8")
    return json_path, markdown_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build per-curve 3DGS plus CARLA handoff jobs from an OpenDRIVE map")
    parser.add_argument("--xodr", type=Path, required=True)
    parser.add_argument("--source-bag", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--pointcloud-ply", type=Path)
    parser.add_argument("--trajectory-csv", type=Path)
    parser.add_argument("--import-manifest", type=Path)
    parser.add_argument("--import-preflight-report", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-cumulative-turn-deg", type=float, default=25.0)
    parser.add_argument("--min-length-m", type=float, default=5.0)
    parser.add_argument("--cluster-radius-m", type=float, default=30.0)
    parser.add_argument("--crop-margin-m", type=float, default=35.0)
    parser.add_argument("--carla-runtime", default="CARLA 0.9.15 / UE4.26")
    parser.add_argument("--map-package", default="qiyu_loop_20260430_105120")
    args = parser.parse_args(argv)

    manifest = build_jobs(
        xodr_path=args.xodr,
        source_bag=args.source_bag,
        metadata_path=args.metadata,
        pointcloud_ply=args.pointcloud_ply,
        trajectory_csv=args.trajectory_csv,
        import_manifest=args.import_manifest,
        import_preflight_report=args.import_preflight_report,
        output_dir=args.output_dir,
        min_cumulative_turn_deg=args.min_cumulative_turn_deg,
        min_length_m=args.min_length_m,
        cluster_radius_m=args.cluster_radius_m,
        crop_margin_m=args.crop_margin_m,
        carla_runtime=args.carla_runtime,
        map_package=args.map_package,
    )
    json_path, markdown_path = write_outputs(args.output_dir, manifest)
    print(json.dumps({"status": manifest["status"], "jobs": len(manifest["jobs"]), "json": str(json_path), "markdown": str(markdown_path)}, ensure_ascii=False, indent=2))
    return 0 if manifest["jobs"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
