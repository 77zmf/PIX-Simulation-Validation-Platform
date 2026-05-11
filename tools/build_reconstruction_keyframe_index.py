from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory


COMPRESSED_IMAGE_TYPE = "sensor_msgs/msg/CompressedImage"
DEFAULT_LOCALIZATION_TOPIC = "/localization/kinematic_state"
DEFAULT_OBJECT_TOPICS = [
    "/perception/object_recognition/detection/bevfusion/objects",
    "/perception/object_recognition/tracking/objects",
    "/perception/object_recognition/objects",
]

CLASS_LABELS = {
    0: "UNKNOWN",
    1: "CAR",
    2: "TRUCK",
    3: "BUS",
    4: "TRAILER",
    5: "MOTORCYCLE",
    6: "BICYCLE",
    7: "PEDESTRIAN",
}


@dataclass(frozen=True)
class McapSpan:
    path: Path
    start_ns: int
    end_ns: int


@dataclass(frozen=True)
class PoseSample:
    time_ns: int
    stamp_ns: int | None
    x: float
    y: float
    z: float
    yaw_rad: float
    speed_mps: float
    cumulative_distance_m: float


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_metadata(metadata_path: Path) -> dict[str, Any]:
    with metadata_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def compressed_image_topics(metadata: dict[str, Any]) -> list[str]:
    topics = (
        metadata.get("rosbag2_bagfile_information", {})
        .get("topics_with_message_count", [])
    )
    selected: list[str] = []
    for item in topics:
        topic_metadata = item.get("topic_metadata", {})
        if topic_metadata.get("type") == COMPRESSED_IMAGE_TYPE:
            selected.append(str(topic_metadata.get("name")))
    return sorted(selected)


def mcap_spans(mcap_paths: list[Path]) -> list[McapSpan]:
    spans: list[McapSpan] = []
    for path in mcap_paths:
        with path.open("rb") as stream:
            summary = make_reader(stream).get_summary()
        if summary is None or summary.statistics is None:
            continue
        stats = summary.statistics
        spans.append(McapSpan(path=path, start_ns=int(stats.message_start_time), end_ns=int(stats.message_end_time)))
    return sorted(spans, key=lambda span: (span.start_ns, span.path.name))


def ros_stamp_ns(message: Any) -> int | None:
    header = getattr(message, "header", None)
    stamp = getattr(header, "stamp", None)
    if stamp is None:
        return None
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def yaw_from_quaternion(q: Any) -> float:
    x = float(getattr(q, "x", 0.0))
    y = float(getattr(q, "y", 0.0))
    z = float(getattr(q, "z", 0.0))
    w = float(getattr(q, "w", 1.0))
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def pose_from_odometry(log_time_ns: int, decoded: Any, previous: PoseSample | None) -> PoseSample:
    pose = decoded.pose.pose
    twist = decoded.twist.twist
    x = float(pose.position.x)
    y = float(pose.position.y)
    z = float(pose.position.z)
    speed = math.hypot(float(twist.linear.x), float(twist.linear.y))
    cumulative = previous.cumulative_distance_m if previous else 0.0
    if previous is not None:
        step = math.hypot(x - previous.x, y - previous.y)
        if step < 20.0:
            cumulative += step
    return PoseSample(
        time_ns=log_time_ns,
        stamp_ns=ros_stamp_ns(decoded),
        x=x,
        y=y,
        z=z,
        yaw_rad=yaw_from_quaternion(pose.orientation),
        speed_mps=speed,
        cumulative_distance_m=cumulative,
    )


def read_localization(spans: list[McapSpan], topic: str) -> list[PoseSample]:
    poses: list[PoseSample] = []
    previous: PoseSample | None = None
    for span in spans:
        with span.path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[DecoderFactory()])
            for _, _, message, decoded in reader.iter_decoded_messages(topics=[topic], log_time_order=True):
                sample = pose_from_odometry(int(message.log_time), decoded, previous)
                poses.append(sample)
                previous = sample
    return poses


def read_topic_timestamps(spans: list[McapSpan], topic: str) -> list[int]:
    timestamps: list[int] = []
    for span in spans:
        with span.path.open("rb") as stream:
            reader = make_reader(stream)
            for _, _, message in reader.iter_messages(topics=[topic], log_time_order=True):
                timestamps.append(int(message.log_time))
    return sorted(timestamps)


def nearest_timestamp(timestamps: list[int], target_ns: int, tolerance_ns: int) -> int | None:
    if not timestamps:
        return None
    index = bisect.bisect_left(timestamps, target_ns)
    candidates = []
    if index < len(timestamps):
        candidates.append(timestamps[index])
    if index > 0:
        candidates.append(timestamps[index - 1])
    if not candidates:
        return None
    best = min(candidates, key=lambda value: abs(value - target_ns))
    return best if abs(best - target_ns) <= tolerance_ns else None


def select_keyframes(
    poses: list[PoseSample],
    distance_step_m: float,
    min_time_step_sec: float,
    max_keyframes: int,
) -> list[PoseSample]:
    if not poses:
        return []
    selected = [poses[0]]
    next_distance = poses[0].cumulative_distance_m + distance_step_m
    min_time_ns = int(min_time_step_sec * 1_000_000_000)
    for pose in poses[1:]:
        if pose.cumulative_distance_m < next_distance:
            continue
        if pose.time_ns - selected[-1].time_ns < min_time_ns:
            continue
        selected.append(pose)
        next_distance = pose.cumulative_distance_m + distance_step_m
        if max_keyframes > 0 and len(selected) >= max_keyframes:
            break
    if selected[-1].time_ns != poses[-1].time_ns and (max_keyframes <= 0 or len(selected) < max_keyframes):
        selected.append(poses[-1])
    return selected


def primary_label(obj: Any) -> tuple[int | None, float | None, str]:
    classifications = getattr(obj, "classification", []) or []
    if not classifications:
        return None, None, "UNKNOWN"
    best = max(classifications, key=lambda item: float(getattr(item, "probability", 0.0)))
    label = int(getattr(best, "label", 0))
    probability = float(getattr(best, "probability", 0.0))
    return label, probability, CLASS_LABELS.get(label, f"LABEL_{label}")


def object_pose(obj: Any) -> tuple[float | None, float | None, float | None]:
    kin = getattr(obj, "kinematics", None)
    pose_with_covariance = None
    if kin is not None:
        pose_with_covariance = getattr(kin, "pose_with_covariance", None)
        if pose_with_covariance is None:
            pose_with_covariance = getattr(kin, "initial_pose_with_covariance", None)
    pose = getattr(pose_with_covariance, "pose", None)
    position = getattr(pose, "position", None)
    if position is None:
        return None, None, None
    return float(position.x), float(position.y), float(position.z)


def object_yaw(obj: Any) -> float | None:
    kin = getattr(obj, "kinematics", None)
    pose_with_covariance = None
    if kin is not None:
        pose_with_covariance = getattr(kin, "pose_with_covariance", None)
        if pose_with_covariance is None:
            pose_with_covariance = getattr(kin, "initial_pose_with_covariance", None)
    pose = getattr(pose_with_covariance, "pose", None)
    orientation = getattr(pose, "orientation", None)
    if orientation is None:
        return None
    return yaw_from_quaternion(orientation)


def object_speed(obj: Any) -> float | None:
    kin = getattr(obj, "kinematics", None)
    twist_with_covariance = None
    if kin is not None:
        twist_with_covariance = getattr(kin, "twist_with_covariance", None)
        if twist_with_covariance is None:
            twist_with_covariance = getattr(kin, "initial_twist_with_covariance", None)
    twist = getattr(twist_with_covariance, "twist", None)
    linear = getattr(twist, "linear", None)
    if linear is None:
        return None
    return math.hypot(float(linear.x), float(linear.y))


def object_dimensions(obj: Any) -> dict[str, float | None]:
    shape = getattr(obj, "shape", None)
    dims = getattr(shape, "dimensions", None)
    if dims is None:
        return {"x": None, "y": None, "z": None}
    return {"x": float(dims.x), "y": float(dims.y), "z": float(dims.z)}


def object_id(obj: Any) -> str | None:
    raw = getattr(obj, "object_id", None)
    uuid = getattr(raw, "uuid", None)
    if uuid is None:
        return None
    if isinstance(uuid, bytes):
        return uuid.hex()
    return str(uuid)


def summarize_object(obj: Any, ego_pose: PoseSample | None, topic: str, speed_threshold_mps: float) -> dict[str, Any]:
    label, class_prob, class_name = primary_label(obj)
    x, y, z = object_pose(obj)
    yaw = object_yaw(obj)
    speed = object_speed(obj)
    dimensions = object_dimensions(obj)
    existence_probability = getattr(obj, "existence_probability", None)
    stationary = getattr(getattr(obj, "kinematics", None), "is_stationary", None)
    if x is not None and y is not None and topic.endswith("bevfusion/objects"):
        distance_m = math.hypot(x, y)
        frame = "sensor_or_base_relative"
    elif x is not None and y is not None and ego_pose is not None:
        distance_m = math.hypot(x - ego_pose.x, y - ego_pose.y)
        frame = "map"
    elif x is not None and y is not None:
        distance_m = math.hypot(x, y)
        frame = "unknown_xy"
    else:
        distance_m = None
        frame = "unknown"
    moving = False
    if speed is not None:
        moving = speed >= speed_threshold_mps
    elif stationary is not None:
        moving = not bool(stationary)
    dynamic_candidate = class_name in {"CAR", "TRUCK", "BUS", "TRAILER", "MOTORCYCLE", "BICYCLE", "PEDESTRIAN", "UNKNOWN"}
    return {
        "object_id": object_id(obj),
        "class_label": label,
        "class_name": class_name,
        "class_probability": round(class_prob, 3) if class_prob is not None else None,
        "existence_probability": round(float(existence_probability), 3) if existence_probability is not None else None,
        "x": round(x, 3) if x is not None else None,
        "y": round(y, 3) if y is not None else None,
        "z": round(z, 3) if z is not None else None,
        "yaw_rad": round(yaw, 6) if yaw is not None else None,
        "frame_hint": frame,
        "distance_to_ego_m": round(distance_m, 3) if distance_m is not None else None,
        "speed_mps": round(speed, 3) if speed is not None else None,
        "is_stationary": bool(stationary) if stationary is not None else None,
        "moving_candidate": moving,
        "dynamic_mask_candidate": dynamic_candidate,
        "dimensions": dimensions,
    }


def pose_at_or_before(poses: list[PoseSample], pose_times: list[int], time_ns: int) -> PoseSample | None:
    index = bisect.bisect_right(pose_times, time_ns) - 1
    if index < 0:
        return None
    return poses[index]


def object_event_summary(
    topic: str,
    log_time_ns: int,
    decoded: Any,
    ego_pose: PoseSample | None,
    speed_threshold_mps: float,
    nearest_limit: int,
) -> dict[str, Any]:
    objects = getattr(decoded, "objects", []) or []
    class_counts: Counter[str] = Counter()
    dynamic_count = 0
    moving_count = 0
    objects_summary: list[dict[str, Any]] = []
    for obj in objects:
        row = summarize_object(obj, ego_pose, topic, speed_threshold_mps)
        class_counts[row["class_name"]] += 1
        if row["dynamic_mask_candidate"]:
            dynamic_count += 1
        if row["moving_candidate"]:
            moving_count += 1
        objects_summary.append(row)
    objects_summary.sort(
        key=lambda row: (
            row["distance_to_ego_m"] is None,
            row["distance_to_ego_m"] if row["distance_to_ego_m"] is not None else 1e9,
        )
    )
    return {
        "topic": topic,
        "log_time_ns": log_time_ns,
        "stamp_ns": ros_stamp_ns(decoded),
        "object_count": len(objects),
        "dynamic_mask_candidate_count": dynamic_count,
        "moving_candidate_count": moving_count,
        "class_counts": dict(sorted(class_counts.items())),
        "nearest_objects": objects_summary[:nearest_limit],
    }


def read_object_events(
    spans: list[McapSpan],
    poses: list[PoseSample],
    object_topics: list[str],
    speed_threshold_mps: float,
    nearest_limit: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    pose_times = [pose.time_ns for pose in poses]
    for span in spans:
        with span.path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[DecoderFactory()])
            for _, channel, message, decoded in reader.iter_decoded_messages(topics=object_topics, log_time_order=True):
                ego_pose = pose_at_or_before(poses, pose_times, int(message.log_time))
                events.append(
                    object_event_summary(
                        topic=channel.topic,
                        log_time_ns=int(message.log_time),
                        decoded=decoded,
                        ego_pose=ego_pose,
                        speed_threshold_mps=speed_threshold_mps,
                        nearest_limit=nearest_limit,
                    )
                )
    return events


def read_capture_indexes(
    spans: list[McapSpan],
    camera_topics: list[str],
    localization_topic: str,
    object_topics: list[str],
    speed_threshold_mps: float,
    nearest_limit: int,
) -> tuple[list[PoseSample], dict[str, list[int]], list[dict[str, Any]], dict[str, int]]:
    image_times_by_topic: dict[str, list[int]] = {topic: [] for topic in camera_topics}
    poses: list[PoseSample] = []
    object_events: list[dict[str, Any]] = []
    decode_error_counts: Counter[str] = Counter()
    topics = sorted(set(camera_topics + [localization_topic] + object_topics))
    decoder_factory = DecoderFactory()
    decoder_cache: dict[tuple[str, int | None], Any] = {}
    previous_pose: PoseSample | None = None
    camera_topic_set = set(camera_topics)
    object_topic_set = set(object_topics)
    for span in spans:
        with span.path.open("rb") as stream:
            reader = make_reader(stream)
            for schema, channel, message in reader.iter_messages(topics=topics, log_time_order=True):
                topic = channel.topic
                log_time_ns = int(message.log_time)
                if topic in camera_topic_set:
                    image_times_by_topic[topic].append(log_time_ns)
                    continue

                cache_key = (channel.message_encoding, channel.schema_id)
                decoder = decoder_cache.get(cache_key)
                if decoder is None:
                    decoder = decoder_factory.decoder_for(channel.message_encoding, schema)
                    decoder_cache[cache_key] = decoder
                if decoder is None:
                    continue
                try:
                    decoded = decoder(message.data)
                except Exception:
                    decode_error_counts[topic] += 1
                    continue

                if topic == localization_topic:
                    previous_pose = pose_from_odometry(log_time_ns, decoded, previous_pose)
                    poses.append(previous_pose)
                    continue
                if topic in object_topic_set:
                    object_events.append(
                        object_event_summary(
                            topic=topic,
                            log_time_ns=log_time_ns,
                            decoded=decoded,
                            ego_pose=previous_pose,
                            speed_threshold_mps=speed_threshold_mps,
                            nearest_limit=nearest_limit,
                        )
                    )
    for timestamps in image_times_by_topic.values():
        timestamps.sort()
    return poses, image_times_by_topic, object_events, dict(sorted(decode_error_counts.items()))


def aggregate_object_bins(events: list[dict[str, Any]], bin_sec: float) -> list[dict[str, Any]]:
    if not events:
        return []
    bin_ns = int(bin_sec * 1_000_000_000)
    origin = min(event["log_time_ns"] for event in events)
    bins: dict[int, dict[str, Any]] = {}
    for event in events:
        index = int((event["log_time_ns"] - origin) // bin_ns)
        row = bins.setdefault(
            index,
            {
                "bin_index": index,
                "start_time_ns": origin + index * bin_ns,
                "end_time_ns": origin + (index + 1) * bin_ns,
                "event_count": 0,
                "max_object_count": 0,
                "max_dynamic_mask_candidate_count": 0,
                "max_moving_candidate_count": 0,
                "topic_counts": Counter(),
                "class_counts": Counter(),
                "nearest_distance_m": None,
            },
        )
        row["event_count"] += 1
        row["max_object_count"] = max(row["max_object_count"], event["object_count"])
        row["max_dynamic_mask_candidate_count"] = max(
            row["max_dynamic_mask_candidate_count"],
            event["dynamic_mask_candidate_count"],
        )
        row["max_moving_candidate_count"] = max(row["max_moving_candidate_count"], event["moving_candidate_count"])
        row["topic_counts"][event["topic"]] += 1
        for name, count in event["class_counts"].items():
            row["class_counts"][name] += count
        for obj in event["nearest_objects"]:
            distance = obj.get("distance_to_ego_m")
            if distance is None:
                continue
            if row["nearest_distance_m"] is None or distance < row["nearest_distance_m"]:
                row["nearest_distance_m"] = distance
    output = []
    for row in sorted(bins.values(), key=lambda item: item["bin_index"]):
        out = dict(row)
        out["topic_counts"] = dict(sorted(out["topic_counts"].items()))
        out["class_counts"] = dict(sorted(out["class_counts"].items()))
        if out["nearest_distance_m"] is not None:
            out["nearest_distance_m"] = round(float(out["nearest_distance_m"]), 3)
        output.append(out)
    return output


def nearest_object_events(
    events_by_topic: dict[str, list[dict[str, Any]]],
    event_times_by_topic: dict[str, list[int]],
    time_ns: int,
    tolerance_ns: int,
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for topic, events in events_by_topic.items():
        times = event_times_by_topic[topic]
        event_time = nearest_timestamp(times, time_ns, tolerance_ns)
        if event_time is None:
            context[topic] = None
            continue
        event = events[bisect.bisect_left(times, event_time)]
        context[topic] = {
            "log_time_ns": event["log_time_ns"],
            "dt_sec": round((event["log_time_ns"] - time_ns) / 1_000_000_000.0, 3),
            "object_count": event["object_count"],
            "dynamic_mask_candidate_count": event["dynamic_mask_candidate_count"],
            "moving_candidate_count": event["moving_candidate_count"],
            "class_counts": event["class_counts"],
            "nearest_objects": event["nearest_objects"],
        }
    return context


def write_keyframe_csv(path: Path, keyframes: list[dict[str, Any]], camera_topics: list[str]) -> None:
    fields = [
        "keyframe_id",
        "time_ns",
        "x",
        "y",
        "z",
        "yaw_rad",
        "speed_mps",
        "cumulative_distance_m",
        "mask_required",
    ]
    for topic in camera_topics:
        fields.append(f"image_time_ns::{topic}")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for frame in keyframes:
            row = {field: frame.get(field) for field in fields}
            for topic in camera_topics:
                image = frame["camera_images"].get(topic)
                row[f"image_time_ns::{topic}"] = image["log_time_ns"] if image else ""
            writer.writerow(row)


def write_markdown_report(manifest: dict[str, Any], path: Path) -> None:
    dyn = manifest["dynamic_obstacle_index"]
    lines = [
        "# Reconstruction Keyframe And Dynamic Mask Index",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- source_bag: `{manifest['source_bag']}`",
        f"- output_dir: `{manifest['output_dir']}`",
        f"- selected_keyframes: `{manifest['keyframe_index']['selected_keyframe_count']}`",
        f"- route_distance_m: `{manifest['localization_summary']['route_distance_m']}`",
        f"- object_events: `{dyn['event_count']}`",
        f"- dynamic_bins: `{dyn['bin_count']}`",
        "",
        "## Available Camera Topics",
        "",
    ]
    for topic in manifest["available_camera_topics"]:
        lines.append(f"- `{topic}`")
    lines.extend(["", f"camera_index_status: `{manifest['keyframe_index']['camera_index_status']}`", ""])
    lines.extend(["", "## Object Topics", ""])
    for topic in manifest["object_topics"]:
        lines.append(f"- `{topic}`")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "- Current CARLA 0.9.15 import target remains `mesh + OpenDRIVE` for drivable collision and routing.",
            "- 3DGS/Gaussian should be treated as a visual reconstruction lane until a NuRec-capable runtime is separately validated.",
            "- `mask_required=true` keyframes should be fed into a dynamic-object masking step before static Gaussian or texture baking.",
            "",
            "## Output Files",
            "",
        ]
    )
    for key in ["keyframes_json", "keyframes_csv", "dynamic_index_json", "manifest_json"]:
        lines.append(f"- {key}: `{manifest['outputs'][key]}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    bag_dir = args.bag_dir.resolve()
    metadata_path = bag_dir / "metadata.yaml"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.yaml not found under {bag_dir}")
    mcap_paths = sorted(bag_dir.glob("*.mcap"))
    if not mcap_paths:
        raise FileNotFoundError(f"no .mcap files found under {bag_dir}")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = load_metadata(metadata_path)
    available_camera_topics = compressed_image_topics(metadata)
    camera_topics = [] if args.skip_camera_index else (args.camera_topic or available_camera_topics)
    object_topics = args.object_topic or DEFAULT_OBJECT_TOPICS
    spans = mcap_spans(mcap_paths)

    poses, image_times_by_topic, object_events, decode_error_counts = read_capture_indexes(
        spans=spans,
        camera_topics=camera_topics,
        localization_topic=args.localization_topic,
        object_topics=object_topics,
        speed_threshold_mps=args.speed_threshold_mps,
        nearest_limit=args.nearest_object_limit,
    )
    if not poses:
        raise RuntimeError(f"no localization messages found for {args.localization_topic}")
    keyframe_poses = select_keyframes(
        poses,
        distance_step_m=args.distance_step_m,
        min_time_step_sec=args.min_time_step_sec,
        max_keyframes=args.max_keyframes,
    )

    image_tolerance_ns = int(args.image_tolerance_sec * 1_000_000_000)

    events_by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in object_events:
        events_by_topic[event["topic"]].append(event)
    for rows in events_by_topic.values():
        rows.sort(key=lambda row: row["log_time_ns"])
    event_times_by_topic = {
        topic: [event["log_time_ns"] for event in rows]
        for topic, rows in events_by_topic.items()
    }
    object_tolerance_ns = int(args.object_context_tolerance_sec * 1_000_000_000)

    keyframes: list[dict[str, Any]] = []
    for index, pose in enumerate(keyframe_poses):
        camera_images = {}
        for topic in camera_topics:
            image_time = nearest_timestamp(image_times_by_topic[topic], pose.time_ns, image_tolerance_ns)
            camera_images[topic] = None if image_time is None else {
                "log_time_ns": image_time,
                "dt_sec": round((image_time - pose.time_ns) / 1_000_000_000.0, 3),
            }
        object_context = nearest_object_events(
            events_by_topic,
            event_times_by_topic,
            pose.time_ns,
            object_tolerance_ns,
        )
        mask_required = any(
            row is not None and row.get("dynamic_mask_candidate_count", 0) > 0
            for row in object_context.values()
        )
        keyframes.append(
            {
                "keyframe_id": f"kf_{index:05d}",
                "time_ns": pose.time_ns,
                "stamp_ns": pose.stamp_ns,
                "x": round(pose.x, 3),
                "y": round(pose.y, 3),
                "z": round(pose.z, 3),
                "yaw_rad": round(pose.yaw_rad, 6),
                "speed_mps": round(pose.speed_mps, 3),
                "cumulative_distance_m": round(pose.cumulative_distance_m, 3),
                "camera_images": camera_images,
                "object_context": object_context,
                "mask_required": mask_required,
            }
        )

    dynamic_bins = aggregate_object_bins(object_events, args.dynamic_bin_sec)
    outputs = {
        "keyframes_json": str(output_dir / "keyframes.json"),
        "keyframes_csv": str(output_dir / "keyframes.csv"),
        "dynamic_index_json": str(output_dir / "dynamic_obstacle_index.json"),
        "manifest_json": str(output_dir / "reconstruction_prep_manifest.json"),
        "report_md": str(output_dir / "reconstruction_prep_report.md"),
    }
    dynamic_index = {
        "event_count": len(object_events),
        "bin_sec": args.dynamic_bin_sec,
        "bin_count": len(dynamic_bins),
        "decode_error_counts": decode_error_counts,
        "events": object_events,
        "bins": dynamic_bins,
    }
    manifest = {
        "generated_at": utc_now(),
        "source_bag": str(bag_dir),
        "output_dir": str(output_dir),
        "available_camera_topics": available_camera_topics,
        "camera_topics": camera_topics,
        "localization_topic": args.localization_topic,
        "object_topics": object_topics,
        "localization_summary": {
            "pose_count": len(poses),
            "start_time_ns": poses[0].time_ns,
            "end_time_ns": poses[-1].time_ns,
            "duration_sec": round((poses[-1].time_ns - poses[0].time_ns) / 1_000_000_000.0, 3),
            "route_distance_m": round(poses[-1].cumulative_distance_m, 3),
        },
        "keyframe_index": {
            "distance_step_m": args.distance_step_m,
            "min_time_step_sec": args.min_time_step_sec,
            "selected_keyframe_count": len(keyframes),
            "image_tolerance_sec": args.image_tolerance_sec,
            "camera_index_status": "skipped" if args.skip_camera_index else "indexed",
            "object_context_tolerance_sec": args.object_context_tolerance_sec,
            "mask_required_count": sum(1 for frame in keyframes if frame["mask_required"]),
        },
        "dynamic_obstacle_index": {
            "event_count": dynamic_index["event_count"],
            "bin_sec": args.dynamic_bin_sec,
            "bin_count": dynamic_index["bin_count"],
            "speed_threshold_mps": args.speed_threshold_mps,
            "decode_error_counts": decode_error_counts,
        },
        "carla_import_lane": {
            "stable_target": "mesh_plus_opendrive_for_carla0915",
            "gaussian_target": "visual_reconstruction_or_nurec_research",
            "note": "Gaussian splats are not treated as directly importable CARLA 0.9.15 maps.",
        },
        "outputs": outputs,
    }

    Path(outputs["keyframes_json"]).write_text(json.dumps({"keyframes": keyframes}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_keyframe_csv(Path(outputs["keyframes_csv"]), keyframes, camera_topics)
    Path(outputs["dynamic_index_json"]).write_text(json.dumps(dynamic_index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(outputs["manifest_json"]).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown_report(manifest, Path(outputs["report_md"]))
    print(json.dumps({"manifest": outputs["manifest_json"], "keyframes": len(keyframes), "object_events": len(object_events)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a reconstruction keyframe index and dynamic-object mask index from a rosbag2 MCAP capture."
    )
    parser.add_argument("--bag-dir", type=Path, required=True, help="rosbag2 directory containing metadata.yaml and .mcap files")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for keyframe and dynamic object index outputs")
    parser.add_argument("--camera-topic", action="append", help="CompressedImage topic to index. Defaults to all compressed image topics.")
    parser.add_argument("--skip-camera-index", action="store_true", help="Do not scan image messages; keep keyframes pose/object-only for faster Mac-side prep.")
    parser.add_argument("--localization-topic", default=DEFAULT_LOCALIZATION_TOPIC)
    parser.add_argument("--object-topic", action="append", help="Object topic to index. Defaults to BEVFusion, tracked, and predicted objects.")
    parser.add_argument("--distance-step-m", type=float, default=5.0, help="Route distance spacing between selected keyframes")
    parser.add_argument("--min-time-step-sec", type=float, default=0.5, help="Minimum time spacing between selected keyframes")
    parser.add_argument("--max-keyframes", type=int, default=0, help="Optional cap on selected keyframes. 0 means no cap.")
    parser.add_argument("--image-tolerance-sec", type=float, default=0.25, help="Nearest camera timestamp tolerance")
    parser.add_argument("--object-context-tolerance-sec", type=float, default=0.75, help="Nearest object message tolerance per keyframe")
    parser.add_argument("--dynamic-bin-sec", type=float, default=1.0, help="Aggregation bin size for dynamic object summaries")
    parser.add_argument("--speed-threshold-mps", type=float, default=0.5, help="Speed threshold for moving object candidates")
    parser.add_argument("--nearest-object-limit", type=int, default=8, help="Objects retained per object event, sorted by distance to ego")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
