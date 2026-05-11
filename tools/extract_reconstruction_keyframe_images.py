from __future__ import annotations

import argparse
import bisect
import csv
import io
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - host dependency check covers this.
    Image = None
    ImageDraw = None


COMPRESSED_IMAGE_TYPE = "sensor_msgs/msg/CompressedImage"
CAMERA_INFO_TYPE = "sensor_msgs/msg/CameraInfo"
TF_TOPICS = ["/tf_static", "/tf_static_relay"]


@dataclass(frozen=True)
class StaticTransform:
    parent: str
    child: str
    translation: tuple[float, float, float]
    rotation_xyzw: tuple[float, float, float, float]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_topic_name(topic: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", topic.strip("/")) or "topic"


def load_metadata(metadata_path: Path) -> dict[str, Any]:
    with metadata_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def compressed_image_topics(metadata: dict[str, Any]) -> list[str]:
    topics = (
        metadata.get("rosbag2_bagfile_information", {})
        .get("topics_with_message_count", [])
    )
    selected = []
    for item in topics:
        topic_metadata = item.get("topic_metadata", {})
        if topic_metadata.get("type") == COMPRESSED_IMAGE_TYPE:
            selected.append(str(topic_metadata.get("name")))
    return sorted(selected)


def default_camera_info_topic(image_topic: str) -> str | None:
    match = re.match(r"^/electronic_rearview_mirror/([^/]+)/camera_image_jpeg$", image_topic)
    if not match:
        return None
    return f"/sensing/camera/{match.group(1)}/camera_info"


def ros_stamp_ns(message: Any) -> int | None:
    header = getattr(message, "header", None)
    stamp = getattr(header, "stamp", None)
    if stamp is None:
        return None
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def load_keyframes(path: Path, stride: int, max_keyframes: int) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    keyframes = payload["keyframes"] if isinstance(payload, dict) and "keyframes" in payload else payload
    keyframes = sorted(keyframes, key=lambda row: int(row["time_ns"]))
    if stride > 1:
        keyframes = keyframes[::stride]
    if max_keyframes > 0:
        keyframes = keyframes[:max_keyframes]
    return keyframes


def nearest_keyframe_index(times: list[int], time_ns: int, tolerance_ns: int) -> int | None:
    index = bisect.bisect_left(times, time_ns)
    candidates = []
    if index < len(times):
        candidates.append(index)
    if index > 0:
        candidates.append(index - 1)
    if not candidates:
        return None
    best = min(candidates, key=lambda idx: abs(times[idx] - time_ns))
    return best if abs(times[best] - time_ns) <= tolerance_ns else None


def quaternion_to_matrix(q: tuple[float, float, float, float]) -> np.ndarray:
    x, y, z, w = q
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm == 0:
        return np.eye(3)
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=float,
    )


def transform_matrix(translation: tuple[float, float, float], rotation_xyzw: tuple[float, float, float, float]) -> np.ndarray:
    mat = np.eye(4, dtype=float)
    mat[:3, :3] = quaternion_to_matrix(rotation_xyzw)
    mat[:3, 3] = np.array(translation, dtype=float)
    return mat


def yaw_matrix(yaw_rad: float) -> np.ndarray:
    c = math.cos(yaw_rad)
    s = math.sin(yaw_rad)
    mat = np.eye(4, dtype=float)
    mat[:3, :3] = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=float)
    return mat


def map_to_base_matrix(keyframe: dict[str, Any]) -> np.ndarray:
    mat = yaw_matrix(float(keyframe["yaw_rad"]))
    mat[:3, 3] = np.array([float(keyframe["x"]), float(keyframe["y"]), float(keyframe["z"])], dtype=float)
    return mat


def read_calibration(
    bag_dir: Path,
    image_topics: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], StaticTransform]]:
    camera_info_topics = {
        topic: default_camera_info_topic(topic)
        for topic in image_topics
        if default_camera_info_topic(topic) is not None
    }
    requested_info_topics = sorted(set(camera_info_topics.values()))
    selected_topics = requested_info_topics + TF_TOPICS
    camera_info_by_topic: dict[str, dict[str, Any]] = {}
    static_transforms: dict[tuple[str, str], StaticTransform] = {}
    decoder_factory = DecoderFactory()

    for path in sorted(bag_dir.glob("*.mcap")):
        with path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[decoder_factory])
            for _, channel, message, decoded in reader.iter_decoded_messages(topics=selected_topics, log_time_order=True):
                topic = channel.topic
                if topic in requested_info_topics and topic not in camera_info_by_topic:
                    camera_info_by_topic[topic] = {
                        "topic": topic,
                        "log_time_ns": int(message.log_time),
                        "stamp_ns": ros_stamp_ns(decoded),
                        "frame_id": str(decoded.header.frame_id),
                        "width": int(decoded.width),
                        "height": int(decoded.height),
                        "distortion_model": str(decoded.distortion_model),
                        "d": [float(value) for value in decoded.d],
                        "k": [float(value) for value in decoded.k],
                        "r": [float(value) for value in decoded.r],
                        "p": [float(value) for value in decoded.p],
                    }
                elif topic in TF_TOPICS:
                    for tf in decoded.transforms:
                        parent = str(tf.header.frame_id)
                        child = str(tf.child_frame_id)
                        static_transforms.setdefault(
                            (parent, child),
                            StaticTransform(
                                parent=parent,
                                child=child,
                                translation=(
                                    float(tf.transform.translation.x),
                                    float(tf.transform.translation.y),
                                    float(tf.transform.translation.z),
                                ),
                                rotation_xyzw=(
                                    float(tf.transform.rotation.x),
                                    float(tf.transform.rotation.y),
                                    float(tf.transform.rotation.z),
                                    float(tf.transform.rotation.w),
                                ),
                            ),
                        )
        if all(topic in camera_info_by_topic for topic in requested_info_topics) and static_transforms:
            break

    image_calibration: dict[str, dict[str, Any]] = {}
    for image_topic, info_topic in camera_info_topics.items():
        if info_topic is None or info_topic not in camera_info_by_topic:
            continue
        image_calibration[image_topic] = camera_info_by_topic[info_topic]
    return image_calibration, static_transforms


def static_chain_matrix(
    static_transforms: dict[tuple[str, str], StaticTransform],
    parent: str,
    child: str,
) -> np.ndarray | None:
    direct = static_transforms.get((parent, child))
    if direct is not None:
        return transform_matrix(direct.translation, direct.rotation_xyzw)
    # This repo's capture uses base_link -> sensor_kit_base_link -> cameraN/camera_link.
    via = "sensor_kit_base_link"
    first = static_transforms.get((parent, via))
    second = static_transforms.get((via, child))
    if first is None or second is None:
        return None
    return transform_matrix(first.translation, first.rotation_xyzw) @ transform_matrix(second.translation, second.rotation_xyzw)


def image_metrics(jpeg_bytes: bytes) -> dict[str, Any]:
    if Image is None:
        return {"width": None, "height": None, "quality_status": "not_evaluated_pillow_missing"}
    with Image.open(io.BytesIO(jpeg_bytes)) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        if max(width, height) > 960:
            scale = 960.0 / max(width, height)
            rgb = rgb.resize((int(width * scale), int(height * scale)))
        gray = np.asarray(rgb.convert("L"), dtype=np.float32)
    center = gray[1:-1, 1:-1]
    laplacian = (
        gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
        - 4.0 * center
    )
    sharpness = float(np.var(laplacian))
    brightness = float(np.mean(gray))
    status = "sample_ok"
    if sharpness < 25.0:
        status = "likely_blurry"
    elif brightness < 35.0 or brightness > 220.0:
        status = "exposure_risk"
    return {
        "width": width,
        "height": height,
        "brightness_mean": round(brightness, 3),
        "laplacian_variance": round(sharpness, 3),
        "quality_status": status,
    }


def object_box_corners(obj: dict[str, Any]) -> np.ndarray | None:
    if obj.get("x") is None or obj.get("y") is None or obj.get("z") is None:
        return None
    dims = obj.get("dimensions") or {}
    length = float(dims.get("x") or 1.0)
    width = float(dims.get("y") or 1.0)
    height = float(dims.get("z") or 1.5)
    center = np.array([float(obj["x"]), float(obj["y"]), float(obj["z"])], dtype=float)
    yaw = float(obj.get("yaw_rad") or 0.0)
    c = math.cos(yaw)
    s = math.sin(yaw)
    rot = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=float)
    local = []
    for dx in (-length / 2.0, length / 2.0):
        for dy in (-width / 2.0, width / 2.0):
            for dz in (-height / 2.0, height / 2.0):
                local.append([dx, dy, dz])
    return center + np.asarray(local, dtype=float) @ rot.T


def project_object_box(
    obj: dict[str, Any],
    keyframe: dict[str, Any],
    camera_info: dict[str, Any],
    base_to_camera: np.ndarray,
    max_distance_m: float,
    inflate_px: int,
) -> dict[str, Any] | None:
    if not obj.get("dynamic_mask_candidate", True):
        return None
    distance = obj.get("distance_to_ego_m")
    if distance is not None and float(distance) > max_distance_m:
        return None
    corners = object_box_corners(obj)
    if corners is None:
        return None
    map_to_camera = map_to_base_matrix(keyframe) @ base_to_camera
    camera_to_map = np.linalg.inv(map_to_camera)
    homogeneous = np.concatenate([corners, np.ones((corners.shape[0], 1), dtype=float)], axis=1)
    camera_points = (camera_to_map @ homogeneous.T).T[:, :3]
    front = camera_points[:, 2] > 0.2
    if int(np.count_nonzero(front)) < 2:
        return None
    points = camera_points[front]
    k = camera_info["k"]
    fx, fy = float(k[0]), float(k[4])
    cx, cy = float(k[2]), float(k[5])
    u = fx * (points[:, 0] / points[:, 2]) + cx
    v = fy * (points[:, 1] / points[:, 2]) + cy
    width = int(camera_info["width"])
    height = int(camera_info["height"])
    x0 = max(0, int(math.floor(float(np.min(u)))) - inflate_px)
    y0 = max(0, int(math.floor(float(np.min(v)))) - inflate_px)
    x1 = min(width - 1, int(math.ceil(float(np.max(u)))) + inflate_px)
    y1 = min(height - 1, int(math.ceil(float(np.max(v)))) + inflate_px)
    if x1 <= 0 or y1 <= 0 or x0 >= width - 1 or y0 >= height - 1 or x1 <= x0 or y1 <= y0:
        return None
    return {
        "object_id": obj.get("object_id"),
        "class_name": obj.get("class_name"),
        "distance_to_ego_m": distance,
        "bbox_xyxy": [x0, y0, x1, y1],
    }


def context_summary(keyframe: dict[str, Any]) -> dict[str, Any]:
    nearest_distance = None
    class_counts: Counter[str] = Counter()
    object_count = 0
    dynamic_count = 0
    moving_count = 0
    nearest_objects = []
    for ctx in (keyframe.get("object_context") or {}).values():
        if ctx is None:
            continue
        object_count += int(ctx.get("object_count") or 0)
        dynamic_count += int(ctx.get("dynamic_mask_candidate_count") or 0)
        moving_count += int(ctx.get("moving_candidate_count") or 0)
        for name, count in (ctx.get("class_counts") or {}).items():
            class_counts[str(name)] += int(count)
        for obj in ctx.get("nearest_objects") or []:
            nearest_objects.append(obj)
            distance = obj.get("distance_to_ego_m")
            if distance is not None:
                nearest_distance = float(distance) if nearest_distance is None else min(nearest_distance, float(distance))
    nearest_objects.sort(key=lambda row: row.get("distance_to_ego_m") if row.get("distance_to_ego_m") is not None else 1e9)
    return {
        "object_count": object_count,
        "dynamic_mask_candidate_count": dynamic_count,
        "moving_candidate_count": moving_count,
        "nearest_distance_m": round(nearest_distance, 3) if nearest_distance is not None else None,
        "class_counts": dict(sorted(class_counts.items())),
        "nearest_objects": nearest_objects,
    }


def build_projection_masks(
    extracted: dict[str, dict[str, Any]],
    keyframes_by_id: dict[str, dict[str, Any]],
    calibration: dict[str, dict[str, Any]],
    static_transforms: dict[tuple[str, str], StaticTransform],
    output_dir: Path,
    max_distance_m: float,
    inflate_px: int,
) -> dict[str, Any]:
    mask_root = output_dir / "masks"
    overlay_root = output_dir / "mask_overlays"
    jobs_path = output_dir / "mask_jobs.jsonl"
    mask_root.mkdir(parents=True, exist_ok=True)
    overlay_root.mkdir(parents=True, exist_ok=True)
    job_count = 0
    projected_box_count = 0
    camera_projection_status: dict[str, str] = {}
    with jobs_path.open("w", encoding="utf-8") as jobs:
        for key, record in sorted(extracted.items()):
            keyframe = keyframes_by_id[record["keyframe_id"]]
            topic = record["topic"]
            safe_topic = safe_topic_name(topic)
            camera_info = calibration.get(topic)
            mask_path = mask_root / safe_topic / f"{record['keyframe_id']}.png"
            overlay_path = overlay_root / safe_topic / f"{record['keyframe_id']}.jpg"
            mask_path.parent.mkdir(parents=True, exist_ok=True)
            overlay_path.parent.mkdir(parents=True, exist_ok=True)
            boxes = []
            status = "missing_camera_info"
            if camera_info is not None:
                base_to_camera = static_chain_matrix(static_transforms, "base_link", camera_info["frame_id"])
                if base_to_camera is None:
                    status = "missing_base_to_camera_tf"
                else:
                    status = "projected"
                    for obj in context_summary(keyframe)["nearest_objects"]:
                        projected = project_object_box(
                            obj=obj,
                            keyframe=keyframe,
                            camera_info=camera_info,
                            base_to_camera=base_to_camera,
                            max_distance_m=max_distance_m,
                            inflate_px=inflate_px,
                        )
                        if projected is not None:
                            boxes.append(projected)
            camera_projection_status[topic] = status
            if Image is not None and ImageDraw is not None and camera_info is not None:
                mask = Image.new("L", (int(camera_info["width"]), int(camera_info["height"])), 0)
                draw = ImageDraw.Draw(mask)
                for box in boxes:
                    draw.rectangle(box["bbox_xyxy"], fill=255)
                mask.save(mask_path)
                if boxes:
                    with Image.open(record["image_path"]) as image:
                        overlay = image.convert("RGB")
                    draw_overlay = ImageDraw.Draw(overlay)
                    for box in boxes:
                        draw_overlay.rectangle(box["bbox_xyxy"], outline=(255, 0, 0), width=4)
                    overlay.save(overlay_path, quality=88)
                else:
                    overlay_path = None
            else:
                mask_path = None
                overlay_path = None
            projected_box_count += len(boxes)
            job = {
                "image_id": record["image_id"],
                "keyframe_id": record["keyframe_id"],
                "topic": topic,
                "image_path": record["image_path"],
                "mask_path": str(mask_path) if mask_path else None,
                "overlay_path": str(overlay_path) if overlay_path else None,
                "projection_status": status,
                "projected_box_count": len(boxes),
                "projected_boxes": boxes,
                "dynamic_context": context_summary(keyframe),
            }
            jobs.write(json.dumps(job, ensure_ascii=False, sort_keys=True) + "\n")
            job_count += 1
    return {
        "mask_jobs_jsonl": str(jobs_path),
        "mask_root": str(mask_root),
        "mask_overlay_root": str(overlay_root),
        "mask_job_count": job_count,
        "projected_box_count": projected_box_count,
        "camera_projection_status": camera_projection_status,
        "projection_note": "Coarse masks are generated from tracking-object 3D boxes and camera calibration. Review overlays before using them as final 3DGS masks.",
    }


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fields = [
        "image_id",
        "keyframe_id",
        "topic",
        "image_path",
        "mask_path",
        "time_ns",
        "image_time_ns",
        "dt_sec",
        "x",
        "y",
        "z",
        "yaw_rad",
        "nearest_dynamic_distance_m",
        "dynamic_mask_candidate_count",
        "laplacian_variance",
        "brightness_mean",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})


def write_markdown_report(manifest: dict[str, Any], path: Path) -> None:
    lines = [
        "# Qiyu Reconstruction Keyframe Image Pack",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- source_bag: `{manifest['source_bag']}`",
        f"- output_dir: `{manifest['output_dir']}`",
        f"- keyframes_requested: `{manifest['keyframe_count']}`",
        f"- images_extracted: `{manifest['image_count']}`",
        f"- missing_images: `{manifest['missing_image_count']}`",
        f"- mask_jobs: `{manifest['masking']['mask_job_count']}`",
        f"- projected_boxes: `{manifest['masking']['projected_box_count']}`",
        "",
        "## Camera Topics",
        "",
    ]
    for topic, summary in manifest["camera_topics"].items():
        lines.append(
            f"- `{topic}`: images={summary['image_count']}, missing={summary['missing_count']}, "
            f"projection=`{manifest['masking']['camera_projection_status'].get(topic, 'unknown')}`"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "- Current CARLA 0.9.15 import lane remains `mesh + OpenDRIVE`; these images and masks are for the NVIDIA Gaussian/NuRec visual lane.",
            "- The generated masks are coarse 3D tracking-box projections. They are suitable as a first dynamic-obstacle suppression pass, but overlay review is required before a long training run.",
            "- If the overlays show systematic offset, use the saved camera calibration and tf_static evidence to fix extrinsics before training.",
            "",
            "## Outputs",
            "",
        ]
    )
    for key, value in manifest["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    bag_dir = args.bag_dir.resolve()
    metadata_path = bag_dir / "metadata.yaml"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.yaml not found under {bag_dir}")
    output_dir = args.output_dir.resolve()
    image_root = output_dir / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    image_root.mkdir(parents=True, exist_ok=True)

    metadata = load_metadata(metadata_path)
    image_topics = args.topic or compressed_image_topics(metadata)
    if not image_topics:
        raise RuntimeError("no compressed image topics selected")
    keyframes = load_keyframes(args.keyframe_index.resolve(), args.keyframe_stride, args.max_keyframes)
    if not keyframes:
        raise RuntimeError("no keyframes selected")
    keyframe_times = [int(row["time_ns"]) for row in keyframes]
    keyframes_by_id = {row["keyframe_id"]: row for row in keyframes}
    tolerance_ns = int(args.image_tolerance_sec * 1_000_000_000)

    calibration, static_transforms = read_calibration(bag_dir, image_topics)
    extracted: dict[str, dict[str, Any]] = {}
    decoder_factory = DecoderFactory()
    decoder_cache: dict[tuple[str, int | None], Any] = {}

    for mcap_path in sorted(bag_dir.glob("*.mcap")):
        with mcap_path.open("rb") as stream:
            reader = make_reader(stream)
            for schema, channel, message in reader.iter_messages(topics=image_topics, log_time_order=True):
                idx = nearest_keyframe_index(keyframe_times, int(message.log_time), tolerance_ns)
                if idx is None:
                    continue
                keyframe = keyframes[idx]
                topic = channel.topic
                key = f"{keyframe['keyframe_id']}::{topic}"
                dt_sec = (int(message.log_time) - int(keyframe["time_ns"])) / 1_000_000_000.0
                previous = extracted.get(key)
                if previous is not None and abs(previous["dt_sec"]) <= abs(dt_sec):
                    continue
                cache_key = (channel.message_encoding, channel.schema_id)
                decoder = decoder_cache.get(cache_key)
                if decoder is None:
                    decoder = decoder_factory.decoder_for(channel.message_encoding, schema)
                    decoder_cache[cache_key] = decoder
                if decoder is None:
                    continue
                decoded = decoder(message.data)
                jpeg_bytes = bytes(decoded.data)
                safe_topic = safe_topic_name(topic)
                image_dir = image_root / safe_topic
                image_dir.mkdir(parents=True, exist_ok=True)
                image_path = image_dir / f"{keyframe['keyframe_id']}.jpg"
                image_path.write_bytes(jpeg_bytes)
                metrics = image_metrics(jpeg_bytes)
                summary = context_summary(keyframe)
                extracted[key] = {
                    "image_id": f"{keyframe['keyframe_id']}__{safe_topic}",
                    "keyframe_id": keyframe["keyframe_id"],
                    "topic": topic,
                    "image_path": str(image_path),
                    "time_ns": int(keyframe["time_ns"]),
                    "image_time_ns": int(message.log_time),
                    "message_stamp_ns": ros_stamp_ns(decoded),
                    "dt_sec": round(dt_sec, 6),
                    "x": keyframe["x"],
                    "y": keyframe["y"],
                    "z": keyframe["z"],
                    "yaw_rad": keyframe["yaw_rad"],
                    "nearest_dynamic_distance_m": summary["nearest_distance_m"],
                    "dynamic_mask_candidate_count": summary["dynamic_mask_candidate_count"],
                    "moving_candidate_count": summary["moving_candidate_count"],
                    "class_counts": summary["class_counts"],
                    "laplacian_variance": metrics.get("laplacian_variance"),
                    "brightness_mean": metrics.get("brightness_mean"),
                    "image_metrics": metrics,
                }

    masking = build_projection_masks(
        extracted=extracted,
        keyframes_by_id=keyframes_by_id,
        calibration=calibration,
        static_transforms=static_transforms,
        output_dir=output_dir,
        max_distance_m=args.mask_max_distance_m,
        inflate_px=args.mask_inflate_px,
    )
    for record in extracted.values():
        safe_topic = safe_topic_name(record["topic"])
        mask_path = output_dir / "masks" / safe_topic / f"{record['keyframe_id']}.png"
        record["mask_path"] = str(mask_path) if mask_path.exists() else None

    records = sorted(extracted.values(), key=lambda row: (row["time_ns"], row["topic"]))
    expected_count = len(keyframes) * len(image_topics)
    topic_summaries = {}
    for topic in image_topics:
        topic_records = [row for row in records if row["topic"] == topic]
        topic_summaries[topic] = {
            "image_count": len(topic_records),
            "missing_count": len(keyframes) - len(topic_records),
            "camera_info": calibration.get(topic),
        }

    outputs = {
        "image_root": str(image_root),
        "frame_index_json": str(output_dir / "keyframe_image_index.json"),
        "frame_index_csv": str(output_dir / "keyframe_image_index.csv"),
        "mask_jobs_jsonl": masking["mask_jobs_jsonl"],
        "mask_root": masking["mask_root"],
        "mask_overlay_root": masking["mask_overlay_root"],
        "manifest_json": str(output_dir / "reconstruction_image_pack_manifest.json"),
        "report_md": str(output_dir / "reconstruction_image_pack_report.md"),
    }
    manifest = {
        "generated_at": utc_now(),
        "source_bag": str(bag_dir),
        "source_keyframe_index": str(args.keyframe_index.resolve()),
        "output_dir": str(output_dir),
        "keyframe_count": len(keyframes),
        "camera_topic_count": len(image_topics),
        "expected_image_count": expected_count,
        "image_count": len(records),
        "missing_image_count": expected_count - len(records),
        "image_tolerance_sec": args.image_tolerance_sec,
        "keyframe_stride": args.keyframe_stride,
        "camera_topics": topic_summaries,
        "static_transform_count": len(static_transforms),
        "masking": masking,
        "carla_import_lane": {
            "stable_target": "mesh_plus_opendrive_for_carla0915",
            "gaussian_target": "nvidia_visual_reconstruction_or_nurec_research",
            "note": "Do not treat Gaussian splats as directly importable CARLA 0.9.15 map assets.",
        },
        "outputs": outputs,
    }

    Path(outputs["frame_index_json"]).write_text(json.dumps({"frames": records}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(Path(outputs["frame_index_csv"]), records)
    Path(outputs["manifest_json"]).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown_report(manifest, Path(outputs["report_md"]))
    print(
        json.dumps(
            {
                "manifest": outputs["manifest_json"],
                "report": outputs["report_md"],
                "keyframes": len(keyframes),
                "images": len(records),
                "missing_images": expected_count - len(records),
                "mask_jobs": masking["mask_job_count"],
                "projected_boxes": masking["projected_box_count"],
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract reconstruction keyframe images and coarse dynamic-obstacle masks.")
    parser.add_argument("--bag-dir", type=Path, required=True, help="rosbag2 directory containing metadata.yaml and .mcap files")
    parser.add_argument("--keyframe-index", type=Path, required=True, help="keyframes.json from build_reconstruction_keyframe_index.py")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output image-pack directory")
    parser.add_argument("--topic", action="append", help="CompressedImage topic to extract. Defaults to all compressed image topics.")
    parser.add_argument("--image-tolerance-sec", type=float, default=0.25, help="Nearest image tolerance for each keyframe")
    parser.add_argument("--keyframe-stride", type=int, default=1, help="Extract every Nth keyframe")
    parser.add_argument("--max-keyframes", type=int, default=0, help="Optional cap on keyframes after stride. 0 means no cap.")
    parser.add_argument("--mask-max-distance-m", type=float, default=45.0, help="Do not project dynamic objects beyond this ego distance")
    parser.add_argument("--mask-inflate-px", type=int, default=24, help="Pixel inflation applied to projected dynamic boxes")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
