#!/usr/bin/env python3
"""Project saved lidar board-hit samples onto captured CARLA camera images."""

from __future__ import annotations

import argparse
import glob
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VIEW_SPECS = {
    "front": ((2.0, 0.0, 2.0), 0.0),
    "left": ((0.0, -0.4, 2.0), -90.0),
    "right": ((0.0, 0.4, 2.0), 90.0),
    "rear": ((-2.0, 0.0, 2.0), 180.0),
}
LIDAR_COLORS = {
    "lidar_ft_base_link": (255, 48, 48),
    "lidar_rt_base_link": (255, 176, 0),
    "lidar_rear_base_link": (0, 210, 120),
    "lidar_fl_base_link": (0, 150, 255),
    "lidar_fr_base_link": (194, 86, 255),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _resolve_path(value: str | None) -> Path | None:
    if not value:
        return None
    matches = sorted(Path(item) for item in glob.glob(value))
    if matches:
        return matches[-1].resolve()
    path = Path(value)
    return path.resolve() if path.exists() else None


def find_scene_spawn_artifact(run_dir: Path, explicit_path: str | None) -> Path | None:
    explicit = _resolve_path(explicit_path)
    if explicit:
        return explicit
    candidates = sorted((run_dir / "runtime_verification" / "calibration_scene").glob("*_spawn.json"))
    return candidates[-1] if candidates else None


def find_lidar_hit_artifact(run_dir: Path, explicit_path: str | None) -> Path | None:
    explicit = _resolve_path(explicit_path)
    if explicit:
        return explicit
    pattern = run_dir / "runtime_verification" / "metric_probe_lidar_fiducial_board_hits_*" / "lidar_fiducial_board_hits.json"
    candidates = sorted(pattern.parent.parent.glob(f"{pattern.parent.name}/{pattern.name}"))
    return candidates[-1] if candidates else None


def _wrap_deg(value: float) -> float:
    while value <= -180.0:
        value += 360.0
    while value > 180.0:
        value -= 360.0
    return value


def _mean_angle_deg(values: list[float]) -> float:
    sine = sum(math.sin(math.radians(value)) for value in values)
    cosine = sum(math.cos(math.radians(value)) for value in values)
    return math.degrees(math.atan2(sine, cosine))


def _rotate_yaw(point: tuple[float, float, float], yaw_deg: float) -> tuple[float, float, float]:
    yaw = math.radians(yaw_deg)
    cosine = math.cos(yaw)
    sine = math.sin(yaw)
    return (
        (point[0] * cosine) - (point[1] * sine),
        (point[0] * sine) + (point[1] * cosine),
        point[2],
    )


def _sub(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _add(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return (left[0] * right[0]) + (left[1] * right[1]) + (left[2] * right[2])


def _cross(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        (left[1] * right[2]) - (left[2] * right[1]),
        (left[2] * right[0]) - (left[0] * right[2]),
        (left[0] * right[1]) - (left[1] * right[0]),
    )


def _normalize(value: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(_dot(value, value))
    if length <= 1e-9:
        return (0.0, 0.0, 0.0)
    return (value[0] / length, value[1] / length, value[2] / length)


def infer_ego_pose_from_scene(scene_payload: dict[str, Any]) -> dict[str, float]:
    targets = {
        str(target.get("target_id")): target
        for target in scene_payload.get("targets", [])
        if isinstance(target, dict)
    }
    yaw_values: list[float] = []
    samples: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for spawned in scene_payload.get("spawned", []):
        if not isinstance(spawned, dict):
            continue
        target = targets.get(str(spawned.get("target_id"))) or {}
        world_transform = spawned.get("world_transform") if isinstance(spawned.get("world_transform"), dict) else {}
        local_pose = target.get("local_pose") if isinstance(target.get("local_pose"), dict) else {}
        if not world_transform or not local_pose:
            continue
        ego_yaw = _wrap_deg(float(world_transform.get("yaw") or 0.0) + float(local_pose.get("yaw_deg") or 0.0))
        yaw_values.append(ego_yaw)
        local_carla = (
            float(local_pose.get("x") or 0.0),
            -float(local_pose.get("y") or 0.0),
            float(local_pose.get("z") or 0.0),
        )
        world = (
            float(world_transform.get("x") or 0.0),
            float(world_transform.get("y") or 0.0),
            float(world_transform.get("z") or 0.0),
        )
        samples.append((world, local_carla))
    if not yaw_values or not samples:
        return {"x": 0.0, "y": 0.0, "z": 0.0, "yaw_deg": 0.0}
    ego_yaw = _mean_angle_deg(yaw_values)
    origins = [_sub(world, _rotate_yaw(local_carla, ego_yaw)) for world, local_carla in samples]
    count = float(len(origins))
    return {
        "x": sum(item[0] for item in origins) / count,
        "y": sum(item[1] for item in origins) / count,
        "z": sum(item[2] for item in origins) / count,
        "yaw_deg": ego_yaw,
    }


def camera_pose_from_ego(
    ego_pose: dict[str, float],
    view_name: str,
    camera_pitch_deg: float,
) -> dict[str, float]:
    local_xyz, yaw_offset = VIEW_SPECS[view_name]
    rotated = _rotate_yaw(local_xyz, float(ego_pose.get("yaw_deg") or 0.0))
    camera_location = _add(
        (
            float(ego_pose.get("x") or 0.0),
            float(ego_pose.get("y") or 0.0),
            float(ego_pose.get("z") or 0.0),
        ),
        rotated,
    )
    return {
        "x": camera_location[0],
        "y": camera_location[1],
        "z": camera_location[2],
        "yaw_deg": float(ego_pose.get("yaw_deg") or 0.0) + yaw_offset,
        "pitch_deg": camera_pitch_deg,
    }


def camera_basis(camera_pose: dict[str, float]) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    yaw = math.radians(float(camera_pose.get("yaw_deg") or 0.0))
    pitch = math.radians(float(camera_pose.get("pitch_deg") or 0.0))
    cosine_pitch = math.cos(pitch)
    forward = (
        cosine_pitch * math.cos(yaw),
        cosine_pitch * math.sin(yaw),
        math.sin(pitch),
    )
    right = (-math.sin(yaw), math.cos(yaw), 0.0)
    up = _normalize(_cross(right, forward))
    return (forward, right, up)


def project_world_point(
    point: tuple[float, float, float],
    camera_pose: dict[str, float],
    image_width: int,
    image_height: int,
    camera_fov_deg: float,
) -> tuple[float, float, float] | None:
    camera_location = (
        float(camera_pose.get("x") or 0.0),
        float(camera_pose.get("y") or 0.0),
        float(camera_pose.get("z") or 0.0),
    )
    relative = _sub(point, camera_location)
    forward, right, up = camera_basis(camera_pose)
    depth = _dot(relative, forward)
    if depth <= 0.05:
        return None
    focal = image_width / (2.0 * math.tan(math.radians(camera_fov_deg) / 2.0))
    u = focal * (_dot(relative, right) / depth) + (image_width / 2.0)
    v = focal * (-_dot(relative, up) / depth) + (image_height / 2.0)
    return (u, v, depth)


def lidar_hit_samples(lidar_payload: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for lidar in lidar_payload.get("lidars", []):
        if not isinstance(lidar, dict):
            continue
        lidar_id = str(lidar.get("lidar_id") or "unknown_lidar")
        for point in lidar.get("hit_points_sample") or []:
            if not isinstance(point, dict):
                continue
            try:
                xyz = (float(point["x"]), float(point["y"]), float(point["z"]))
            except (KeyError, TypeError, ValueError):
                continue
            samples.append(
                {
                    "lidar_id": lidar_id,
                    "target_id": str(point.get("target_id") or "unknown_target"),
                    "xyz": xyz,
                    "intensity": float(point.get("intensity") or 0.0),
                }
            )
    return samples


def _load_pil_backend() -> Any:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-not-found]
    except ImportError:
        return None
    return {"Image": Image, "ImageDraw": ImageDraw, "ImageFont": ImageFont}


def _load_cv2_backend() -> Any:
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except ImportError:
        return None
    return {"cv2": cv2, "np": np}


def image_size(image_path: Path) -> tuple[int, int]:
    pil_backend = _load_pil_backend()
    if pil_backend is not None:
        with pil_backend["Image"].open(image_path) as image:
            return (int(image.size[0]), int(image.size[1]))
    cv2_backend = _load_cv2_backend()
    if cv2_backend is not None:
        image = cv2_backend["cv2"].imread(str(image_path), cv2_backend["cv2"].IMREAD_COLOR)
        if image is not None:
            return (int(image.shape[1]), int(image.shape[0]))
    raise RuntimeError("Pillow or OpenCV is required to read camera image size")


def render_projection_image_cv2(
    image_path: Path,
    output_path: Path,
    projected: list[dict[str, Any]],
    title: str,
) -> None:
    backend = _load_cv2_backend()
    if backend is None:
        raise RuntimeError("Pillow or OpenCV is required to render lidar projection images")
    cv2 = backend["cv2"]
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unable to read image: {image_path}")
    height, width = image.shape[:2]
    in_frame = [
        item
        for item in projected
        if 0.0 <= float(item["u"]) < width and 0.0 <= float(item["v"]) < height
    ]
    overlay = image.copy()
    for item in sorted(in_frame, key=lambda value: float(value["depth_m"]), reverse=True):
        u = int(round(float(item["u"])))
        v = int(round(float(item["v"])))
        depth = float(item["depth_m"])
        color_rgb = LIDAR_COLORS.get(str(item["lidar_id"]), (255, 255, 255))
        color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
        radius = max(4, min(10, int(16 - depth / 8.0)))
        cv2.circle(overlay, (u, v), radius, color_bgr, -1, lineType=cv2.LINE_AA)
        cv2.circle(overlay, (u, v), radius, (0, 0, 0), 2, lineType=cv2.LINE_AA)
    image = cv2.addWeighted(overlay, 0.82, image, 0.18, 0)

    grouped: dict[str, list[tuple[float, float]]] = {}
    for item in in_frame:
        grouped.setdefault(str(item["target_id"]), []).append((float(item["u"]), float(item["v"])))
    for target_id, points in sorted(grouped.items(), key=lambda value: -len(value[1]))[:5]:
        u = int(round(sum(point[0] for point in points) / float(len(points))))
        v = int(round(sum(point[1] for point in points) / float(len(points))))
        label = f"{target_id} ({len(points)})"
        (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(image, (u + 8, v - 18), (u + text_width + 18, v + 8), (0, 0, 0), -1)
        cv2.putText(image, label, (u + 12, v), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    (title_width, _), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)
    cv2.rectangle(image, (12, 12), (12 + title_width + 16, 45), (0, 0, 0), -1)
    cv2.putText(image, title, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1, cv2.LINE_AA)
    y = 64
    by_lidar: dict[str, int] = {}
    for item in in_frame:
        by_lidar[str(item["lidar_id"])] = by_lidar.get(str(item["lidar_id"]), 0) + 1
    for lidar_id, color_rgb in LIDAR_COLORS.items():
        count = by_lidar.get(lidar_id, 0)
        if not count:
            continue
        color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
        cv2.circle(image, (27, y - 5), 7, color_bgr, -1, lineType=cv2.LINE_AA)
        cv2.putText(image, f"{lidar_id}: {count}", (42, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        y += 20

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)


def render_projection_image(
    image_path: Path,
    output_path: Path,
    projected: list[dict[str, Any]],
    title: str,
) -> None:
    backend = _load_pil_backend()
    if backend is None:
        render_projection_image_cv2(image_path, output_path, projected, title)
        return
    Image = backend["Image"]
    ImageDraw = backend["ImageDraw"]
    ImageFont = backend["ImageFont"]
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
        small_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 15)
    except Exception:
        font = None
        small_font = None
    width, height = image.size
    in_frame = [
        item
        for item in projected
        if 0.0 <= float(item["u"]) < width and 0.0 <= float(item["v"]) < height
    ]
    for item in sorted(in_frame, key=lambda value: float(value["depth_m"]), reverse=True):
        u = float(item["u"])
        v = float(item["v"])
        depth = float(item["depth_m"])
        color = LIDAR_COLORS.get(str(item["lidar_id"]), (255, 255, 255))
        radius = max(4, min(10, int(16 - depth / 8.0)))
        draw.ellipse((u - radius, v - radius, u + radius, v + radius), fill=(*color, 210), outline=(0, 0, 0, 230), width=2)

    grouped: dict[str, list[tuple[float, float]]] = {}
    for item in in_frame:
        grouped.setdefault(str(item["target_id"]), []).append((float(item["u"]), float(item["v"])))
    for target_id, points in sorted(grouped.items(), key=lambda value: -len(value[1]))[:5]:
        u = sum(point[0] for point in points) / float(len(points))
        v = sum(point[1] for point in points) / float(len(points))
        label = f"{target_id} ({len(points)})"
        text_width = draw.textlength(label, font=small_font) if small_font else len(label) * 8
        draw.rectangle((u + 8, v - 13, u + text_width + 16, v + 9), fill=(0, 0, 0, 150))
        draw.text((u + 12, v - 12), label, fill=(255, 255, 255, 240), font=small_font)

    title_width = draw.textlength(title, font=font) if font else len(title) * 9
    draw.rectangle((12, 12, 12 + title_width + 16, 45), fill=(0, 0, 0, 160))
    draw.text((20, 18), title, fill=(255, 255, 255, 255), font=font)
    y = 58
    by_lidar: dict[str, int] = {}
    for item in in_frame:
        by_lidar[str(item["lidar_id"])] = by_lidar.get(str(item["lidar_id"]), 0) + 1
    for lidar_id, color in LIDAR_COLORS.items():
        count = by_lidar.get(lidar_id, 0)
        if not count:
            continue
        draw.ellipse((20, y, 34, y + 14), fill=(*color, 230), outline=(0, 0, 0, 255))
        draw.text((42, y - 2), f"{lidar_id}: {count}", fill=(255, 255, 255, 245), font=small_font)
        y += 20

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def write_contact_sheet(image_paths: list[Path], output_path: Path) -> None:
    backend = _load_pil_backend()
    if not image_paths:
        return
    if backend is None:
        cv2_backend = _load_cv2_backend()
        if cv2_backend is None:
            return
        cv2 = cv2_backend["cv2"]
        np = cv2_backend["np"]
        sheet = np.full((1000, 1600, 3), 18, dtype=np.uint8)
        for index, path in enumerate(image_paths[:4]):
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                continue
            height, width = image.shape[:2]
            scale = min(800.0 / float(width), 500.0 / float(height))
            resized = cv2.resize(image, (int(width * scale), int(height * scale)))
            tile_y = (index // 2) * 500
            tile_x = (index % 2) * 800
            y_offset = tile_y + ((500 - resized.shape[0]) // 2)
            x_offset = tile_x + ((800 - resized.shape[1]) // 2)
            sheet[y_offset : y_offset + resized.shape[0], x_offset : x_offset + resized.shape[1]] = resized
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), sheet)
        return
    Image = backend["Image"]
    tiles = []
    for path in image_paths:
        image = Image.open(path).convert("RGB")
        image.thumbnail((800, 500))
        tile = Image.new("RGB", (800, 500), (18, 18, 18))
        tile.paste(image, ((800 - image.width) // 2, (500 - image.height) // 2))
        tiles.append(tile)
    sheet = Image.new("RGB", (1600, 1000), (18, 18, 18))
    for index, tile in enumerate(tiles[:4]):
        sheet.paste(tile, ((index % 2) * 800, (index // 2) * 500))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir).resolve()
    runtime_dir = run_dir / "runtime_verification"
    scene_path = find_scene_spawn_artifact(run_dir, args.scene_spawn_artifact)
    lidar_path = find_lidar_hit_artifact(run_dir, args.lidar_hit_artifact)
    image_dir = Path(args.image_dir).resolve() if args.image_dir else runtime_dir / "calibration" / "camera_fiducial_board_detection" / "images"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else runtime_dir / f"metric_probe_lidar_camera_projection_{timestamp}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    missing_reasons = []
    if scene_path is None:
        missing_reasons.append("missing_scene_spawn_artifact")
    if lidar_path is None:
        missing_reasons.append("missing_lidar_hit_artifact")
    if not image_dir.exists():
        missing_reasons.append("missing_camera_image_dir")
    if missing_reasons:
        payload = {
            "generated_at": utc_now(),
            "profile": "lidar_camera_projection",
            "overall_passed": False,
            "blocked_reason": ",".join(missing_reasons),
            "metrics": {},
            "scene_spawn_artifact": str(scene_path) if scene_path else None,
            "lidar_hit_artifact": str(lidar_path) if lidar_path else None,
            "image_dir": str(image_dir),
            "views": [],
        }
        output_path = output_dir / "lidar_camera_projection.json"
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        payload["result_path"] = str(output_path)
        return payload

    scene_payload = _load_json(scene_path)
    lidar_payload = _load_json(lidar_path)
    ego_pose = infer_ego_pose_from_scene(scene_payload)
    samples = lidar_hit_samples(lidar_payload)
    views = [item.strip() for item in str(args.capture_views).split(",") if item.strip()]
    view_results = []
    projection_images: list[Path] = []
    total_in_frame = 0
    for view in views:
        if view not in VIEW_SPECS:
            raise ValueError(f"Unsupported view: {view}")
        image_path = image_dir / f"{view}_camera.png"
        if not image_path.exists():
            view_results.append({"view": view, "status": "missing_image", "image": str(image_path)})
            continue
        width, height = image_size(image_path)
        camera_pose = camera_pose_from_ego(ego_pose, view, float(args.camera_pitch_deg))
        projected = []
        for sample in samples:
            projection = project_world_point(
                sample["xyz"],
                camera_pose,
                width,
                height,
                float(args.camera_fov_deg),
            )
            if projection is None:
                continue
            u, v, depth = projection
            if -float(args.edge_slop_px) <= u <= width + float(args.edge_slop_px) and -float(args.edge_slop_px) <= v <= height + float(args.edge_slop_px):
                projected.append(
                    {
                        "u": u,
                        "v": v,
                        "depth_m": depth,
                        "lidar_id": sample["lidar_id"],
                        "target_id": sample["target_id"],
                    }
                )
        in_frame = [
            item
            for item in projected
            if 0.0 <= float(item["u"]) < width and 0.0 <= float(item["v"]) < height
        ]
        total_in_frame += len(in_frame)
        by_lidar: dict[str, int] = {}
        by_target: dict[str, int] = {}
        for item in in_frame:
            by_lidar[str(item["lidar_id"])] = by_lidar.get(str(item["lidar_id"]), 0) + 1
            by_target[str(item["target_id"])] = by_target.get(str(item["target_id"]), 0) + 1
        output_path = output_dir / f"{view}_camera_lidar_projection.png"
        render_projection_image(
            image_path,
            output_path,
            projected,
            f"LiDAR board-hit samples projected to {view}_camera | in-frame {len(in_frame)}/{len(samples)}",
        )
        projection_images.append(output_path)
        view_results.append(
            {
                "view": view,
                "status": "projected",
                "image": str(image_path),
                "projection_image": str(output_path),
                "projected_near_frame_count": len(projected),
                "in_frame_count": len(in_frame),
                "by_lidar": by_lidar,
                "by_target": by_target,
            }
        )

    contact_sheet_path = output_dir / "lidar_projection_contact_sheet.png"
    write_contact_sheet(projection_images, contact_sheet_path)
    projected_view_count = sum(1 for item in view_results if int(item.get("in_frame_count") or 0) > 0)
    missing_reasons = []
    if total_in_frame < int(args.min_in_frame_count):
        missing_reasons.append("insufficient_lidar_points_projected_to_camera_images")
    if projected_view_count < int(args.min_projected_views):
        missing_reasons.append("insufficient_camera_views_with_projected_lidar_points")
    payload = {
        "generated_at": utc_now(),
        "profile": "lidar_camera_projection",
        "point_source": "lidar_fiducial_board_hit_points_sample",
        "overall_passed": not missing_reasons,
        "blocked_reason": ",".join(missing_reasons) if missing_reasons else None,
        "missing_metrics": [],
        "missing_topics": [],
        "sample_missing_topics": [],
        "scene_spawn_artifact": str(scene_path),
        "lidar_hit_artifact": str(lidar_path),
        "image_dir": str(image_dir),
        "output_dir": str(output_dir),
        "ego_pose_inferred": ego_pose,
        "sample_count": len(samples),
        "views": view_results,
        "contact_sheet": str(contact_sheet_path) if contact_sheet_path.exists() else None,
        "metrics": {
            "lidar_camera_projection_sample_count": float(len(samples)),
            "lidar_camera_projection_in_frame_count": float(total_in_frame),
            "lidar_camera_projection_view_count": float(projected_view_count),
        },
    }
    output_path = output_dir / "lidar_camera_projection.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["result_path"] = str(output_path)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--scene-spawn-artifact")
    parser.add_argument("--lidar-hit-artifact")
    parser.add_argument("--image-dir")
    parser.add_argument("--output-dir")
    parser.add_argument("--capture-views", default="front,left,right,rear")
    parser.add_argument("--camera-fov-deg", type=float, default=95.0)
    parser.add_argument("--camera-pitch-deg", type=float, default=-5.0)
    parser.add_argument("--edge-slop-px", type=float, default=60.0)
    parser.add_argument("--min-in-frame-count", type=int, default=20)
    parser.add_argument("--min-projected-views", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    payload = run_probe(parse_args())
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
