#!/usr/bin/env python3
"""Extract real Robobus dynamics from a recorded bag and suggest CARLA runtime knobs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


DEFAULT_TOPICS = (
    "/sensing/vehicle_velocity_converter/twist_with_covariance",
    "/localization/twist_estimator/twist_with_covariance",
    "/localization/twist_estimator/gyro_twist",
    "/sensing/gnss/imu",
    "/sensing/gnss/heading",
    "/pix_robobus/va_chassis_wheel_rpm_fb",
)

DEFAULT_PLANNING_TOPICS = (
    "/control/command/control_cmd",
    "/control/command/actuation_cmd",
    "/vehicle/status/steering_status",
    "/vehicle/status/velocity_status",
    "/localization/kinematic_state",
)


@dataclass(frozen=True)
class TrajectoryPose:
    t_sec: float
    x: float
    y: float
    z: float
    yaw_rad: float


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def percentile(values: Iterable[float], q: float) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    rank = (len(clean) - 1) * q
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return clean[int(rank)]
    weight = rank - lower
    return clean[lower] * (1.0 - weight) + clean[upper] * weight


def value_stats(values: Iterable[float]) -> dict[str, float | int | None]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {
            "count": 0,
            "min": None,
            "p50": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "max": None,
            "mean": None,
        }
    return {
        "count": len(clean),
        "min": min(clean),
        "p50": percentile(clean, 0.50),
        "p90": percentile(clean, 0.90),
        "p95": percentile(clean, 0.95),
        "p99": percentile(clean, 0.99),
        "max": max(clean),
        "mean": sum(clean) / len(clean),
    }


def round_nested(value: Any, digits: int = 6) -> Any:
    if isinstance(value, float):
        return round(value, digits) if math.isfinite(value) else None
    if isinstance(value, list):
        return [round_nested(item, digits) for item in value]
    if isinstance(value, dict):
        return {key: round_nested(item, digits) for key, item in value.items()}
    return value


def quaternion_yaw(qx: float, qy: float, qz: float, qw: float) -> float:
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


def unwrap_delta_rad(delta: float) -> float:
    while delta <= -math.pi:
        delta += 2.0 * math.pi
    while delta > math.pi:
        delta -= 2.0 * math.pi
    return delta


def load_metadata_topics(metadata_path: Path | None) -> dict[str, dict[str, Any]]:
    if metadata_path is None or not metadata_path.exists():
        return {}
    payload = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
    info = payload.get("rosbag2_bagfile_information", payload)
    topics: dict[str, dict[str, Any]] = {}
    for item in info.get("topics_with_message_count", []) or []:
        meta = item.get("topic_metadata", {}) if isinstance(item, dict) else {}
        name = meta.get("name")
        if not name:
            continue
        topics[str(name)] = {
            "type": meta.get("type"),
            "message_count": int(item.get("message_count") or 0),
            "serialization_format": meta.get("serialization_format"),
        }
    return topics


def load_trajectory_csv(path: Path | None) -> list[TrajectoryPose]:
    if path is None or not path.exists():
        return []
    poses: list[TrajectoryPose] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            t_ns = finite(row.get("cloud_bag_time_ns") or row.get("tf_stamp_ns") or row.get("cloud_stamp_ns"))
            x = finite(row.get("x"))
            y = finite(row.get("y"))
            z = finite(row.get("z"))
            qx = finite(row.get("qx"))
            qy = finite(row.get("qy"))
            qz = finite(row.get("qz"))
            qw = finite(row.get("qw"))
            if None in {t_ns, x, y, z, qx, qy, qz, qw}:
                continue
            poses.append(
                TrajectoryPose(
                    t_sec=float(t_ns) * 1e-9,
                    x=float(x),
                    y=float(y),
                    z=float(z),
                    yaw_rad=quaternion_yaw(float(qx), float(qy), float(qz), float(qw)),
                )
            )
    return sorted(poses, key=lambda pose: pose.t_sec)


def adjacent_rates(samples: list[tuple[float, float]], max_dt_sec: float = 5.0) -> list[float]:
    rates: list[float] = []
    for previous, current in zip(samples, samples[1:]):
        dt = current[0] - previous[0]
        if dt <= 1e-6 or dt > max_dt_sec:
            continue
        rates.append((current[1] - previous[1]) / dt)
    return rates


def summarize_trajectory(poses: list[TrajectoryPose]) -> dict[str, Any]:
    if len(poses) < 2:
        return {"pose_count": len(poses), "available": False}
    distances: list[float] = []
    speed_samples: list[tuple[float, float]] = []
    yaw_samples: list[tuple[float, float]] = []
    grade_samples: list[float] = []
    route_length = 0.0
    for previous, current in zip(poses, poses[1:]):
        dt = current.t_sec - previous.t_sec
        dxy = math.hypot(current.x - previous.x, current.y - previous.y)
        dz = current.z - previous.z
        route_length += dxy
        distances.append(dxy)
        if dt > 1e-6:
            speed_samples.append((current.t_sec, dxy / dt))
            yaw_delta = unwrap_delta_rad(current.yaw_rad - previous.yaw_rad)
            yaw_samples.append((current.t_sec, yaw_delta / dt))
        if dxy > 1e-6:
            grade_samples.append(math.degrees(math.atan2(dz, dxy)))
    speeds = [sample[1] for sample in speed_samples]
    accelerations = adjacent_rates(speed_samples, max_dt_sec=8.0)
    return {
        "available": True,
        "pose_count": len(poses),
        "duration_sec": poses[-1].t_sec - poses[0].t_sec,
        "route_length_m": route_length,
        "closed_loop_gap_m": math.hypot(poses[-1].x - poses[0].x, poses[-1].y - poses[0].y),
        "sample_spacing_m": value_stats(distances),
        "speed_mps": value_stats(speeds),
        "accel_mps2": value_stats(accelerations),
        "decel_mps2_abs": value_stats([-value for value in accelerations if value < 0.0]),
        "yaw_rate_radps_abs": value_stats([abs(sample[1]) for sample in yaw_samples]),
        "grade_deg_abs": value_stats([abs(value) for value in grade_samples]),
    }


def vector_speed(linear: Any) -> float:
    return math.sqrt(float(linear.x) ** 2 + float(linear.y) ** 2 + float(linear.z) ** 2)


def flatten_numeric_fields(message: Any, prefix: str = "", depth: int = 0) -> dict[str, float]:
    if depth > 3:
        return {}
    fields: dict[str, float] = {}
    slots = getattr(message, "__slots__", [])
    for raw_name in slots:
        name = str(raw_name).lstrip("_")
        if name in {"header"}:
            continue
        try:
            value = getattr(message, name)
        except AttributeError:
            continue
        key = f"{prefix}.{name}" if prefix else name
        numeric = finite(value)
        if numeric is not None:
            fields[key] = numeric
            continue
        if hasattr(value, "__slots__"):
            fields.update(flatten_numeric_fields(value, key, depth + 1))
    return fields


def parse_ros_message(topic: str, message: Any, t_sec: float) -> dict[str, Any]:
    if topic.endswith("/control_cmd"):
        lateral = message.lateral
        longitudinal = message.longitudinal
        return {
            "t_sec": t_sec,
            "control_steering_tire_angle_rad": float(lateral.steering_tire_angle),
            "control_steering_rate_radps": float(getattr(lateral, "steering_tire_rotation_rate", 0.0)),
            "target_velocity_mps": float(longitudinal.velocity),
            "target_accel_mps2": float(longitudinal.acceleration),
            "target_jerk_mps3": float(getattr(longitudinal, "jerk", 0.0)),
        }
    if topic.endswith("/actuation_cmd"):
        actuation = message.actuation
        return {
            "t_sec": t_sec,
            "actuation_accel_cmd": float(actuation.accel_cmd),
            "actuation_brake_cmd": float(actuation.brake_cmd),
            "actuation_steer_cmd": float(actuation.steer_cmd),
        }
    if topic.endswith("/steering_status"):
        return {
            "t_sec": t_sec,
            "steering_tire_angle_rad": float(message.steering_tire_angle),
        }
    if topic.endswith("/velocity_status"):
        return {
            "t_sec": t_sec,
            "speed_mps": abs(float(message.longitudinal_velocity)),
            "longitudinal_velocity_mps": float(message.longitudinal_velocity),
            "lateral_velocity_mps": float(message.lateral_velocity),
            "yaw_rate_radps": float(message.heading_rate),
        }
    if topic.endswith("/kinematic_state"):
        twist = message.twist.twist
        return {
            "t_sec": t_sec,
            "speed_mps": vector_speed(twist.linear),
            "linear_x_mps": float(twist.linear.x),
            "linear_y_mps": float(twist.linear.y),
            "yaw_rate_radps": float(twist.angular.z),
        }
    if topic.endswith("twist_with_covariance"):
        twist = message.twist.twist
        return {
            "t_sec": t_sec,
            "speed_mps": vector_speed(twist.linear),
            "linear_x_mps": float(twist.linear.x),
            "linear_y_mps": float(twist.linear.y),
            "yaw_rate_radps": float(twist.angular.z),
        }
    if topic.endswith("gyro_twist"):
        twist = message.twist
        return {
            "t_sec": t_sec,
            "speed_mps": vector_speed(twist.linear),
            "linear_x_mps": float(twist.linear.x),
            "linear_y_mps": float(twist.linear.y),
            "yaw_rate_radps": float(twist.angular.z),
        }
    if topic.endswith("/imu"):
        return {
            "t_sec": t_sec,
            "linear_accel_x_mps2": float(message.linear_acceleration.x),
            "linear_accel_y_mps2": float(message.linear_acceleration.y),
            "linear_accel_z_mps2": float(message.linear_acceleration.z),
            "yaw_rate_radps": float(message.angular_velocity.z),
        }
    if topic.endswith("/heading"):
        return {"t_sec": t_sec, "heading": float(message.data)}
    if topic.endswith("va_chassis_wheel_rpm_fb"):
        return {"t_sec": t_sec, "numeric_fields": flatten_numeric_fields(message)}
    return {"t_sec": t_sec}


def extract_rosbag_samples(
    bag_path: Path | None,
    topics: tuple[str, ...],
    sample_period_sec: float,
    max_messages_per_topic: int,
) -> dict[str, Any]:
    if bag_path is None:
        return {"available": False, "blocked_reason": "bag_path_not_provided", "samples": {}}
    try:
        import rosbag2_py  # type: ignore
        from rclpy.serialization import deserialize_message  # type: ignore
        from rosidl_runtime_py.utilities import get_message  # type: ignore
    except Exception as exc:
        return {
            "available": False,
            "blocked_reason": f"ros2_python_import_failed:{type(exc).__name__}:{exc}",
            "samples": {},
        }

    selected = set(topics)
    samples: dict[str, list[dict[str, Any]]] = {topic: [] for topic in topics}
    errors: dict[str, str] = {}
    try:
        reader = rosbag2_py.SequentialReader()
        storage_options = rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="mcap")
        converter_options = rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        )
        reader.open(storage_options, converter_options)
        type_map = {topic.name: topic.type for topic in reader.get_all_topics_and_types()}
        message_types = {}
        for topic in selected:
            if topic not in type_map:
                errors.setdefault(topic, "topic_not_found_in_bag")
                continue
            try:
                message_types[topic] = get_message(type_map[topic])
            except Exception as exc:
                errors.setdefault(topic, f"message_type_unavailable:{type(exc).__name__}:{exc}")
        if hasattr(reader, "set_filter") and hasattr(rosbag2_py, "StorageFilter"):
            reader.set_filter(rosbag2_py.StorageFilter(topics=sorted(message_types)))
        last_kept_ns: dict[str, int] = defaultdict(lambda: -10**30)
        sample_period_ns = max(0, int(sample_period_sec * 1e9))
        while reader.has_next():
            topic, raw, t_ns = reader.read_next()
            if topic not in selected or topic not in message_types:
                continue
            if len(samples[topic]) >= max_messages_per_topic:
                continue
            if t_ns - last_kept_ns[topic] < sample_period_ns:
                continue
            try:
                message = deserialize_message(raw, message_types[topic])
                samples[topic].append(parse_ros_message(topic, message, t_ns * 1e-9))
                last_kept_ns[topic] = t_ns
            except Exception as exc:
                errors.setdefault(topic, f"{type(exc).__name__}:{exc}")
    except Exception as exc:
        return {
            "available": False,
            "blocked_reason": f"rosbag_read_failed:{type(exc).__name__}:{exc}",
            "samples": samples,
            "errors": errors,
        }
    return {
        "available": True,
        "blocked_reason": None,
        "sample_period_sec": sample_period_sec,
        "max_messages_per_topic": max_messages_per_topic,
        "samples": samples,
        "errors": errors,
    }


def _open_mcap_stream(path: Path) -> Any:
    if path.suffix == ".zst":
        import zstandard as zstd  # type: ignore

        raw = path.open("rb")
        dctx = zstd.ZstdDecompressor()
        stream = dctx.stream_reader(raw)
        return raw, stream
    stream = path.open("rb")
    return None, stream


def extract_mcap_ros2_samples(
    paths: list[Path],
    topics: tuple[str, ...],
    sample_period_sec: float,
    max_messages_per_topic: int,
) -> dict[str, Any]:
    if not paths:
        return {"available": False, "blocked_reason": "mcap_paths_not_provided", "samples": {}}
    try:
        from mcap.reader import make_reader  # type: ignore
        from mcap_ros2.decoder import DecoderFactory  # type: ignore
    except Exception as exc:
        return {
            "available": False,
            "blocked_reason": f"mcap_ros2_import_failed:{type(exc).__name__}:{exc}",
            "samples": {},
        }
    samples: dict[str, list[dict[str, Any]]] = {topic: [] for topic in topics}
    errors: dict[str, str] = {}
    selected = set(topics)
    last_kept_ns: dict[str, int] = defaultdict(lambda: -10**30)
    sample_period_ns = max(0, int(sample_period_sec * 1e9))
    for path in paths:
        if not path.exists():
            errors[str(path)] = "path_not_found"
            continue
        raw = None
        try:
            raw, stream = _open_mcap_stream(path)
            with stream:
                reader = make_reader(stream, decoder_factories=[DecoderFactory()])
                for schema, channel, message, decoded in reader.iter_decoded_messages(topics=sorted(selected)):
                    topic = channel.topic
                    if len(samples[topic]) >= max_messages_per_topic:
                        continue
                    t_ns = int(message.log_time)
                    if t_ns - last_kept_ns[topic] < sample_period_ns:
                        continue
                    try:
                        samples[topic].append(parse_ros_message(topic, decoded, t_ns * 1e-9))
                        last_kept_ns[topic] = t_ns
                    except Exception as exc:
                        errors.setdefault(topic, f"message_parse_failed:{type(exc).__name__}:{exc}")
        except Exception as exc:
            errors.setdefault(str(path), f"mcap_read_failed:{type(exc).__name__}:{exc}")
        finally:
            if raw is not None:
                raw.close()
    available = any(samples.values())
    return {
        "available": available,
        "blocked_reason": None if available else "no_selected_samples_decoded",
        "sample_period_sec": sample_period_sec,
        "max_messages_per_topic": max_messages_per_topic,
        "paths": [str(path) for path in paths],
        "samples": samples,
        "errors": errors,
    }


def summarize_bag_samples(samples_by_topic: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for topic, samples in samples_by_topic.items():
        if not samples:
            summary[topic] = {"sample_count": 0}
            continue
        speed_samples = [(float(item["t_sec"]), float(item["speed_mps"])) for item in samples if "speed_mps" in item]
        accel = adjacent_rates(speed_samples, max_dt_sec=2.0)
        yaw_rates = [abs(float(item["yaw_rate_radps"])) for item in samples if "yaw_rate_radps" in item]
        entry: dict[str, Any] = {
            "sample_count": len(samples),
            "time_span_sec": float(samples[-1]["t_sec"]) - float(samples[0]["t_sec"]) if len(samples) > 1 else 0.0,
        }
        if speed_samples:
            entry["speed_mps"] = value_stats([sample[1] for sample in speed_samples])
            entry["accel_mps2"] = value_stats(accel)
            entry["decel_mps2_abs"] = value_stats([-value for value in accel if value < 0.0])
        if yaw_rates:
            entry["yaw_rate_radps_abs"] = value_stats(yaw_rates)
        numeric_series: dict[str, list[float]] = defaultdict(list)
        for item in samples:
            for field, value in item.items():
                if field in {"t_sec", "numeric_fields"}:
                    continue
                numeric = finite(value)
                if numeric is not None:
                    numeric_series[field].append(numeric)
        if numeric_series:
            entry["numeric_stats"] = {
                field: value_stats(values) for field, values in sorted(numeric_series.items())
            }
            entry["numeric_abs_stats"] = {
                field: value_stats([abs(value) for value in values])
                for field, values in sorted(numeric_series.items())
            }
        wheel_fields: dict[str, list[float]] = defaultdict(list)
        for item in samples:
            for field, value in (item.get("numeric_fields") or {}).items():
                wheel_fields[field].append(float(value))
        if wheel_fields:
            entry["numeric_field_stats"] = {
                field: value_stats(values) for field, values in sorted(wheel_fields.items())
            }
        summary[topic] = entry
    return summary


def first_stat(summary: dict[str, Any], key: str, stat: str) -> float | None:
    for topic in (
        "/vehicle/status/velocity_status",
        "/localization/kinematic_state",
        "/sensing/vehicle_velocity_converter/twist_with_covariance",
        "/localization/twist_estimator/twist_with_covariance",
        "/localization/twist_estimator/gyro_twist",
        "trajectory",
    ):
        entry = summary.get(topic, {})
        stats = entry.get(key, {}) if isinstance(entry, dict) else {}
        value = stats.get(stat) if isinstance(stats, dict) else None
        numeric = finite(value)
        if numeric is not None:
            return numeric
    return None


def max_stat(summary: dict[str, Any], key: str, stat: str, minimum: float = 0.0) -> float | None:
    values: list[float] = []
    for entry in summary.values():
        stats = entry.get(key, {}) if isinstance(entry, dict) else {}
        value = stats.get(stat) if isinstance(stats, dict) else None
        numeric = finite(value)
        if numeric is not None and numeric > minimum:
            values.append(numeric)
    return max(values) if values else None


def nested_stat(
    summary: dict[str, Any],
    topic: str,
    section: str,
    field: str,
    stat: str,
) -> float | None:
    entry = summary.get(topic, {})
    if not isinstance(entry, dict):
        return None
    section_values = entry.get(section, {})
    if not isinstance(section_values, dict):
        return None
    field_stats = section_values.get(field, {})
    if not isinstance(field_stats, dict):
        return None
    return finite(field_stats.get(stat))


def clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def suggest_runtime_overrides(
    dynamics_summary: dict[str, Any],
    current_carla_max_speed_mps: float | None,
    current_throttle_gain: float,
    current_max_throttle: float,
    current_brake_gain: float,
    current_max_brake: float,
    current_steer_gain: float,
) -> dict[str, Any]:
    real_speed_p95 = first_stat(dynamics_summary, "speed_mps", "p95")
    real_speed_p99 = first_stat(dynamics_summary, "speed_mps", "p99")
    real_speed_max = first_stat(dynamics_summary, "speed_mps", "max")
    real_decel_p95 = first_stat(dynamics_summary, "decel_mps2_abs", "p95")
    real_yaw_p95 = max_stat(dynamics_summary, "yaw_rate_radps_abs", "p95")
    target_speed = None
    if real_speed_p95 is not None:
        ceiling = real_speed_p99 if real_speed_p99 is not None else real_speed_max
        target_speed = real_speed_p95 * 1.10
        if ceiling is not None:
            target_speed = min(target_speed, ceiling * 1.05)

    overrides: dict[str, Any] = {}
    if current_carla_max_speed_mps and target_speed and current_carla_max_speed_mps > 0.1:
        ratio = clamp(target_speed / current_carla_max_speed_mps, 0.25, 1.20)
        if 0.90 <= ratio <= 1.10:
            throttle_gain = current_throttle_gain
            max_throttle = current_max_throttle
            throttle_reason = (
                f"CARLA reference speed {current_carla_max_speed_mps:.2f} m/s is already inside "
                f"the recorded speed envelope target {target_speed:.2f} m/s"
            )
            max_throttle_reason = "keep full throttle authority; planner actuation commands already cap cruise speed"
        else:
            throttle_gain = current_throttle_gain * clamp(ratio, 0.35, 1.10)
            max_throttle = current_max_throttle * clamp(ratio + 0.10, 0.30, 1.00)
            throttle_reason = (
                f"bag target speed {target_speed:.2f} m/s vs current CARLA reference "
                f"{current_carla_max_speed_mps:.2f} m/s"
            )
            max_throttle_reason = "cap throttle while validating the qiyu loop speed envelope from the recorded bag"
        overrides["pix_carla_throttle_gain"] = {
            "current": current_throttle_gain,
            "suggested": round(throttle_gain, 3),
            "reason": throttle_reason,
        }
        overrides["pix_carla_max_throttle"] = {
            "current": current_max_throttle,
            "suggested": round(max_throttle, 3),
            "reason": max_throttle_reason,
        }
    else:
        overrides["pix_carla_throttle_gain"] = {
            "current": current_throttle_gain,
            "suggested": current_throttle_gain,
            "reason": "not enough bag speed evidence or no CARLA reference speed was provided",
        }
        overrides["pix_carla_max_throttle"] = {
            "current": current_max_throttle,
            "suggested": current_max_throttle,
            "reason": "not enough bag speed evidence or no CARLA reference speed was provided",
        }

    actuation_brake_p95 = nested_stat(
        dynamics_summary,
        "/control/command/actuation_cmd",
        "numeric_abs_stats",
        "actuation_brake_cmd",
        "p95",
    )
    if real_decel_p95 is not None and real_decel_p95 > 0.1:
        if actuation_brake_p95 is not None and actuation_brake_p95 > 0.05:
            target_carla_brake_at_p95 = 0.85 if real_decel_p95 >= 0.75 else 0.65
            brake_gain = clamp(target_carla_brake_at_p95 / actuation_brake_p95, current_brake_gain, 2.0)
            max_brake = 1.0 if real_decel_p95 >= 0.75 else clamp(current_max_brake, 0.80, 1.00)
            brake_reason = (
                f"planning brake cmd p95 {actuation_brake_p95:.3f} maps to only "
                f"{actuation_brake_p95 * current_brake_gain:.3f} CARLA brake with current gain; "
                f"bag deceleration p95 target is {real_decel_p95:.2f} m/s^2"
            )
            max_brake_reason = "allow full CARLA brake authority for the next qiyu route calibration run"
        else:
            brake_gain = clamp(current_brake_gain, 0.10, 0.80)
            max_brake = clamp(current_max_brake, 0.50, 1.00)
            brake_reason = (
                f"bag deceleration p95 target is {real_decel_p95:.2f} m/s^2; "
                "requires next CARLA brake probe fit"
            )
            max_brake_reason = "keep braking bounded until simulated brake step response is compared against bag deceleration"
        overrides["pix_carla_brake_gain"] = {
            "current": current_brake_gain,
            "suggested": round(brake_gain, 3),
            "reason": brake_reason,
        }
        overrides["pix_carla_max_brake"] = {
            "current": current_max_brake,
            "suggested": round(max_brake, 3),
            "reason": max_brake_reason,
        }

    steer_cmd_max = nested_stat(
        dynamics_summary,
        "/control/command/actuation_cmd",
        "numeric_abs_stats",
        "actuation_steer_cmd",
        "max",
    )
    steering_feedback_max = nested_stat(
        dynamics_summary,
        "/vehicle/status/steering_status",
        "numeric_abs_stats",
        "steering_tire_angle_rad",
        "max",
    )
    if steer_cmd_max is not None and steering_feedback_max is not None:
        steer_reason = (
            f"planning steer cmd max {steer_cmd_max:.3f} rad and steering feedback max "
            f"{steering_feedback_max:.3f} rad are available; keep gain for the first brake-focused route trial"
        )
    elif real_yaw_p95 is not None:
        steer_reason = (
            f"bag yaw-rate p95 is {real_yaw_p95:.3f} rad/s; steering still needs command/feedback or "
            "CARLA lateral-error fit"
        )
    else:
        steer_reason = "steering needs yaw-rate plus steering command or CARLA lateral-error fit"
    overrides["pix_carla_steer_gain"] = {
        "current": current_steer_gain,
        "suggested": current_steer_gain,
        "reason": steer_reason,
    }
    return {
        "target_speed_mps": target_speed,
        "real_speed_p95_mps": real_speed_p95,
        "real_speed_p99_mps": real_speed_p99,
        "real_decel_p95_mps2": real_decel_p95,
        "real_yaw_rate_p95_radps": real_yaw_p95,
        "stable_runtime_overrides": overrides,
    }


def analyze_planning_control(
    dynamics_summary: dict[str, Any],
    current_brake_gain: float,
    current_max_brake: float,
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    brake_override = recommendation.get("stable_runtime_overrides", {}).get("pix_carla_brake_gain", {})
    max_brake_override = recommendation.get("stable_runtime_overrides", {}).get("pix_carla_max_brake", {})
    suggested_brake_gain = finite(brake_override.get("suggested")) or current_brake_gain
    suggested_max_brake = finite(max_brake_override.get("suggested")) or current_max_brake
    brake_p95 = nested_stat(
        dynamics_summary,
        "/control/command/actuation_cmd",
        "numeric_abs_stats",
        "actuation_brake_cmd",
        "p95",
    )
    brake_max = nested_stat(
        dynamics_summary,
        "/control/command/actuation_cmd",
        "numeric_abs_stats",
        "actuation_brake_cmd",
        "max",
    )
    control_steer_max = nested_stat(
        dynamics_summary,
        "/control/command/control_cmd",
        "numeric_abs_stats",
        "control_steering_tire_angle_rad",
        "max",
    )
    actuation_steer_max = nested_stat(
        dynamics_summary,
        "/control/command/actuation_cmd",
        "numeric_abs_stats",
        "actuation_steer_cmd",
        "max",
    )
    steering_feedback_max = nested_stat(
        dynamics_summary,
        "/vehicle/status/steering_status",
        "numeric_abs_stats",
        "steering_tire_angle_rad",
        "max",
    )
    control_target_velocity_p95 = nested_stat(
        dynamics_summary,
        "/control/command/control_cmd",
        "numeric_stats",
        "target_velocity_mps",
        "p95",
    )
    vehicle_speed_p95 = first_stat(dynamics_summary, "speed_mps", "p95")
    current_brake_at_p95 = None
    suggested_brake_at_p95 = None
    if brake_p95 is not None:
        current_brake_at_p95 = min(brake_p95 * current_brake_gain, current_max_brake)
        suggested_brake_at_p95 = min(brake_p95 * suggested_brake_gain, suggested_max_brake)
    sample_counts = {
        topic: entry.get("sample_count")
        for topic, entry in dynamics_summary.items()
        if topic in DEFAULT_PLANNING_TOPICS and isinstance(entry, dict)
    }
    available = any((count or 0) > 0 for count in sample_counts.values())
    if brake_p95 is not None and current_brake_at_p95 is not None and current_brake_at_p95 < 0.15:
        decision = "planning bag shows current CARLA brake mapping is too weak; run next qiyu route trial with stronger brake gain"
    elif available:
        decision = "planning bag provides control/status evidence; use route lateral error before changing steer gain"
    else:
        decision = "planning control topics were not decoded"
    return {
        "available": available,
        "sample_counts": sample_counts,
        "control_target_velocity_p95_mps": control_target_velocity_p95,
        "vehicle_speed_p95_mps": vehicle_speed_p95,
        "actuation_brake_cmd_p95": brake_p95,
        "actuation_brake_cmd_max": brake_max,
        "current_carla_brake_at_p95_cmd": current_brake_at_p95,
        "suggested_carla_brake_at_p95_cmd": suggested_brake_at_p95,
        "control_steer_cmd_max_abs_rad": control_steer_max,
        "actuation_steer_cmd_max_abs_rad": actuation_steer_max,
        "steering_feedback_max_abs_rad": steering_feedback_max,
        "decision": decision,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    recommendation = report["recommendation"]
    planning_control = report.get("planning_control_analysis", {})
    lines = [
        "# Robobus Bag-Based Physics Calibration",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Status: `{report['status']}`",
        f"- Source bag: `{report['source_assets'].get('bag')}`",
        f"- Planning bags: `{len(report['source_assets'].get('planning_bags') or [])}`",
        f"- Trajectory CSV: `{report['source_assets'].get('trajectory_csv')}`",
        "",
        "## Real Dynamics Targets",
        "",
        f"- Speed p95: `{recommendation.get('real_speed_p95_mps')}` m/s",
        f"- Speed p99: `{recommendation.get('real_speed_p99_mps')}` m/s",
        f"- Deceleration p95: `{recommendation.get('real_decel_p95_mps2')}` m/s^2",
        f"- Yaw-rate p95: `{recommendation.get('real_yaw_rate_p95_radps')}` rad/s",
        f"- Target CARLA speed envelope: `{recommendation.get('target_speed_mps')}` m/s",
        "",
        "## Suggested Stable Runtime Overrides",
        "",
    ]
    for key, item in recommendation["stable_runtime_overrides"].items():
        lines.append(f"- `{key}`: `{item['current']}` -> `{item['suggested']}`; {item['reason']}")
    if planning_control.get("available"):
        lines.extend(
            [
                "",
                "## Planning Control Evidence",
                "",
                f"- Target velocity p95: `{planning_control.get('control_target_velocity_p95_mps')}` m/s",
                f"- Vehicle speed p95: `{planning_control.get('vehicle_speed_p95_mps')}` m/s",
                f"- Actuation brake cmd p95/max: `{planning_control.get('actuation_brake_cmd_p95')}` / `{planning_control.get('actuation_brake_cmd_max')}`",
                f"- CARLA brake at p95 cmd, current/suggested: `{planning_control.get('current_carla_brake_at_p95_cmd')}` / `{planning_control.get('suggested_carla_brake_at_p95_cmd')}`",
                f"- Steering cmd/status max abs: `{planning_control.get('actuation_steer_cmd_max_abs_rad')}` / `{planning_control.get('steering_feedback_max_abs_rad')}` rad",
                f"- Decision: {planning_control.get('decision')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Validation Plan",
            "",
            "1. Re-run the CARLA direct vehicle dynamics probe with the suggested overrides and compare max speed, acceleration, and deceleration against this report.",
            "2. Re-run the qiyu route smoke with the same overrides and inspect lateral error, route completion, collision count, and final speed near goal.",
            "3. Treat this as CARLA/bridge physics calibration only until `run_result -> KPI gate -> report -> replay` is finalized on the Ubuntu host.",
            "",
            "## Limitations",
            "",
        ]
    )
    for item in report.get("limitations", []):
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_env(path: Path, overrides: dict[str, Any]) -> None:
    env_names = {
        "pix_carla_throttle_gain": "PIX_CARLA_THROTTLE_GAIN",
        "pix_carla_max_throttle": "PIX_CARLA_MAX_THROTTLE",
        "pix_carla_brake_gain": "PIX_CARLA_BRAKE_GAIN",
        "pix_carla_max_brake": "PIX_CARLA_MAX_BRAKE",
        "pix_carla_steer_gain": "PIX_CARLA_STEER_GAIN",
    }
    lines = [
        "# Generated by tools/calibrate_robobus_physics_from_bag.py",
        "# Source these values only for qiyu Robobus calibration runs, not global stable acceptance.",
    ]
    for key, env_name in env_names.items():
        if key in overrides:
            lines.append(f"export {env_name}={overrides[key]['suggested']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    metadata_topics = load_metadata_topics(args.metadata)
    trajectory_summary = summarize_trajectory(load_trajectory_csv(args.trajectory_csv))
    bag_extract = extract_rosbag_samples(
        args.bag,
        tuple(args.topic),
        args.sample_period_sec,
        args.max_messages_per_topic,
    )
    bag_summary = summarize_bag_samples(bag_extract.get("samples", {}))
    planning_extract = extract_mcap_ros2_samples(
        args.planning_bag or [],
        tuple(args.planning_topic),
        args.sample_period_sec,
        args.max_messages_per_topic,
    )
    planning_summary = summarize_bag_samples(planning_extract.get("samples", {}))
    dynamics_summary = dict(bag_summary)
    dynamics_summary.update(planning_summary)
    if trajectory_summary.get("available"):
        dynamics_summary["trajectory"] = trajectory_summary
    recommendation = suggest_runtime_overrides(
        dynamics_summary,
        args.current_carla_max_speed_mps,
        args.current_pix_carla_throttle_gain,
        args.current_pix_carla_max_throttle,
        args.current_pix_carla_brake_gain,
        args.current_pix_carla_max_brake,
        args.current_pix_carla_steer_gain,
    )
    planning_control_analysis = analyze_planning_control(
        dynamics_summary,
        args.current_pix_carla_brake_gain,
        args.current_pix_carla_max_brake,
        recommendation,
    )
    status = "ready_for_carla_physics_probe"
    if not bag_extract.get("available") and not planning_extract.get("available") and not trajectory_summary.get("available"):
        status = "blocked_no_dynamics_source"
    elif not bag_extract.get("available") and not planning_extract.get("available"):
        status = "trajectory_only_needs_rosbag_extraction"
    limitations = [
        "The planning MCAP carries control, actuation, steering, and velocity evidence, but route-level acceptance still needs CARLA closed-loop replay.",
        "Throttle, brake, and steering suggestions are first-pass bridge/runtime knobs; CARLA UE vehicle physics still needs a step-response probe before permanent asset changes.",
        "Mac/local execution cannot prove stable closed-loop acceptance; the qiyu validation must finalize on the Ubuntu runtime host.",
    ]
    return round_nested(
        {
            "generated_at": utc_now(),
            "status": status,
            "source_assets": {
                "bag": str(args.bag) if args.bag else None,
                "planning_bags": [str(path) for path in (args.planning_bag or [])],
                "metadata": str(args.metadata) if args.metadata else None,
                "trajectory_csv": str(args.trajectory_csv) if args.trajectory_csv else None,
            },
            "selected_topics": list(args.topic),
            "metadata_topics": {topic: metadata_topics.get(topic) for topic in args.topic},
            "bag_extract": {
                "available": bag_extract.get("available"),
                "blocked_reason": bag_extract.get("blocked_reason"),
                "sample_period_sec": bag_extract.get("sample_period_sec"),
                "max_messages_per_topic": bag_extract.get("max_messages_per_topic"),
                "errors": bag_extract.get("errors", {}),
            },
            "planning_extract": {
                "available": planning_extract.get("available"),
                "blocked_reason": planning_extract.get("blocked_reason"),
                "sample_period_sec": planning_extract.get("sample_period_sec"),
                "max_messages_per_topic": planning_extract.get("max_messages_per_topic"),
                "paths": planning_extract.get("paths", []),
                "errors": planning_extract.get("errors", {}),
            },
            "bag_dynamics": bag_summary,
            "planning_dynamics": planning_summary,
            "trajectory_dynamics": trajectory_summary,
            "current_carla_reference": {
                "max_speed_mps": args.current_carla_max_speed_mps,
                "pix_carla_throttle_gain": args.current_pix_carla_throttle_gain,
                "pix_carla_max_throttle": args.current_pix_carla_max_throttle,
                "pix_carla_brake_gain": args.current_pix_carla_brake_gain,
                "pix_carla_max_brake": args.current_pix_carla_max_brake,
                "pix_carla_steer_gain": args.current_pix_carla_steer_gain,
            },
            "recommendation": recommendation,
            "planning_control_analysis": planning_control_analysis,
            "limitations": limitations,
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag", type=Path, help="ROS 2 bag directory to read on the Ubuntu host")
    parser.add_argument("--planning-bag", action="append", type=Path, help="planning MCAP or MCAP.zst file")
    parser.add_argument("--metadata", type=Path, help="bag metadata.yaml")
    parser.add_argument("--trajectory-csv", type=Path, help="trajectory_samples.csv extracted from the same run")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--topic", action="append", default=list(DEFAULT_TOPICS))
    parser.add_argument("--planning-topic", action="append", default=list(DEFAULT_PLANNING_TOPICS))
    parser.add_argument("--sample-period-sec", type=float, default=0.20)
    parser.add_argument("--max-messages-per-topic", type=int, default=8000)
    parser.add_argument("--current-carla-max-speed-mps", type=float, default=None)
    parser.add_argument("--current-pix-carla-throttle-gain", type=float, default=3.8)
    parser.add_argument("--current-pix-carla-max-throttle", type=float, default=1.0)
    parser.add_argument("--current-pix-carla-brake-gain", type=float, default=0.2)
    parser.add_argument("--current-pix-carla-max-brake", type=float, default=0.8)
    parser.add_argument("--current-pix-carla-steer-gain", type=float, default=0.90)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    report_path = args.output_dir / "robobus_physics_calibration_report.json"
    markdown_path = args.output_dir / "robobus_physics_calibration_report.md"
    env_path = args.output_dir / "robobus_physics_calibration_overrides.env"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(markdown_path, report)
    write_env(env_path, report["recommendation"]["stable_runtime_overrides"])
    print(json.dumps({"report": str(report_path), "markdown": str(markdown_path), "env": str(env_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
