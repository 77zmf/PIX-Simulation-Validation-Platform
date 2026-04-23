#!/usr/bin/env python3
"""Run an L0 CARLA + Autoware closed-loop route probe.

This probe is intentionally host-side. Run it on the Ubuntu runtime host after
`simctl run --execute` has started CARLA, the CARLA bridge, and Autoware. It
initializes localization, sets a route, engages autonomous mode, samples the
CARLA ego actor, and writes `closed_loop_route_sync_*.json` under
`<run-dir>/runtime_verification/` for `simctl finalize`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from carla_dynamic_actor_probe import (
    CameraVideoRecorder,
    apply_spectator_view,
    pose_yaml,
    route_yaml,
    run_cmd,
    sample_actor,
    spectator_transform_params,
    wait_for_ego,
)


DEFAULT_START_MAP = {
    "x": 229.78167724609375,
    "y": -2.0201120376586914,
    "z": 0.0,
    "yaw": 0.0,
}
DEFAULT_GOAL_MAP = {
    "x": 314.2434997558594,
    "y": -1.982629656791687,
    "z": 0.0,
    "yaw_deg": -0.03045654296875,
}
GOAL_DISTANCE_TOLERANCE_M = 8.0
TOPIC_SAMPLE_TIMEOUT_SEC = 5
CONTROL_TAIL_SAMPLE_COUNT = 50


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def tail(text: str | bytes | None, limit: int = 1600) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return text[-limit:]


def load_carla_module() -> Any:
    try:
        import carla  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Missing CARLA Python module. Run this on the Ubuntu runtime host "
            "with CARLA PythonAPI on PYTHONPATH."
        ) from exc
    return carla


class RosTelemetryCollector:
    """Collect lightweight ROS telemetry while CARLA samples are recorded.

    The collector is best-effort: if ROS Python modules or message packages are
    unavailable, route probing still runs and records the import error.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = False
        self.error: str | None = None
        self.latest: dict[str, dict[str, Any]] = {}
        self.counts: dict[str, int] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._rclpy: Any = None
        self._context: Any = None
        self._node: Any = None
        self._executor: Any = None
        if not enabled:
            self.error = "disabled"
            return
        try:
            import rclpy  # type: ignore[import-not-found]
            from rclpy.context import Context  # type: ignore[import-not-found]
            from rclpy.executors import SingleThreadedExecutor  # type: ignore[import-not-found]
            from rclpy.node import Node  # type: ignore[import-not-found]

            from autoware_control_msgs.msg import Control  # type: ignore[import-not-found]
            from autoware_planning_msgs.msg import LaneletRoute  # type: ignore[import-not-found]
            from autoware_planning_msgs.msg import Trajectory  # type: ignore[import-not-found]
            from autoware_vehicle_msgs.msg import SteeringReport  # type: ignore[import-not-found]
            from autoware_vehicle_msgs.msg import VelocityReport  # type: ignore[import-not-found]
            from nav_msgs.msg import Odometry  # type: ignore[import-not-found]
            from tier4_vehicle_msgs.msg import ActuationCommandStamped  # type: ignore[import-not-found]
            from tier4_vehicle_msgs.msg import ActuationStatusStamped  # type: ignore[import-not-found]
        except Exception as exc:
            self.error = f"ros_telemetry_import_failed: {exc}"
            return

        try:
            self._rclpy = rclpy
            self._context = Context()
            rclpy.init(args=None, context=self._context)
            self._node = Node(f"simctl_route_probe_telemetry_{os.getpid()}", context=self._context)
            self._executor = SingleThreadedExecutor(context=self._context)
            self._executor.add_node(self._node)
            subscriptions = (
                ("/planning/mission_planning/route", LaneletRoute, self._on_route),
                ("/planning/scenario_planning/trajectory", Trajectory, self._on_trajectory),
                ("/control/command/control_cmd", Control, self._on_control_cmd),
                ("/control/command/actuation_cmd", ActuationCommandStamped, self._on_actuation_cmd),
                ("/vehicle/status/actuation_status", ActuationStatusStamped, self._on_actuation_status),
                ("/vehicle/status/steering_status", SteeringReport, self._on_steering_status),
                ("/vehicle/status/velocity_status", VelocityReport, self._on_velocity_status),
                ("/localization/kinematic_state", Odometry, self._on_localization),
            )
            for topic, msg_type, callback in subscriptions:
                self._node.create_subscription(msg_type, topic, callback, 10)
                self.counts[self._key_for_topic(topic)] = 0
            self._thread = threading.Thread(target=self._executor.spin, daemon=True)
            self._thread.start()
            self.enabled = True
        except Exception as exc:
            self.error = f"ros_telemetry_start_failed: {exc}"
            self.shutdown()

    def _key_for_topic(self, topic: str) -> str:
        return topic.strip("/").split("/")[-1].replace("-", "_")

    def _record(self, key: str, payload: dict[str, Any]) -> None:
        payload = {"received_wall_time": time.time(), **payload}
        with self._lock:
            self.latest[key] = payload
            self.counts[key] = self.counts.get(key, 0) + 1

    def _stamp(self, msg: Any) -> float | None:
        header = getattr(msg, "header", None)
        stamp = getattr(header, "stamp", None)
        if stamp is None:
            stamp = getattr(msg, "stamp", None)
        if stamp is None:
            return None
        return float(getattr(stamp, "sec", 0)) + float(getattr(stamp, "nanosec", 0)) * 1e-9

    def _pose_payload(self, pose: Any) -> dict[str, float]:
        position = getattr(pose, "position", pose)
        return {
            "x": float(getattr(position, "x", 0.0)),
            "y": float(getattr(position, "y", 0.0)),
            "z": float(getattr(position, "z", 0.0)),
        }

    def _on_route(self, msg: Any) -> None:
        self._record(
            "route",
            {
                "stamp": self._stamp(msg),
                "goal_pose": self._pose_payload(msg.goal_pose.position),
                "start_pose": self._pose_payload(msg.start_pose.position),
                "segment_count": len(getattr(msg, "segments", []) or []),
            },
        )

    def _trajectory_point_payload(self, point: Any) -> dict[str, Any]:
        return {
            "pose": self._pose_payload(point.pose.position),
            "longitudinal_velocity_mps": float(getattr(point, "longitudinal_velocity_mps", 0.0)),
            "acceleration_mps2": float(getattr(point, "acceleration_mps2", 0.0)),
            "front_wheel_angle_rad": float(getattr(point, "front_wheel_angle_rad", 0.0)),
        }

    def _on_trajectory(self, msg: Any) -> None:
        points = list(getattr(msg, "points", []) or [])
        payload: dict[str, Any] = {"stamp": self._stamp(msg), "point_count": len(points)}
        if points:
            payload["first_point"] = self._trajectory_point_payload(points[0])
            payload["last_point"] = self._trajectory_point_payload(points[-1])
        self._record("trajectory", payload)

    def _on_control_cmd(self, msg: Any) -> None:
        lateral = getattr(msg, "lateral", None)
        longitudinal = getattr(msg, "longitudinal", None)
        self._record(
            "control_cmd",
            {
                "stamp": self._stamp(msg),
                "steering_tire_angle": float(getattr(lateral, "steering_tire_angle", 0.0)),
                "steering_tire_rotation_rate": float(getattr(lateral, "steering_tire_rotation_rate", 0.0)),
                "velocity_mps": float(getattr(longitudinal, "velocity", 0.0)),
                "acceleration_mps2": float(getattr(longitudinal, "acceleration", 0.0)),
                "jerk_mps3": float(getattr(longitudinal, "jerk", 0.0)),
            },
        )

    def _on_actuation_cmd(self, msg: Any) -> None:
        actuation = getattr(msg, "actuation", None)
        self._record(
            "actuation_cmd",
            {
                "stamp": self._stamp(msg),
                "accel_cmd": float(getattr(actuation, "accel_cmd", 0.0)),
                "brake_cmd": float(getattr(actuation, "brake_cmd", 0.0)),
                "steer_cmd": float(getattr(actuation, "steer_cmd", 0.0)),
            },
        )

    def _on_actuation_status(self, msg: Any) -> None:
        status = getattr(msg, "status", None)
        self._record(
            "actuation_status",
            {
                "stamp": self._stamp(msg),
                "accel_status": float(getattr(status, "accel_status", 0.0)),
                "brake_status": float(getattr(status, "brake_status", 0.0)),
                "steer_status": float(getattr(status, "steer_status", 0.0)),
            },
        )

    def _on_steering_status(self, msg: Any) -> None:
        self._record(
            "steering_status",
            {
                "stamp": self._stamp(msg),
                "steering_tire_angle": float(getattr(msg, "steering_tire_angle", 0.0)),
            },
        )

    def _on_velocity_status(self, msg: Any) -> None:
        self._record(
            "velocity_status",
            {
                "stamp": self._stamp(msg),
                "longitudinal_velocity_mps": float(getattr(msg, "longitudinal_velocity", 0.0)),
                "lateral_velocity_mps": float(getattr(msg, "lateral_velocity", 0.0)),
                "heading_rate_rps": float(getattr(msg, "heading_rate", 0.0)),
            },
        )

    def _on_localization(self, msg: Any) -> None:
        position = msg.pose.pose.position
        twist = msg.twist.twist
        self._record(
            "localization",
            {
                "stamp": self._stamp(msg),
                "pose": {
                    "x": float(position.x),
                    "y": float(position.y),
                    "z": float(position.z),
                },
                "twist": {
                    "linear_x_mps": float(twist.linear.x),
                    "linear_y_mps": float(twist.linear.y),
                    "angular_z_rps": float(twist.angular.z),
                },
            },
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "latest": {key: dict(value) for key, value in self.latest.items()},
                "counts": dict(self.counts),
                "enabled": self.enabled,
                "error": self.error,
            }

    def sample_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {key: dict(value) for key, value in self.latest.items()}

    def effective_goal_map(self) -> dict[str, float] | None:
        with self._lock:
            route = self.latest.get("route")
            goal = route.get("goal_pose") if route else None
        if not isinstance(goal, dict):
            return None
        return {
            "x": float(goal.get("x", 0.0)),
            "y": float(goal.get("y", 0.0)),
            "z": float(goal.get("z", 0.0)),
            "yaw": 0.0,
            "yaw_deg": 0.0,
        }

    def shutdown(self) -> None:
        try:
            if self._executor is not None:
                self._executor.shutdown()
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        try:
            if self._node is not None:
                self._node.destroy_node()
        except Exception:
            pass
        try:
            if self._rclpy is not None and self._context is not None:
                self._rclpy.shutdown(context=self._context)
        except Exception:
            pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return payload if isinstance(payload, dict) else {}


def pose_from_payload(payload: dict[str, Any], key: str, fallback: dict[str, float]) -> dict[str, float]:
    pose = payload.get(key)
    if isinstance(pose, dict) and isinstance(pose.get("pose"), dict):
        pose = pose["pose"]
    if not isinstance(pose, dict):
        return dict(fallback)
    return {
        "x": float(pose.get("x", fallback["x"])),
        "y": float(pose.get("y", fallback["y"])),
        "z": float(pose.get("z", fallback.get("z", 0.0))),
        "yaw": float(pose.get("yaw_deg", pose.get("yaw", fallback.get("yaw", fallback.get("yaw_deg", 0.0))))),
        "yaw_deg": float(pose.get("yaw_deg", pose.get("yaw", fallback.get("yaw_deg", fallback.get("yaw", 0.0))))),
    }


def scenario_payload(run_dir: Path, explicit_scenario: str | None) -> dict[str, Any]:
    run_result = load_json(run_dir / "run_result.json")
    scenario_path = explicit_scenario or str(run_result.get("scenario_path") or "")
    scenario = load_yaml(Path(scenario_path)) if scenario_path else {}
    if scenario:
        return scenario
    params = run_result.get("scenario_params")
    return params if isinstance(params, dict) else {}


def carla_pose_from_map_pose(map_pose: dict[str, float], z_offset: float) -> dict[str, float]:
    return {
        "x": float(map_pose["x"]),
        "y": -float(map_pose["y"]),
        "z": float(map_pose.get("z", 0.0)) + z_offset,
        "yaw": float(map_pose.get("yaw_deg", map_pose.get("yaw", 0.0))),
    }


def distance_to_goal_m(carla_location: dict[str, Any], goal_map: dict[str, float]) -> float:
    direct = math.hypot(float(carla_location["x"]) - goal_map["x"], float(carla_location["y"]) - goal_map["y"])
    flipped = math.hypot(float(carla_location["x"]) - goal_map["x"], float(carla_location["y"]) + goal_map["y"])
    return min(direct, flipped)


def carla_waypoint_context(world: Any, carla: Any, ego_sample: dict[str, Any]) -> dict[str, Any] | None:
    try:
        waypoint = world.get_map().get_waypoint(
            carla.Location(
                x=float(ego_sample["x"]),
                y=float(ego_sample["y"]),
                z=float(ego_sample.get("z", 0.0)),
            ),
            project_to_road=True,
            lane_type=carla.LaneType.Driving,
        )
    except Exception:
        return None
    if waypoint is None:
        return None
    transform = waypoint.transform
    location = transform.location
    ego_x = float(ego_sample["x"])
    ego_y = float(ego_sample["y"])
    carla_lateral_error_m = math.hypot(ego_x - float(location.x), ego_y - float(location.y))
    return {
        "road_id": int(getattr(waypoint, "road_id", 0)),
        "section_id": int(getattr(waypoint, "section_id", 0)),
        "lane_id": int(getattr(waypoint, "lane_id", 0)),
        "s": float(getattr(waypoint, "s", 0.0)),
        "lane_width_m": float(getattr(waypoint, "lane_width", 0.0)),
        "center_carla": {
            "x": float(location.x),
            "y": float(location.y),
            "z": float(location.z),
            "yaw": float(transform.rotation.yaw),
        },
        "center_map": {
            "x": float(location.x),
            "y": -float(location.y),
            "z": float(location.z),
            "yaw": float(transform.rotation.yaw),
        },
        "carla_lateral_error_m": carla_lateral_error_m,
    }


def call_topic_echo(topic: str, env: dict[str, str], field: str | None = None) -> dict[str, Any]:
    command = [
        "timeout",
        str(TOPIC_SAMPLE_TIMEOUT_SEC),
        "ros2",
        "topic",
        "echo",
        "--once",
        "--spin-time",
        "1",
        "--truncate-length",
        "160",
        "--flow-style",
    ]
    if field:
        command.extend(["--field", field])
    command.append(topic)
    try:
        completed = subprocess.run(
            command,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=TOPIC_SAMPLE_TIMEOUT_SEC + 2,
        )
        return {
            "topic": topic,
            "field": field,
            "returncode": completed.returncode,
            "sample_received": completed.returncode == 0 and bool(completed.stdout.strip()),
            "output_tail": tail(completed.stdout),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "topic": topic,
            "field": field,
            "returncode": 124,
            "sample_received": False,
            "output_tail": tail((exc.stdout or "") + (exc.stderr or "")),
        }


def service_call_successful(service_calls: list[dict[str, Any]]) -> bool:
    for call in service_calls:
        if call.get("returncode") not in (None, 0):
            return False
        output = str(call.get("output") or "")
        if re.search(r"\bsuccess\s*[:=]\s*False\b", output, flags=re.IGNORECASE):
            return False
    return True


def required_service_call_successful(service_calls: list[dict[str, Any]], required_steps: set[str]) -> bool:
    matched_calls = [call for call in service_calls if str(call.get("step") or "") in required_steps]
    matched_steps = {str(call.get("step") or "") for call in matched_calls}
    if not required_steps.issubset(matched_steps):
        return False
    return service_call_successful(matched_calls)


def ego_sample_to_map_xy(sample: dict[str, Any]) -> tuple[float, float]:
    return (float(sample["x"]), -float(sample["y"]))


def abs_jerk_samples_mps3(samples: list[dict[str, Any]]) -> list[float]:
    acceleration_samples: list[tuple[float, float]] = []
    for previous, current in zip(samples, samples[1:]):
        previous_t = float(previous.get("t", 0.0))
        current_t = float(current.get("t", 0.0))
        dt = current_t - previous_t
        if dt <= 0.0:
            continue
        previous_speed = float(previous["ego"].get("speed_mps", 0.0))
        current_speed = float(current["ego"].get("speed_mps", 0.0))
        acceleration_samples.append((current_t, (current_speed - previous_speed) / dt))

    jerk_samples: list[float] = []
    for previous, current in zip(acceleration_samples, acceleration_samples[1:]):
        dt = current[0] - previous[0]
        if dt <= 0.0:
            continue
        jerk_samples.append(abs((current[1] - previous[1]) / dt))
    return jerk_samples


def percentile_value(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    clamped = min(max(percentile, 0.0), 1.0)
    index = int(round((len(sorted_values) - 1) * clamped))
    return sorted_values[index]


def max_abs_jerk_mps3(samples: list[dict[str, Any]]) -> float:
    jerk_samples = abs_jerk_samples_mps3(samples)
    return max(jerk_samples) if jerk_samples else 0.0


def robust_abs_jerk_mps3(samples: list[dict[str, Any]]) -> float:
    # CARLA actor speed has occasional one-sample quantization spikes; p90 keeps
    # the comfort gate deterministic without allowing sustained harsh motion.
    return percentile_value(abs_jerk_samples_mps3(samples), 0.90)


def nested_value(payload: dict[str, Any], path: tuple[str, ...]) -> float | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    try:
        return float(current)
    except (TypeError, ValueError):
        return None


def numeric_tail_stats(samples: list[dict[str, Any]], topic: str, path: tuple[str, ...]) -> dict[str, float] | None:
    values: list[float] = []
    tail_samples = samples[-CONTROL_TAIL_SAMPLE_COUNT:]
    for sample in tail_samples:
        telemetry = sample.get("ros_telemetry")
        if not isinstance(telemetry, dict):
            continue
        topic_payload = telemetry.get(topic)
        if not isinstance(topic_payload, dict):
            continue
        value = nested_value(topic_payload, path)
        if value is not None:
            values.append(value)
    if not values:
        return None
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "sample_count": float(len(values)),
    }


def summarize_ros_control_telemetry(
    samples: list[dict[str, Any]],
    telemetry_snapshot: dict[str, Any],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "enabled": bool(telemetry_snapshot.get("enabled")),
        "error": telemetry_snapshot.get("error"),
        "topic_counts": telemetry_snapshot.get("counts", {}),
        "latest": telemetry_snapshot.get("latest", {}),
    }
    tail_specs = {
        "tail_control_velocity_mps": ("control_cmd", ("velocity_mps",)),
        "tail_control_acceleration_mps2": ("control_cmd", ("acceleration_mps2",)),
        "tail_control_steering_tire_angle_rad": ("control_cmd", ("steering_tire_angle",)),
        "tail_actuation_accel_cmd": ("actuation_cmd", ("accel_cmd",)),
        "tail_actuation_brake_cmd": ("actuation_cmd", ("brake_cmd",)),
        "tail_actuation_steer_cmd": ("actuation_cmd", ("steer_cmd",)),
        "tail_status_accel": ("actuation_status", ("accel_status",)),
        "tail_status_brake": ("actuation_status", ("brake_status",)),
        "tail_status_steer": ("actuation_status", ("steer_status",)),
        "tail_vehicle_velocity_mps": ("velocity_status", ("longitudinal_velocity_mps",)),
        "tail_vehicle_steering_tire_angle_rad": ("steering_status", ("steering_tire_angle",)),
    }
    tail_stats: dict[str, dict[str, float]] = {}
    for output_name, (topic, path) in tail_specs.items():
        stats = numeric_tail_stats(samples, topic, path)
        if stats is not None:
            tail_stats[output_name] = stats
    summary["tail_stats"] = tail_stats
    return summary


def setup_route(
    env: dict[str, str],
    start_map: dict[str, float],
    goal_map: dict[str, float],
    calls: list[dict[str, Any]],
    *,
    allow_goal_modification: bool = True,
) -> None:
    run_cmd(
        "engage_false",
        ["timeout", "15", "ros2", "service", "call", "/api/autoware/set/engage", "tier4_external_api_msgs/srv/Engage", "{engage: false}"],
        env,
        calls,
        18,
    )
    run_cmd(
        "clear_route",
        ["timeout", "15", "ros2", "service", "call", "/api/routing/clear_route", "autoware_adapi_v1_msgs/srv/ClearRoute", "{}"],
        env,
        calls,
        18,
    )
    run_cmd(
        "change_to_stop",
        ["timeout", "15", "ros2", "service", "call", "/api/operation_mode/change_to_stop", "autoware_adapi_v1_msgs/srv/ChangeOperationMode", "{}"],
        env,
        calls,
        18,
    )
    run_cmd(
        "initialize_localization",
        ["timeout", "25", "ros2", "service", "call", "/api/localization/initialize", "autoware_adapi_v1_msgs/srv/InitializeLocalization", pose_yaml(start_map)],
        env,
        calls,
        28,
    )
    time.sleep(4.0)
    run_cmd(
        "set_route_points",
        [
            "timeout",
            "25",
            "ros2",
            "service",
            "call",
            "/api/routing/set_route_points",
            "autoware_adapi_v1_msgs/srv/SetRoutePoints",
            route_yaml(goal_map, allow_goal_modification=allow_goal_modification),
        ],
        env,
        calls,
        28,
    )
    time.sleep(2.0)
    run_cmd(
        "enable_autoware_control",
        ["timeout", "15", "ros2", "service", "call", "/api/operation_mode/enable_autoware_control", "autoware_adapi_v1_msgs/srv/ChangeOperationMode", "{}"],
        env,
        calls,
        18,
    )
    run_cmd(
        "change_to_autonomous",
        ["timeout", "25", "ros2", "service", "call", "/api/operation_mode/change_to_autonomous", "autoware_adapi_v1_msgs/srv/ChangeOperationMode", "{}"],
        env,
        calls,
        28,
    )
    run_cmd(
        "engage_true",
        ["timeout", "15", "ros2", "service", "call", "/api/autoware/set/engage", "tier4_external_api_msgs/srv/Engage", "{engage: true}"],
        env,
        calls,
        18,
    )


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    carla = load_carla_module()
    run_dir = Path(args.run_dir).resolve()
    payload = scenario_payload(run_dir, args.scenario)
    start_map = pose_from_payload(payload, "ego_init", DEFAULT_START_MAP)
    goal_map = pose_from_payload(payload, "goal", DEFAULT_GOAL_MAP)
    start_carla = carla_pose_from_map_pose(start_map, args.carla_z_offset)
    stamp = utc_stamp()
    output_dir = run_dir / "runtime_verification"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"closed_loop_route_sync_{stamp}.json"
    summary_path = output_dir / "closed_loop_route_sync_summary.json"

    env = os.environ.copy()
    env["ROS_DOMAIN_ID"] = str(args.ros_domain_id)
    env["RMW_IMPLEMENTATION"] = args.rmw_implementation
    os.environ["ROS_DOMAIN_ID"] = env["ROS_DOMAIN_ID"]
    os.environ["RMW_IMPLEMENTATION"] = env["RMW_IMPLEMENTATION"]

    service_calls: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    topic_samples: list[dict[str, Any]] = []
    video_recorder: CameraVideoRecorder | None = None
    last_spectator_view: dict[str, float] | None = None
    last_camera_view: dict[str, float] | None = None
    telemetry = RosTelemetryCollector(enabled=not args.disable_ros_telemetry)

    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(args.carla_timeout)
    world, ego = wait_for_ego(client, timeout_sec=args.ego_timeout)
    ego.set_transform(
        carla.Transform(
            carla.Location(x=start_carla["x"], y=start_carla["y"], z=start_carla["z"]),
            carla.Rotation(yaw=start_carla["yaw"]),
        )
    )
    ego.set_target_velocity(carla.Vector3D(0, 0, 0))
    ego.set_target_angular_velocity(carla.Vector3D(0, 0, 0))
    ego.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))
    time.sleep(1.0)

    bp_lib = world.get_blueprint_library()
    video_error = None
    if args.camera_video_output:
        try:
            initial_sample = sample_actor(ego)
            initial_view = spectator_transform_params(args.camera_video_mode, initial_sample, [])
            if initial_view is not None:
                video_recorder = CameraVideoRecorder(
                    output_path=Path(args.camera_video_output).resolve(),
                    width=args.camera_video_width,
                    height=args.camera_video_height,
                    fps=args.camera_video_fps,
                )
                video_recorder.start(world=world, carla=carla, blueprint_library=bp_lib, transform_params=initial_view)
                last_camera_view = initial_view
        except Exception as exc:  # Video evidence must not mask route/control failures.
            video_error = str(exc)
            video_recorder = None

    try:
        setup_route(
            env,
            start_map,
            goal_map,
            service_calls,
            allow_goal_modification=not args.disable_goal_modification,
        )
        start_t = time.time()
        reached_near_goal = False
        min_goal_distance_m = math.inf
        max_speed_mps = 0.0
        sample_period = args.sample_period
        max_samples = max(1, int(args.max_duration_sec / sample_period))
        for index in range(max_samples):
            elapsed = time.time() - start_t
            ego_sample = sample_actor(ego)
            effective_goal_map = telemetry.effective_goal_map() or goal_map
            goal_distance = distance_to_goal_m(ego_sample, effective_goal_map)
            reached_near_goal = reached_near_goal or goal_distance <= args.goal_tolerance_m
            min_goal_distance_m = min(min_goal_distance_m, goal_distance)
            max_speed_mps = max(max_speed_mps, float(ego_sample["speed_mps"]))
            if args.spectator_mode != "none":
                last_spectator_view = apply_spectator_view(
                    world=world,
                    carla=carla,
                    mode=args.spectator_mode,
                    ego_sample=ego_sample,
                    target_samples=[],
                )
            if video_recorder is not None:
                camera_view = spectator_transform_params(args.camera_video_mode, ego_sample, [])
                if camera_view is not None:
                    video_recorder.set_transform(carla=carla, transform_params=camera_view)
                    last_camera_view = camera_view
                video_recorder.drain()
            sample_record = {
                "i": index,
                "t": elapsed,
                "frame": world.get_snapshot().frame,
                "ego": ego_sample,
                "goal_distance_m": goal_distance,
                "effective_goal": effective_goal_map,
            }
            lane_context = carla_waypoint_context(world, carla, ego_sample)
            if lane_context is not None:
                sample_record["carla_waypoint"] = lane_context
            ros_sample = telemetry.sample_snapshot()
            if ros_sample:
                sample_record["ros_telemetry"] = ros_sample
            samples.append(sample_record)
            if reached_near_goal and elapsed >= args.min_duration_sec:
                break
            time.sleep(sample_period)

        if video_recorder is not None:
            video_recorder.drain()

        for topic, field in (
            ("/planning/mission_planning/route", None),
            ("/planning/scenario_planning/trajectory", None),
            ("/control/command/control_cmd", None),
            ("/control/command/actuation_cmd", None),
            ("/vehicle/status/steering_status", None),
            ("/vehicle/status/velocity_status", None),
            ("/localization/kinematic_state", None),
            ("/api/operation_mode/state", None),
            ("/autoware/state", None),
        ):
            topic_samples.append(call_topic_echo(topic, env, field))

        total_delta_m = 0.0
        if len(samples) > 1:
            first = samples[0]["ego"]
            last = samples[-1]["ego"]
            total_delta_m = math.hypot(float(last["x"]) - float(first["x"]), float(last["y"]) - float(first["y"]))
        last_location = samples[-1]["ego"] if samples else None
        moved = total_delta_m > args.min_delta_m or max_speed_mps > args.min_speed_mps
        all_service_calls_successful = service_call_successful(service_calls)
        route_required_steps = {"initialize_localization", "set_route_points"}
        route_valid = required_service_call_successful(service_calls, route_required_steps)
        final_map_location = None
        lateral_error_m = None
        route_goal_lateral_error_m = None
        longitudinal_error_m = None
        final_carla_waypoint = None
        final_effective_goal_map = telemetry.effective_goal_map() or goal_map
        if last_location is not None:
            final_map_x, final_map_y = ego_sample_to_map_xy(last_location)
            final_map_location = {
                "x": final_map_x,
                "y": final_map_y,
                "z": float(last_location.get("z", 0.0)),
                "yaw": float(last_location.get("yaw", 0.0)),
            }
            route_goal_lateral_error_m = abs(final_map_y - float(final_effective_goal_map["y"]))
            longitudinal_error_m = abs(float(final_effective_goal_map["x"]) - final_map_x)
            final_carla_waypoint = carla_waypoint_context(world, carla, last_location)
            if final_carla_waypoint is not None:
                lateral_error_m = float(final_carla_waypoint["carla_lateral_error_m"])
            else:
                lateral_error_m = route_goal_lateral_error_m
        ros_telemetry = summarize_ros_control_telemetry(samples, telemetry.snapshot())
        max_jerk_mps3 = max_abs_jerk_mps3(samples)
        summary = {
            "sample_count": len(samples),
            "moved": moved,
            "total_delta_m": total_delta_m,
            "max_speed_mps": max_speed_mps,
            "requested_goal": goal_map,
            "effective_goal": final_effective_goal_map,
            "last_location": last_location,
            "final_map_location": final_map_location,
            "final_carla_waypoint": final_carla_waypoint,
            "min_goal_distance_m": min_goal_distance_m if math.isfinite(min_goal_distance_m) else None,
            "lateral_error_m": lateral_error_m,
            "route_goal_lateral_error_m": route_goal_lateral_error_m,
            "longitudinal_error_m": longitudinal_error_m,
            "jerk_mps3": robust_abs_jerk_mps3(samples),
            "max_jerk_mps3": max_jerk_mps3,
            "stopped_before_goal": bool(
                last_location is not None
                and float(last_location.get("speed_mps", 0.0)) <= args.min_speed_mps
                and not reached_near_goal
            ),
            "reached_near_goal": reached_near_goal,
            "route_service_calls_successful": route_valid,
            "all_service_calls_successful": all_service_calls_successful,
            "route_required_service_steps": sorted(route_required_steps),
            "route_goal_modification_allowed": not args.disable_goal_modification,
            "topic_sample_count": len(topic_samples),
            "topic_samples_received": sum(1 for item in topic_samples if item.get("sample_received")),
            "ros_telemetry": ros_telemetry,
            "last_spectator_view": last_spectator_view,
            "camera_video": {
                "path": str(video_recorder.output_path) if video_recorder is not None else args.camera_video_output,
                "mode": args.camera_video_mode if args.camera_video_output else None,
                "width": args.camera_video_width if args.camera_video_output else None,
                "height": args.camera_video_height if args.camera_video_output else None,
                "fps": args.camera_video_fps if args.camera_video_output else None,
                "frames_written": video_recorder.frames_written if video_recorder is not None else 0,
                "frames_dropped": video_recorder.frames_dropped if video_recorder is not None else 0,
                "last_camera_view": last_camera_view,
                "error": video_error,
            },
        }
        result = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "classification": "l0_closed_loop_route_sync",
            "run_dir": str(run_dir),
            "start": {"map": start_map, "carla": start_carla},
            "goal": goal_map,
            "service_calls": service_calls,
            "topic_samples": topic_samples,
            "samples": samples,
            "summary": summary,
            "verdict": {
                "overall_passed": route_valid and moved and reached_near_goal,
                "route_passed": route_valid and reached_near_goal,
                "movement_passed": moved,
            },
        }
        artifact_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        summary_payload = {
            **result["verdict"],
            "summary": summary,
            "artifact": str(artifact_path),
            "camera_video": summary["camera_video"],
        }
        summary_path.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return summary_payload
    finally:
        try:
            run_cmd(
                "engage_false_cleanup",
                ["timeout", "15", "ros2", "service", "call", "/api/autoware/set/engage", "tier4_external_api_msgs/srv/Engage", "{engage: false}"],
                env,
                service_calls,
                18,
            )
            run_cmd(
                "change_to_stop_cleanup",
                ["timeout", "15", "ros2", "service", "call", "/api/operation_mode/change_to_stop", "autoware_adapi_v1_msgs/srv/ChangeOperationMode", "{}"],
                env,
                service_calls,
                18,
            )
        except Exception as exc:
            print(f"cleanup services failed: {exc}", file=sys.stderr)
        if video_recorder is not None:
            try:
                video_recorder.close()
            except Exception as exc:
                print(f"close camera video failed: {exc}", file=sys.stderr)
        telemetry.shutdown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Existing simctl run directory on the runtime host")
    parser.add_argument("--scenario", help="Optional scenario YAML path; defaults to run_result.scenario_path")
    parser.add_argument("--ros-domain-id", type=int, default=21)
    parser.add_argument("--rmw-implementation", default="rmw_cyclonedds_cpp")
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=2000)
    parser.add_argument("--carla-timeout", type=float, default=10.0)
    parser.add_argument("--ego-timeout", type=int, default=20)
    parser.add_argument("--sample-period", type=float, default=0.2)
    parser.add_argument("--min-duration-sec", type=float, default=8.0)
    parser.add_argument("--max-duration-sec", type=float, default=80.0)
    parser.add_argument("--goal-tolerance-m", type=float, default=GOAL_DISTANCE_TOLERANCE_M)
    parser.add_argument(
        "--disable-goal-modification",
        action="store_true",
        help="Send SetRoutePoints with allow_goal_modification=false to keep the requested goal pose.",
    )
    parser.add_argument("--min-delta-m", type=float, default=5.0)
    parser.add_argument("--min-speed-mps", type=float, default=1.0)
    parser.add_argument("--carla-z-offset", type=float, default=0.08)
    parser.add_argument(
        "--spectator-mode",
        choices=["none", "ego_chase", "overview"],
        default="none",
        help="Move the CARLA spectator during the probe.",
    )
    parser.add_argument("--camera-video-output", help="Optional mp4 path for CARLA RGB camera evidence")
    parser.add_argument("--camera-video-mode", choices=["ego_chase", "overview"], default="ego_chase")
    parser.add_argument("--camera-video-width", type=int, default=1280)
    parser.add_argument("--camera-video-height", type=int, default=720)
    parser.add_argument("--camera-video-fps", type=int, default=10)
    parser.add_argument(
        "--disable-ros-telemetry",
        action="store_true",
        help="Disable best-effort ROS topic subscriptions for route/control/vehicle diagnostics.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_probe(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
