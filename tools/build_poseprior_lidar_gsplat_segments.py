from __future__ import annotations

import argparse
import bisect
import json
import math
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory
from PIL import Image


CAMERA_TOPICS = {
    "front_3mm": "/electronic_rearview_mirror/front_3mm/camera_image_jpeg",
    "front_left": "/electronic_rearview_mirror/front_left/camera_image_jpeg",
    "front_right": "/electronic_rearview_mirror/front_right/camera_image_jpeg",
    "rear_3mm": "/electronic_rearview_mirror/rear_3mm/camera_image_jpeg",
    "rear_left": "/electronic_rearview_mirror/rear_left/camera_image_jpeg",
    "rear_right": "/electronic_rearview_mirror/rear_right/camera_image_jpeg",
}
TOPIC_TO_CAMERA = {topic: camera for camera, topic in CAMERA_TOPICS.items()}

# The existing artifact-side gsplat runner has this historical camera frame map.
# Keep the remap here so the current 82 capture can reuse that runner unchanged.
LEGACY_FRAME_BY_CAMERA = {
    "front_3mm": "camera0/camera_link",
    "rear_3mm": "camera1/camera_link",
    "front_left": "camera2/camera_link",
    "front_right": "camera3/camera_link",
    "rear_left": "camera4/camera_link",
    "rear_right": "camera5/camera_link",
}

POINTCLOUD_DTYPE = np.dtype(
    [
        ("x", "<f4"),
        ("y", "<f4"),
        ("z", "<f4"),
        ("intensity", "u1"),
        ("return_type", "u1"),
        ("channel", "<u2"),
    ]
)

MCAP_INDEX_RE = re.compile(r"rosbag2_(\d+)\.mcap$")


@dataclass(frozen=True)
class SegmentSpec:
    segment_id: str
    start_distance_m: float
    end_distance_m: float
    keyframes: list[dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_topic_name(topic: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", topic.strip("/")) or "topic"


def yaw_to_quat(yaw: float) -> tuple[float, float, float, float]:
    return 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0)


def quat_to_matrix(q: tuple[float, float, float, float]) -> np.ndarray:
    x, y, z, w = q
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm == 0:
        return np.eye(3, dtype=np.float64)
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def quat_to_rpy(q: tuple[float, float, float, float]) -> tuple[float, float, float]:
    x, y, z, w = q
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    sinp = 2 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return roll, pitch, yaw


def tf_spec(tf: Any) -> dict[str, float]:
    q = (
        float(tf.transform.rotation.x),
        float(tf.transform.rotation.y),
        float(tf.transform.rotation.z),
        float(tf.transform.rotation.w),
    )
    roll, pitch, yaw = quat_to_rpy(q)
    return {
        "x": float(tf.transform.translation.x),
        "y": float(tf.transform.translation.y),
        "z": float(tf.transform.translation.z),
        "roll": roll,
        "pitch": pitch,
        "yaw": yaw,
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resize_image(src: Path, dst: Path, max_px: int, is_mask: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as image:
        image = image.convert("L" if is_mask else "RGB")
        width, height = image.size
        scale = max_px / float(max(width, height))
        if scale < 1.0:
            resampling = Image.Resampling.NEAREST if is_mask else Image.Resampling.LANCZOS
            image = image.resize((int(round(width * scale)), int(round(height * scale))), resampling)
        if is_mask:
            image.save(dst)
        else:
            image.save(dst, quality=92)


def sorted_mcap_paths(bag_dir: Path) -> list[Path]:
    """Return rosbag2 split files in numeric order instead of lexical order."""
    return sorted(
        bag_dir.glob("*.mcap"),
        key=lambda path: (
            int(match.group(1)) if (match := MCAP_INDEX_RE.match(path.name)) else math.inf,
            path.name,
        ),
    )


def read_static_transforms(bag_dir: Path) -> dict[str, Any]:
    static_by_child: dict[str, Any] = {}
    decoder_factory = DecoderFactory()
    for mcap_path in sorted_mcap_paths(bag_dir):
        with mcap_path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[decoder_factory])
            for _, _, _, decoded in reader.iter_decoded_messages(topics=["/tf_static"], log_time_order=True):
                for tf in decoded.transforms:
                    static_by_child[str(tf.child_frame_id)] = tf
        if "sensor_kit_base_link" in static_by_child and sum(k.startswith("camera") for k in static_by_child) >= 6:
            break
    return static_by_child


def build_pose_prior(
    *,
    source_bag: Path,
    image_pack_manifest: dict[str, Any],
    static_by_child: dict[str, Any],
) -> dict[str, Any]:
    base_sensor_tf = static_by_child.get("sensor_kit_base_link")
    if base_sensor_tf is None:
        raise RuntimeError("missing base_link -> sensor_kit_base_link static transform")

    actual_frame_by_camera: dict[str, str] = {}
    for topic, summary in image_pack_manifest["camera_topics"].items():
        camera = TOPIC_TO_CAMERA.get(topic)
        info = summary.get("camera_info")
        if camera and info:
            actual_frame_by_camera[camera] = str(info["frame_id"])

    extrinsics = {
        "current_82_remapped_for_existing_runner": {
            "base_link": {"sensor_kit_base_link": tf_spec(base_sensor_tf)},
            "sensor_kit_base_link": {},
        }
    }
    camera_info = []
    for topic, summary in sorted(image_pack_manifest["camera_topics"].items()):
        camera = TOPIC_TO_CAMERA.get(topic)
        info = summary.get("camera_info")
        if camera is None or info is None:
            continue
        actual_frame = actual_frame_by_camera[camera]
        tf = static_by_child.get(actual_frame)
        if tf is None:
            raise RuntimeError(f"missing static transform for {camera}: {actual_frame}")
        legacy_frame = LEGACY_FRAME_BY_CAMERA[camera]
        item = dict(info)
        item["camera"] = camera
        item["actual_frame_id"] = actual_frame
        item["frame_id"] = legacy_frame
        camera_info.append(item)
        extrinsics["current_82_remapped_for_existing_runner"]["sensor_kit_base_link"][legacy_frame] = tf_spec(tf)

    return {
        "generated_at": utc_now(),
        "source_bag": str(source_bag),
        "compatibility_note": (
            "Current 82 camera frame ids are remapped to the legacy frame ids expected by "
            "run_masked_lidar_gsplat_smoke.py; actual_frame_id records the source frame."
        ),
        "camera_info": camera_info,
        "extrinsics": extrinsics,
    }


def make_segments(
    keyframes: list[dict[str, Any]],
    segment_length_m: float,
    start_distance_m: float,
    end_distance_m: float | None,
    max_segments: int,
    prefix: str,
) -> list[SegmentSpec]:
    route_end = float(keyframes[-1]["cumulative_distance_m"])
    stop = min(route_end, end_distance_m if end_distance_m is not None else route_end)
    segments: list[SegmentSpec] = []
    start = start_distance_m
    while start < stop:
        end = min(start + segment_length_m, stop)
        selected = [
            row
            for row in keyframes
            if start <= float(row["cumulative_distance_m"]) < end
        ]
        if selected:
            index = int(round(start / segment_length_m))
            segments.append(SegmentSpec(f"{prefix}_{index:03d}_{int(start):04d}m_{int(end):04d}m", start, end, selected))
        if max_segments > 0 and len(segments) >= max_segments:
            break
        start = end
    return segments


def load_odom(bag_dir: Path, odom_topic: str) -> list[tuple[int, np.ndarray, tuple[float, float, float, float]]]:
    rows: list[tuple[int, np.ndarray, tuple[float, float, float, float]]] = []
    decoder_factory = DecoderFactory()
    for mcap_path in sorted_mcap_paths(bag_dir):
        with mcap_path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[decoder_factory])
            for _, _, message, decoded in reader.iter_decoded_messages(topics=[odom_topic], log_time_order=True):
                position = decoded.pose.pose.position
                orientation = decoded.pose.pose.orientation
                rows.append(
                    (
                        int(message.log_time),
                        np.array([float(position.x), float(position.y), float(position.z)], dtype=np.float64),
                        (
                            float(orientation.x),
                            float(orientation.y),
                            float(orientation.z),
                            float(orientation.w),
                        ),
                    )
                )
    rows.sort(key=lambda row: row[0])
    return rows


def load_external_odom_csv(path: Path) -> list[tuple[int, np.ndarray, tuple[float, float, float, float]]]:
    rows: list[tuple[int, np.ndarray, tuple[float, float, float, float]]] = []
    with path.open("r", encoding="utf-8") as fh:
        header = [item.strip() for item in fh.readline().strip().lstrip("#").split(",")]
        if not header:
            return rows
        indexes = {name: index for index, name in enumerate(header)}

        def value(parts: list[str], *names: str) -> float:
            for name in names:
                if name in indexes:
                    return float(parts[indexes[name]])
            raise KeyError(f"{path}: missing one of {names}")

        for raw in fh:
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            parts = [item.strip() for item in raw.split(",")]
            if "timestamp_ns" in indexes:
                stamp_ns = int(float(parts[indexes["timestamp_ns"]]))
            else:
                stamp_ns = int(value(parts, "timestamp", "time_sec") * 1e9)
            position = np.array(
                [
                    value(parts, "tx", "x"),
                    value(parts, "ty", "y"),
                    value(parts, "tz", "z"),
                ],
                dtype=np.float64,
            )
            quaternion = (
                value(parts, "qx"),
                value(parts, "qy"),
                value(parts, "qz"),
                value(parts, "qw"),
            )
            rows.append((stamp_ns, position, quaternion))
    rows.sort(key=lambda row: row[0])
    return rows


def nearest_odom(
    rows: list[tuple[int, np.ndarray, tuple[float, float, float, float]]],
    times: list[int],
    stamp_ns: int,
    tolerance_ns: int,
) -> tuple[int, np.ndarray, tuple[float, float, float, float]] | None:
    index = bisect.bisect_left(times, stamp_ns)
    candidates = []
    if index < len(rows):
        candidates.append(rows[index])
    if index > 0:
        candidates.append(rows[index - 1])
    if not candidates:
        return None
    best = min(candidates, key=lambda row: abs(row[0] - stamp_ns))
    return best if abs(best[0] - stamp_ns) <= tolerance_ns else None


def pointcloud_points(decoded: Any) -> np.ndarray:
    count = int(decoded.width) * int(decoded.height)
    arr = np.frombuffer(decoded.data, dtype=POINTCLOUD_DTYPE, count=count)
    return np.column_stack([arr["x"], arr["y"], arr["z"]]).astype(np.float32), arr["intensity"].astype(np.uint8)


def build_lidar_seed(
    *,
    bag_dir: Path,
    lidar_topic: str,
    odom_rows: list[tuple[int, np.ndarray, tuple[float, float, float, float]]],
    output_ply: Path,
    time_min_ns: int,
    time_max_ns: int,
    sample_period_ns: int,
    points_per_frame: int,
    max_points: int,
    odom_tolerance_ns: int,
    min_range_m: float,
    max_range_m: float,
    z_min_m: float,
    z_max_m: float,
    seed: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    odom_times = [row[0] for row in odom_rows]
    points_by_frame: list[np.ndarray] = []
    colors_by_frame: list[np.ndarray] = []
    frame_count = 0
    last_stamp: int | None = None
    decoder_factory = DecoderFactory()
    for mcap_path in sorted_mcap_paths(bag_dir):
        with mcap_path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[decoder_factory])
            for _, _, message, decoded in reader.iter_decoded_messages(topics=[lidar_topic], log_time_order=True):
                stamp = int(message.log_time)
                if stamp < time_min_ns:
                    continue
                if stamp > time_max_ns:
                    break
                if last_stamp is not None and stamp - last_stamp < sample_period_ns:
                    continue
                odom = nearest_odom(odom_rows, odom_times, stamp, odom_tolerance_ns)
                if odom is None:
                    continue
                points, intensity = pointcloud_points(decoded)
                finite = np.isfinite(points).all(axis=1)
                ranges = np.linalg.norm(points[:, :2], axis=1)
                keep = (
                    finite
                    & (np.abs(points[:, 0]) < 1e4)
                    & (np.abs(points[:, 1]) < 1e4)
                    & (np.abs(points[:, 2]) < 1e4)
                    & (ranges > min_range_m)
                    & (ranges < max_range_m)
                    & (points[:, 2] > z_min_m)
                    & (points[:, 2] < z_max_m)
                )
                indices = np.flatnonzero(keep)
                if len(indices) == 0:
                    continue
                if len(indices) > points_per_frame:
                    indices = rng.choice(indices, size=points_per_frame, replace=False)
                local_points = points[indices].astype(np.float64)
                _, translation, quaternion = odom
                rotation = quat_to_matrix(quaternion)
                local_intensity = intensity[indices]
                with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                    map_points = (rotation @ local_points.T).T + translation[None, :]
                transformed_finite = (
                    np.isfinite(map_points).all(axis=1)
                    & (np.abs(map_points[:, 0]) < 1e6)
                    & (np.abs(map_points[:, 1]) < 1e6)
                    & (np.abs(map_points[:, 2]) < 1e6)
                )
                if not np.any(transformed_finite):
                    continue
                map_points = map_points[transformed_finite]
                local_points = local_points[transformed_finite]
                local_intensity = local_intensity[transformed_finite]
                red = np.clip(local_intensity.astype(np.int16) + 20, 0, 255).astype(np.uint8)
                green = local_intensity
                blue = np.clip(220 - np.clip((local_points[:, 2] + 2.0) * 25.0, 0, 180), 0, 255).astype(np.uint8)
                points_by_frame.append(map_points.astype(np.float32))
                colors_by_frame.append(np.column_stack([red, green, blue]).astype(np.uint8))
                frame_count += 1
                last_stamp = stamp

    if not points_by_frame:
        raise RuntimeError(f"no lidar points selected for {time_min_ns}..{time_max_ns}")
    points = np.concatenate(points_by_frame, axis=0)
    colors = np.concatenate(colors_by_frame, axis=0)
    if len(points) > max_points:
        indices = rng.choice(len(points), size=max_points, replace=False)
        points = points[indices]
        colors = colors[indices]

    output_ply.parent.mkdir(parents=True, exist_ok=True)
    with output_ply.open("w", encoding="ascii") as fh:
        fh.write("ply\nformat ascii 1.0\n")
        fh.write(f"element vertex {len(points)}\n")
        fh.write("property float x\nproperty float y\nproperty float z\n")
        fh.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
        fh.write("end_header\n")
        for (x, y, z), (red, green, blue) in zip(points, colors):
            fh.write(f"{x:.4f} {y:.4f} {z:.4f} {int(red)} {int(green)} {int(blue)}\n")

    return {
        "lidar_frame_count": frame_count,
        "lidar_point_count": int(len(points)),
        "time_min_ns": int(time_min_ns),
        "time_max_ns": int(time_max_ns),
        "ply": str(output_ply),
    }


def build_segment(
    *,
    spec: SegmentSpec,
    bag_dir: Path,
    output_dir: Path,
    image_records: list[dict[str, Any]],
    keyframes_by_id: dict[str, dict[str, Any]],
    pose_prior: dict[str, Any],
    odom_rows: list[tuple[int, np.ndarray, tuple[float, float, float, float]]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    segment_dir = output_dir / "segments" / spec.segment_id
    if segment_dir.exists() and args.force:
        shutil.rmtree(segment_dir)
    if segment_dir.exists() and not args.force:
        raise FileExistsError(f"{segment_dir} exists; pass --force to replace it")
    (segment_dir / "images_colmap_960").mkdir(parents=True)
    (segment_dir / "dynamic_masks_960").mkdir(parents=True)
    (segment_dir / "lidar_seed").mkdir(parents=True)

    selected_ids = {row["keyframe_id"] for row in spec.keyframes[:: args.keyframe_stride]}
    records = [
        row
        for row in image_records
        if row["keyframe_id"] in selected_ids and TOPIC_TO_CAMERA.get(row["topic"]) in args.cameras
    ]
    records.sort(key=lambda row: (int(row["time_ns"]), TOPIC_TO_CAMERA[row["topic"]]))
    if not records:
        raise RuntimeError(f"{spec.segment_id}: no image records selected")

    poses = []
    for record in records:
        camera = TOPIC_TO_CAMERA[record["topic"]]
        image_rel = f"{camera}/{record['keyframe_id']}.jpg"
        mask_rel = f"{camera}/{record['keyframe_id']}.png"
        resize_image(Path(record["image_path"]), segment_dir / "images_colmap_960" / image_rel, args.resize_max_px, False)
        resize_image(Path(record["mask_path"]), segment_dir / "dynamic_masks_960" / mask_rel, args.resize_max_px, True)
        keyframe = keyframes_by_id[record["keyframe_id"]]
        qx, qy, qz, qw = yaw_to_quat(float(keyframe["yaw_rad"]))
        poses.append(
            {
                "image": image_rel,
                "topic": record["topic"],
                "camera": camera,
                "timestamp_ns": int(record["image_time_ns"]),
                "nearest_base_link_pose": {
                    "t": int(keyframe["time_ns"]),
                    "frame_id": "base_link",
                    "points": None,
                    "x": float(keyframe["x"]),
                    "y": float(keyframe["y"]),
                    "z": float(keyframe["z"]),
                    "qx": qx,
                    "qy": qy,
                    "qz": qz,
                    "qw": qw,
                    "delta_s": round((int(record["image_time_ns"]) - int(keyframe["time_ns"])) / 1e9, 6),
                },
                "inside_segment_time_window": True,
            }
        )

    time_min_ns = min(int(row["timestamp_ns"]) for row in poses) - int(args.lidar_time_margin_sec * 1e9)
    time_max_ns = max(int(row["timestamp_ns"]) for row in poses) + int(args.lidar_time_margin_sec * 1e9)
    lidar_ply = segment_dir / "lidar_seed" / f"{spec.segment_id}_current_pose_lidar_seed.ply"
    lidar_summary = build_lidar_seed(
        bag_dir=bag_dir,
        lidar_topic=args.lidar_topic,
        odom_rows=odom_rows,
        output_ply=lidar_ply,
        time_min_ns=time_min_ns,
        time_max_ns=time_max_ns,
        sample_period_ns=int(args.lidar_sample_period_sec * 1e9),
        points_per_frame=args.lidar_points_per_frame,
        max_points=args.max_lidar_points,
        odom_tolerance_ns=int(args.odom_tolerance_sec * 1e9),
        min_range_m=args.min_lidar_range_m,
        max_range_m=args.max_lidar_range_m,
        z_min_m=args.z_min_m,
        z_max_m=args.z_max_m,
        seed=args.seed + int(spec.start_distance_m),
    )

    camera_poses = {
        "generated_at": utc_now(),
        "segment_id": spec.segment_id,
        "status": "ready_pose_prior_lidar_seed_smoke",
        "source_bag": str(bag_dir),
        "frames_dir": str(segment_dir),
        "colmap_image_dir": str(segment_dir / "images_colmap_960"),
        "distance_window_m": [spec.start_distance_m, spec.end_distance_m],
        "time_window_ns": [min(p["timestamp_ns"] for p in poses), max(p["timestamp_ns"] for p in poses)],
        "selected_cameras": args.cameras,
        "image_count": len(poses),
        "poses": poses,
        "note": "Poses use /localization/kinematic_state keyframe yaw and position; this segment is for pose-prior LiDAR-seeded 3DGS smoke.",
    }
    (segment_dir / "camera_poses.json").write_text(json.dumps(camera_poses, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (segment_dir / "camera_pose_prior_inputs_compat.json").write_text(json.dumps(pose_prior, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    handoff = {
        "generated_at": utc_now(),
        "segment_id": spec.segment_id,
        "segment_dir": str(segment_dir),
        "camera_poses": str(segment_dir / "camera_poses.json"),
        "pose_prior_json": str(segment_dir / "camera_pose_prior_inputs_compat.json"),
        "map_ply": str(lidar_ply),
        "source_bag": str(bag_dir),
        "selected_cameras": args.cameras,
        "selected_keyframes": sorted(selected_ids),
        "distance_window_m": [spec.start_distance_m, spec.end_distance_m],
        "image_count": len(poses),
        **lidar_summary,
        "dynamic_obstacle_policy": "Use resized planning-object projected masks in dynamic_masks_960 to suppress dynamic pixels during static/background training.",
        "carla_import_boundary": "This is a pose-prior visual 3DGS segment. CARLA 0.9.15 drivable import remains mesh + OpenDRIVE + collision proxy.",
    }
    (segment_dir / "segment_handoff_manifest.json").write_text(json.dumps(handoff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return handoff


def run(args: argparse.Namespace) -> int:
    bag_dir = args.bag_dir.resolve()
    image_pack_dir = args.image_pack_dir.resolve()
    output_dir = args.output_dir.resolve()
    image_pack_manifest = read_json(image_pack_dir / "reconstruction_image_pack_manifest.json")
    image_records = read_json(image_pack_dir / "keyframe_image_index.json")["frames"]
    keyframes = read_json(args.keyframe_index.resolve())["keyframes"]
    keyframes_by_id = {row["keyframe_id"]: row for row in keyframes}
    args.cameras = args.camera or ["front_3mm", "front_left", "front_right"]

    static_by_child = read_static_transforms(bag_dir)
    pose_prior = build_pose_prior(
        source_bag=bag_dir,
        image_pack_manifest=image_pack_manifest,
        static_by_child=static_by_child,
    )
    odom_rows = (
        load_external_odom_csv(args.external_odom_csv.resolve())
        if args.external_odom_csv
        else load_odom(bag_dir, args.odom_topic)
    )
    if not odom_rows:
        source = str(args.external_odom_csv) if args.external_odom_csv else args.odom_topic
        raise RuntimeError(f"no odom rows found on {source}")

    segments = make_segments(
        keyframes=keyframes,
        segment_length_m=args.segment_length_m,
        start_distance_m=args.start_distance_m,
        end_distance_m=args.end_distance_m,
        max_segments=args.max_segments,
        prefix=args.segment_id_prefix,
    )
    if not segments:
        raise RuntimeError("no segments selected")

    output_dir.mkdir(parents=True, exist_ok=True)
    handoffs = [
        build_segment(
            spec=spec,
            bag_dir=bag_dir,
            output_dir=output_dir,
            image_records=image_records,
            keyframes_by_id=keyframes_by_id,
            pose_prior=pose_prior,
            odom_rows=odom_rows,
            args=args,
        )
        for spec in segments
    ]
    manifest = {
        "generated_at": utc_now(),
        "mode": "poseprior_lidar_gsplat_segment_batch",
        "source_bag": str(bag_dir),
        "image_pack_dir": str(image_pack_dir),
        "keyframe_index": str(args.keyframe_index.resolve()),
        "odom_source": str(args.external_odom_csv.resolve()) if args.external_odom_csv else args.odom_topic,
        "output_dir": str(output_dir),
        "segment_count": len(handoffs),
        "segment_length_m": args.segment_length_m,
        "resize_max_px": args.resize_max_px,
        "cameras": args.cameras,
        "segments": handoffs,
        "carla_import_boundary": "CARLA 0.9.15 import remains mesh + OpenDRIVE + collision proxy; these segments are NVIDIA visual 3DGS inputs.",
    }
    manifest_path = output_dir / "poseprior_lidar_gsplat_segments_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "segment_count": len(handoffs)}, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build pose-prior LiDAR-seeded 3DGS route segments from Qiyu reconstruction inputs.")
    parser.add_argument("--bag-dir", type=Path, required=True)
    parser.add_argument("--image-pack-dir", type=Path, required=True)
    parser.add_argument("--keyframe-index", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--segment-id-prefix", default="qiyu82_seg")
    parser.add_argument("--segment-length-m", type=float, default=250.0)
    parser.add_argument("--start-distance-m", type=float, default=0.0)
    parser.add_argument("--end-distance-m", type=float)
    parser.add_argument("--max-segments", type=int, default=0)
    parser.add_argument("--camera", action="append", choices=sorted(CAMERA_TOPICS), help="Semantic camera name; repeatable.")
    parser.add_argument("--keyframe-stride", type=int, default=2)
    parser.add_argument("--resize-max-px", type=int, default=480)
    parser.add_argument("--lidar-topic", default="/sensing/lidar/concatenated/pointcloud")
    parser.add_argument("--odom-topic", default="/localization/kinematic_state")
    parser.add_argument("--external-odom-csv", type=Path, help="Optional odom CSV with timestamp_ns or timestamp plus tx/ty/tz/qx/qy/qz/qw columns.")
    parser.add_argument("--lidar-time-margin-sec", type=float, default=2.0)
    parser.add_argument("--lidar-sample-period-sec", type=float, default=0.5)
    parser.add_argument("--lidar-points-per-frame", type=int, default=2500)
    parser.add_argument("--max-lidar-points", type=int, default=320000)
    parser.add_argument("--odom-tolerance-sec", type=float, default=0.25)
    parser.add_argument("--min-lidar-range-m", type=float, default=1.5)
    parser.add_argument("--max-lidar-range-m", type=float, default=90.0)
    parser.add_argument("--z-min-m", type=float, default=-4.0)
    parser.add_argument("--z-max-m", type=float, default=8.0)
    parser.add_argument("--seed", type=int, default=82)
    parser.add_argument("--force", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
