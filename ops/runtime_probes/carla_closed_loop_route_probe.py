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
OPERATION_MODE_BLOCKER_TOPIC_SPECS: tuple[tuple[str, str, str | None], ...] = (
    ("operation_mode_state", "/api/operation_mode/state", None),
    ("operation_mode_availability", "/system/operation_mode/availability", None),
    ("fail_safe_mrm_state", "/system/fail_safe/mrm_state", None),
    ("autoware_state", "/autoware/state", None),
    ("vehicle_velocity_status", "/vehicle/status/velocity_status", None),
    ("vehicle_steering_status", "/vehicle/status/steering_status", None),
    ("control_cmd", "/control/command/control_cmd", None),
    ("actuation_cmd", "/control/command/actuation_cmd", None),
    ("imu_raw", "/sensing/imu/tamagawa/imu_raw", None),
    ("diagnostics", "/diagnostics", None),
)


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value in {None, ""}:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value in {None, ""}:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def tail(text: str | bytes | None, limit: int = 1600) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return text[-limit:]


def diagnostic_level_to_int(level: Any) -> int:
    if isinstance(level, bytes):
        return level[0] if level else 0
    try:
        return int(level)
    except (TypeError, ValueError):
        return 0


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
            from diagnostic_msgs.msg import DiagnosticArray  # type: ignore[import-not-found]
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
                ("/diagnostics", DiagnosticArray, self._on_diagnostics),
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

    def _on_diagnostics(self, msg: Any) -> None:
        statuses = list(getattr(msg, "status", []) or [])
        problems: list[dict[str, Any]] = []
        max_level = 0
        for status in statuses:
            level = diagnostic_level_to_int(getattr(status, "level", 0))
            max_level = max(max_level, level)
            if level <= 0:
                continue
            values = []
            for item in list(getattr(status, "values", []) or [])[:12]:
                values.append(
                    {
                        "key": str(getattr(item, "key", "")),
                        "value": str(getattr(item, "value", "")),
                    }
                )
            problems.append(
                {
                    "name": str(getattr(status, "name", "")),
                    "level": level,
                    "message": str(getattr(status, "message", "")),
                    "hardware_id": str(getattr(status, "hardware_id", "")),
                    "values": values,
                }
            )
        self._record(
            "diagnostics",
            {
                "stamp": self._stamp(msg),
                "status_count": len(statuses),
                "problem_count": len(problems),
                "max_level": max_level,
                "problems": problems[:30],
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


def pose_from_value(value: Any, fallback: dict[str, float], *, require_xy: bool = False) -> dict[str, float] | None:
    pose = value
    if isinstance(pose, dict) and isinstance(pose.get("pose"), dict):
        pose = pose["pose"]
    if not isinstance(pose, dict):
        return None
    if require_xy and ("x" not in pose or "y" not in pose):
        return None
    return {
        "x": float(pose.get("x", fallback["x"])),
        "y": float(pose.get("y", fallback["y"])),
        "z": float(pose.get("z", fallback.get("z", 0.0))),
        "yaw": float(pose.get("yaw_deg", pose.get("yaw", fallback.get("yaw", fallback.get("yaw_deg", 0.0))))),
        "yaw_deg": float(pose.get("yaw_deg", pose.get("yaw", fallback.get("yaw_deg", fallback.get("yaw", 0.0))))),
    }


def pose_from_payload(payload: dict[str, Any], key: str, fallback: dict[str, float]) -> dict[str, float]:
    return pose_from_value(payload.get(key), fallback) or dict(fallback)


def pose_list_from_value(value: Any) -> list[dict[str, float]]:
    if not isinstance(value, list):
        return []
    poses: list[dict[str, float]] = []
    fallback = {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0, "yaw_deg": 0.0}
    for item in value:
        pose = pose_from_value(item, fallback, require_xy=True)
        if pose is None:
            continue
        poses.append(pose)
        fallback = pose
    return poses


def route_from_payload(
    payload: dict[str, Any],
    fallback_goal: dict[str, float],
) -> tuple[list[dict[str, float]], dict[str, float]]:
    route = payload.get("route")
    route_payload = route if isinstance(route, dict) else {}

    for points_value in (payload.get("route_points"), route_payload.get("points"), route_payload.get("route_points")):
        points = pose_list_from_value(points_value)
        if points:
            return points[:-1], points[-1]

    waypoint_values = (
        payload.get("route_waypoints"),
        payload.get("waypoints"),
        route_payload.get("waypoints"),
        route_payload.get("via"),
    )
    waypoints = [pose for value in waypoint_values for pose in pose_list_from_value(value)]
    goal = pose_from_value(route_payload.get("goal"), fallback_goal) or fallback_goal
    return waypoints, goal


def scenario_payload(run_dir: Path, explicit_scenario: str | None) -> dict[str, Any]:
    run_result = load_json(run_dir / "run_result.json")
    scenario_path = explicit_scenario or str(run_result.get("scenario_path") or "")
    scenario = load_yaml(Path(scenario_path)) if scenario_path else {}
    if scenario:
        return scenario
    params = run_result.get("scenario_params")
    return params if isinstance(params, dict) else {}


def carla_pose_from_map_pose(map_pose: dict[str, float], z_offset: float, y_sign: float = -1.0) -> dict[str, float]:
    return {
        "x": float(map_pose["x"]),
        "y": float(y_sign) * float(map_pose["y"]),
        "z": float(map_pose.get("z", 0.0)) + z_offset,
        "yaw": float(map_pose.get("yaw_deg", map_pose.get("yaw", 0.0))),
    }


def distance_to_goal_m(carla_location: dict[str, Any], goal_map: dict[str, float]) -> float:
    direct = math.hypot(float(carla_location["x"]) - goal_map["x"], float(carla_location["y"]) - goal_map["y"])
    flipped = math.hypot(float(carla_location["x"]) - goal_map["x"], float(carla_location["y"]) + goal_map["y"])
    return min(direct, flipped)


def point_to_segment_distance_m(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    ratio = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq
    ratio = max(0.0, min(1.0, ratio))
    closest = (start[0] + ratio * dx, start[1] + ratio * dy)
    return math.hypot(point[0] - closest[0], point[1] - closest[1])


def distance_to_goal_segment_m(
    previous_carla_location: dict[str, Any],
    current_carla_location: dict[str, Any],
    goal_map: dict[str, float],
) -> float:
    start = (float(previous_carla_location["x"]), float(previous_carla_location["y"]))
    end = (float(current_carla_location["x"]), float(current_carla_location["y"]))
    direct_goal = (float(goal_map["x"]), float(goal_map["y"]))
    flipped_goal = (float(goal_map["x"]), -float(goal_map["y"]))
    return min(
        point_to_segment_distance_m(direct_goal, start, end),
        point_to_segment_distance_m(flipped_goal, start, end),
    )


def carla_waypoint_context(
    world: Any,
    carla: Any,
    ego_sample: dict[str, Any],
    *,
    y_sign: float = -1.0,
) -> dict[str, Any] | None:
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
            "y": float(y_sign) * float(location.y),
            "z": float(location.z),
            "yaw": float(transform.rotation.yaw),
        },
        "carla_lateral_error_m": carla_lateral_error_m,
    }


def call_topic_echo(
    topic: str,
    env: dict[str, str],
    field: str | None = None,
    *,
    timeout_sec: int = TOPIC_SAMPLE_TIMEOUT_SEC,
    truncate_length: int = 160,
) -> dict[str, Any]:
    command = [
        "timeout",
        str(timeout_sec),
        "ros2",
        "topic",
        "echo",
        "--once",
        "--spin-time",
        "1",
        "--truncate-length",
        str(truncate_length),
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
            timeout=timeout_sec + 2,
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


def collect_operation_mode_blocker_snapshot(env: dict[str, str]) -> dict[str, Any]:
    """Capture the ROS boundary state that explains why autonomous mode is blocked."""
    topics: dict[str, Any] = {}
    for key, topic, field in OPERATION_MODE_BLOCKER_TOPIC_SPECS:
        topics[key] = call_topic_echo(
            topic,
            env,
            field,
            timeout_sec=3,
            truncate_length=700,
        )
    return {
        "created_wall_time": time.time(),
        "topics": topics,
    }


def service_call_successful(service_calls: list[dict[str, Any]]) -> bool:
    for call in service_calls:
        if call.get("superseded_by_success"):
            continue
        if call.get("returncode") not in (None, 0):
            return False
        output = str(call.get("output") or "")
        if re.search(r"\bsuccess\s*[:=]\s*False\b", output, flags=re.IGNORECASE):
            return False
    return True


def service_call_failure(call: dict[str, Any]) -> dict[str, Any] | None:
    if call.get("superseded_by_success"):
        return None
    step = str(call.get("step") or call.get("name") or "unknown")
    output = str(call.get("output") or "")
    rc = call.get("returncode")
    if rc not in (None, 0):
        return {
            "step": step,
            "reason": "returncode_nonzero",
            "returncode": rc,
            "message_tail": tail(output, 500),
        }
    if re.search(r"\bsuccess\s*[:=]\s*False\b", output, flags=re.IGNORECASE):
        message_match = re.search(r"message='([^']*)'", output)
        message = message_match.group(1) if message_match else ""
        return {
            "step": step,
            "reason": "service_status_false",
            "returncode": rc,
            "message": message,
            "message_tail": tail(output, 500),
        }
    return None


def run_service_cmd_with_retries(
    step: str,
    args: list[str],
    env: dict[str, str],
    calls: list[dict[str, Any]],
    *,
    timeout_sec: int = 20,
    retries: int = 1,
    retry_delay_sec: float = 2.0,
) -> dict[str, Any]:
    """Retry ROS service calls until both transport and service status succeed."""
    failed_attempts: list[dict[str, Any]] = []
    last_item: dict[str, Any] | None = None
    total_attempts = max(1, retries)
    for attempt in range(1, total_attempts + 1):
        item = run_cmd(step, args, env, calls, timeout_sec)
        item["attempt"] = attempt
        item["max_attempts"] = total_attempts
        last_item = item
        failure = service_call_failure(item)
        if failure is None:
            for failed in failed_attempts:
                failed["superseded_by_success"] = True
                failed["superseded_by_step"] = step
            return item
        item["service_failure_reason"] = failure["reason"]
        if failure.get("message"):
            item["service_failure_message"] = failure["message"]
        failed_attempts.append(item)
        if attempt < total_attempts:
            time.sleep(retry_delay_sec)
    assert last_item is not None
    return last_item


def mark_service_step_superseded(
    service_calls: list[dict[str, Any]],
    *,
    step: str,
    superseded_by_step: str,
) -> None:
    for call in service_calls:
        if str(call.get("step") or call.get("name") or "") != step:
            continue
        if service_call_failure(call) is None:
            continue
        call["superseded_by_success"] = True
        call["superseded_by_step"] = superseded_by_step


def text_indicates_true(output: str) -> bool:
    return bool(re.search(r"\b(true|True|TRUE)\b", output))


def wait_for_operation_mode_autonomous_available(
    env: dict[str, str],
    setup_checks: list[dict[str, Any]],
    *,
    timeout_sec: float,
    poll_interval_sec: float,
) -> bool:
    deadline = time.time() + max(0.0, timeout_sec)
    attempts: list[dict[str, Any]] = []
    passed = False
    while True:
        sample = call_topic_echo("/api/operation_mode/state", env, field="is_autonomous_mode_available")
        attempts.append(
            {
                "returncode": sample.get("returncode"),
                "sample_received": sample.get("sample_received"),
                "output_tail": sample.get("output_tail"),
            }
        )
        if sample.get("sample_received") and text_indicates_true(str(sample.get("output_tail") or "")):
            passed = True
            break
        if time.time() >= deadline:
            break
        time.sleep(max(0.0, poll_interval_sec))

    check = {
        "step": "wait_operation_mode_autonomous_available",
        "topic": "/api/operation_mode/state",
        "field": "is_autonomous_mode_available",
        "passed": passed,
        "timeout_sec": timeout_sec,
        "poll_interval_sec": poll_interval_sec,
        "attempt_count": len(attempts),
        "attempts": attempts[-10:],
    }
    if not passed:
        check["blocker_snapshot"] = collect_operation_mode_blocker_snapshot(env)
    setup_checks.append(check)
    return passed


def wait_for_topic_sample(
    step: str,
    topic: str,
    env: dict[str, str],
    setup_checks: list[dict[str, Any]],
    *,
    retries: int = 5,
    retry_delay_sec: float = 3.0,
) -> bool:
    attempts: list[dict[str, Any]] = []
    passed = False
    total_attempts = max(1, retries)
    for attempt in range(1, total_attempts + 1):
        sample = call_topic_echo(topic, env)
        attempts.append(
            {
                "attempt": attempt,
                "returncode": sample.get("returncode"),
                "sample_received": sample.get("sample_received"),
                "output_tail": sample.get("output_tail"),
            }
        )
        if sample.get("sample_received"):
            passed = True
            break
        if attempt < total_attempts:
            time.sleep(max(0.0, retry_delay_sec))

    setup_checks.append(
        {
            "step": step,
            "topic": topic,
            "passed": passed,
            "attempt_count": len(attempts),
            "attempts": attempts[-10:],
        }
    )
    return passed


def actor_role_name(actor: Any) -> str:
    attributes = getattr(actor, "attributes", {}) or {}
    if isinstance(attributes, dict):
        return str(attributes.get("role_name", ""))
    return ""


def actor_type_id(actor: Any) -> str:
    return str(getattr(actor, "type_id", ""))


def actor_location_payload(actor: Any) -> dict[str, float] | None:
    try:
        location = actor.get_transform().location
    except Exception:
        return None
    return {
        "x": float(getattr(location, "x", 0.0)),
        "y": float(getattr(location, "y", 0.0)),
        "z": float(getattr(location, "z", 0.0)),
    }


def is_ego_candidate(actor: Any, ego: Any) -> bool:
    actor_id = getattr(actor, "id", None)
    ego_id = getattr(ego, "id", None)
    if actor_id is not None and ego_id is not None and actor_id == ego_id:
        return True
    return actor_role_name(actor) in {"ego_vehicle", "hero", "autoware_v1"}


def clear_nearby_start_traffic(world: Any, ego: Any, radius_m: float) -> dict[str, Any]:
    """Destroy non-ego vehicles inside the ego start safety radius.

    This is opt-in and intended for dense SUMO traffic startup only. It keeps
    setup-time background traffic from physically pushing the ego before the
    route probe starts sampling.
    """
    ego_location = actor_location_payload(ego)
    if radius_m <= 0.0 or ego_location is None:
        return {
            "enabled": radius_m > 0.0,
            "radius_m": radius_m,
            "ego_location": ego_location,
            "checked_count": 0,
            "nearby_count": 0,
            "destroyed_count": 0,
            "destroyed_actors": [],
            "nearest_actor": None,
            "error": None if ego_location is not None else "missing_ego_location",
        }

    destroyed: list[dict[str, Any]] = []
    nearby: list[dict[str, Any]] = []
    checked_count = 0
    try:
        vehicles = list(world.get_actors().filter("vehicle.*"))
    except Exception as exc:
        return {
            "enabled": True,
            "radius_m": radius_m,
            "ego_location": ego_location,
            "checked_count": 0,
            "nearby_count": 0,
            "destroyed_count": 0,
            "destroyed_actors": [],
            "nearest_actor": None,
            "error": str(exc),
        }

    for actor in vehicles:
        if is_ego_candidate(actor, ego):
            continue
        location = actor_location_payload(actor)
        if location is None:
            continue
        checked_count += 1
        distance_m = math.hypot(location["x"] - ego_location["x"], location["y"] - ego_location["y"])
        actor_payload = {
            "id": getattr(actor, "id", None),
            "type_id": actor_type_id(actor),
            "role_name": actor_role_name(actor),
            "location": location,
            "distance_m": distance_m,
        }
        if distance_m <= radius_m:
            try:
                actor_payload["destroyed"] = bool(actor.destroy())
            except Exception as exc:
                actor_payload["destroyed"] = False
                actor_payload["destroy_error"] = str(exc)
            destroyed.append(actor_payload)
        else:
            nearby.append(actor_payload)

    nearest_candidates = destroyed + nearby
    nearest_actor = min(nearest_candidates, key=lambda item: float(item["distance_m"]), default=None)
    return {
        "enabled": True,
        "radius_m": radius_m,
        "ego_location": ego_location,
        "checked_count": checked_count,
        "nearby_count": len(destroyed),
        "destroyed_count": sum(1 for item in destroyed if item.get("destroyed")),
        "destroyed_actors": destroyed,
        "nearest_actor": nearest_actor,
        "error": None,
    }


class EgoStartTrafficGuard:
    def __init__(
        self,
        *,
        world: Any,
        ego: Any,
        radius_m: float,
        poll_sec: float,
        max_duration_sec: float,
    ) -> None:
        self.world = world
        self.ego = ego
        self.radius_m = radius_m
        self.poll_sec = poll_sec
        self.max_duration_sec = max_duration_sec
        self.enabled = radius_m > 0.0
        self.started_at: str | None = None
        self.stopped_at: str | None = None
        self.cycles: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        deadline = time.time() + max(0.0, self.max_duration_sec)
        while not self._stop.is_set() and time.time() <= deadline:
            cycle = clear_nearby_start_traffic(self.world, self.ego, self.radius_m)
            cycle["wall_time"] = time.time()
            with self._lock:
                self.cycles.append(cycle)
                self.cycles = self.cycles[-40:]
            self._stop.wait(max(0.05, self.poll_sec))

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.stopped_at = datetime.now(timezone.utc).isoformat()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            cycles = [dict(cycle) for cycle in self.cycles]
        destroyed_count = sum(int(cycle.get("destroyed_count", 0) or 0) for cycle in cycles)
        nearest_distance = None
        nearest_actor = None
        for cycle in cycles:
            actor = cycle.get("nearest_actor")
            if not isinstance(actor, dict):
                continue
            distance = actor.get("distance_m")
            if distance is None:
                continue
            if nearest_distance is None or float(distance) < nearest_distance:
                nearest_distance = float(distance)
                nearest_actor = actor
        return {
            "enabled": self.enabled,
            "radius_m": self.radius_m,
            "poll_sec": self.poll_sec,
            "max_duration_sec": self.max_duration_sec,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "cycle_count": len(cycles),
            "destroyed_count": destroyed_count,
            "nearest_distance_m": nearest_distance,
            "nearest_actor": nearest_actor,
            "cycles": cycles,
        }


def required_service_call_successful(service_calls: list[dict[str, Any]], required_steps: set[str]) -> bool:
    matched_calls = [call for call in service_calls if str(call.get("step") or "") in required_steps]
    matched_steps = {str(call.get("step") or "") for call in matched_calls}
    if not required_steps.issubset(matched_steps):
        return False
    return service_call_successful(matched_calls)


def ego_sample_to_map_xy(sample: dict[str, Any], y_sign: float = -1.0) -> tuple[float, float]:
    return (float(sample["x"]), float(y_sign) * float(sample["y"]))


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
    latest = telemetry_snapshot.get("latest", {})
    if isinstance(latest, dict) and isinstance(latest.get("diagnostics"), dict):
        summary["diagnostics"] = latest["diagnostics"]
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


def speed_target_summary(max_speed_mps: float, target_speed_mps: float | None, tolerance_mps: float) -> dict[str, Any]:
    if target_speed_mps is None or target_speed_mps <= 0.0:
        return {
            "max_speed_kph": max_speed_mps * 3.6,
            "target_speed_mps": None,
            "target_speed_kph": None,
            "target_speed_tolerance_mps": tolerance_mps,
            "target_speed_reached": None,
            "target_speed_deficit_mps": None,
        }
    threshold = max(0.0, target_speed_mps - max(0.0, tolerance_mps))
    deficit = max(0.0, threshold - max_speed_mps)
    return {
        "max_speed_kph": max_speed_mps * 3.6,
        "target_speed_mps": target_speed_mps,
        "target_speed_kph": target_speed_mps * 3.6,
        "target_speed_tolerance_mps": tolerance_mps,
        "target_speed_reached": max_speed_mps >= threshold,
        "target_speed_deficit_mps": deficit,
    }


def setup_route(
    env: dict[str, str],
    start_map: dict[str, float],
    goal_map: dict[str, float],
    calls: list[dict[str, Any]],
    setup_checks: list[dict[str, Any]],
    *,
    waypoints_map: list[dict[str, float]] | None = None,
    allow_goal_modification: bool = True,
    operation_mode_ready_timeout_sec: float = 45.0,
    operation_mode_ready_poll_sec: float = 2.0,
    operation_mode_service_retries: int = 5,
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
    wait_for_topic_sample(
        "wait_localization_state",
        "/localization/kinematic_state",
        env,
        setup_checks,
        retries=3,
        retry_delay_sec=2.0,
    )
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
            route_yaml(goal_map, allow_goal_modification=allow_goal_modification, waypoints=waypoints_map),
        ],
        env,
        calls,
        28,
    )
    time.sleep(2.0)
    wait_for_topic_sample(
        "wait_planning_trajectory",
        "/planning/scenario_planning/trajectory",
        env,
        setup_checks,
        retries=5,
        retry_delay_sec=3.0,
    )
    run_service_cmd_with_retries(
        "enable_autoware_control",
        ["timeout", "15", "ros2", "service", "call", "/api/operation_mode/enable_autoware_control", "autoware_adapi_v1_msgs/srv/ChangeOperationMode", "{}"],
        env,
        calls,
        timeout_sec=18,
        retries=3,
        retry_delay_sec=3.0,
    )
    wait_for_operation_mode_autonomous_available(
        env,
        setup_checks,
        timeout_sec=operation_mode_ready_timeout_sec,
        poll_interval_sec=operation_mode_ready_poll_sec,
    )
    autonomous_call = run_service_cmd_with_retries(
        "change_to_autonomous",
        ["timeout", "25", "ros2", "service", "call", "/api/operation_mode/change_to_autonomous", "autoware_adapi_v1_msgs/srv/ChangeOperationMode", "{}"],
        env,
        calls,
        timeout_sec=28,
        retries=operation_mode_service_retries,
        retry_delay_sec=3.0,
    )
    autonomous_failure = service_call_failure(autonomous_call)
    if autonomous_failure is None:
        mark_service_step_superseded(
            calls,
            step="enable_autoware_control",
            superseded_by_step="change_to_autonomous",
        )
    else:
        failure_context = collect_operation_mode_blocker_snapshot(env)
        autonomous_call["failure_context"] = failure_context
        setup_checks.append(
            {
                "step": "change_to_autonomous_failure_context",
                "passed": False,
                "failure": autonomous_failure,
                "blocker_snapshot": failure_context,
            }
        )
    run_service_cmd_with_retries(
        "engage_true",
        ["timeout", "15", "ros2", "service", "call", "/api/autoware/set/engage", "tier4_external_api_msgs/srv/Engage", "{engage: true}"],
        env,
        calls,
        timeout_sec=18,
        retries=3,
        retry_delay_sec=3.0,
    )


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    carla = load_carla_module()
    run_dir = Path(args.run_dir).resolve()
    payload = scenario_payload(run_dir, args.scenario)
    start_map = pose_from_payload(payload, "ego_init", DEFAULT_START_MAP)
    goal_map = pose_from_payload(payload, "goal", DEFAULT_GOAL_MAP)
    route_waypoints_map, goal_map = route_from_payload(payload, goal_map)
    start_carla = carla_pose_from_map_pose(start_map, args.carla_z_offset, args.carla_y_sign)
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
    setup_checks: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    topic_samples: list[dict[str, Any]] = []
    video_recorder: CameraVideoRecorder | None = None
    last_spectator_view: dict[str, float] | None = None
    last_camera_view: dict[str, float] | None = None
    telemetry = RosTelemetryCollector(enabled=not args.disable_ros_telemetry)
    ego_start_guard: EgoStartTrafficGuard | None = None

    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(args.carla_timeout)
    world, ego = wait_for_ego(client, timeout_sec=args.ego_timeout)
    pre_reset_sample = sample_actor(ego)
    reset_applied = not args.skip_ego_reset
    if reset_applied:
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
    post_reset_sample = sample_actor(ego)
    ego_start_pose_preparation = {
        "desired_carla": start_carla,
        "pre_reset_sample": pre_reset_sample,
        "post_reset_sample": post_reset_sample,
        "reset_applied": reset_applied,
        "skip_ego_reset": bool(args.skip_ego_reset),
        "delta_after_reset_m": math.hypot(
            float(post_reset_sample["x"]) - float(start_carla["x"]),
            float(post_reset_sample["y"]) - float(start_carla["y"]),
        ),
        "yaw_after_reset_delta_deg": abs(float(post_reset_sample["yaw"]) - float(start_carla["yaw"])),
    }
    ego_start_guard = EgoStartTrafficGuard(
        world=world,
        ego=ego,
        radius_m=args.ego_start_clear_radius_m,
        poll_sec=args.ego_start_clear_poll_sec,
        max_duration_sec=args.ego_start_clear_duration_sec,
    )
    ego_start_guard.start()

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

    sample_start_t = time.time()
    setup_sampling_errors: list[str] = []
    sample_period = args.sample_period
    goal_reached_observed = threading.Event()

    def record_ego_sample(phase: str) -> dict[str, Any]:
        nonlocal last_spectator_view, last_camera_view
        elapsed = time.time() - sample_start_t
        ego_sample = sample_actor(ego)
        effective_goal_map = telemetry.effective_goal_map() or goal_map
        sample_goal_distance = distance_to_goal_m(ego_sample, effective_goal_map)
        segment_goal_distance = sample_goal_distance
        if samples:
            previous_ego = samples[-1].get("ego")
            if isinstance(previous_ego, dict):
                segment_goal_distance = min(
                    segment_goal_distance,
                    distance_to_goal_segment_m(previous_ego, ego_sample, effective_goal_map),
                )
        route_progress_goal_distance = min(sample_goal_distance, segment_goal_distance)
        if route_progress_goal_distance <= args.goal_tolerance_m:
            goal_reached_observed.set()
        if args.stop_ego_after_goal and goal_reached_observed.is_set():
            try:
                ego.set_target_velocity(carla.Vector3D(0, 0, 0))
                ego.set_target_angular_velocity(carla.Vector3D(0, 0, 0))
                ego.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))
            except Exception as exc:
                setup_sampling_errors.append(f"stop_ego_after_goal_failed: {exc}")
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
            "i": len(samples),
            "t": elapsed,
            "phase": phase,
            "frame": world.get_snapshot().frame,
            "ego": ego_sample,
            "goal_distance_m": sample_goal_distance,
            "goal_segment_distance_m": segment_goal_distance,
            "route_progress_goal_distance_m": route_progress_goal_distance,
            "effective_goal": effective_goal_map,
        }
        lane_context = carla_waypoint_context(world, carla, ego_sample, y_sign=args.carla_y_sign)
        if lane_context is not None:
            sample_record["carla_waypoint"] = lane_context
        ros_sample = telemetry.sample_snapshot()
        if ros_sample:
            sample_record["ros_telemetry"] = ros_sample
        samples.append(sample_record)
        return sample_record

    setup_sampling_stop = threading.Event()

    def setup_sampler() -> None:
        while not setup_sampling_stop.is_set():
            try:
                record_ego_sample("route_setup")
            except Exception as exc:  # Best-effort diagnostics; setup errors still surface normally.
                setup_sampling_errors.append(str(exc))
                return
            setup_sampling_stop.wait(sample_period)

    try:
        setup_sampling_thread = threading.Thread(target=setup_sampler, daemon=True)
        setup_sampling_thread.start()
        setup_route(
            env,
            start_map,
            goal_map,
            service_calls,
            setup_checks,
            waypoints_map=route_waypoints_map,
            allow_goal_modification=not args.disable_goal_modification,
            operation_mode_ready_timeout_sec=args.operation_mode_ready_timeout_sec,
            operation_mode_ready_poll_sec=args.operation_mode_ready_poll_sec,
            operation_mode_service_retries=args.operation_mode_service_retries,
        )
        setup_sampling_stop.set()
        setup_sampling_thread.join(timeout=max(1.0, sample_period * 2.0))
        if ego_start_guard is not None:
            ego_start_guard.stop()
        start_t = time.time()
        reached_near_goal = any(
            float(sample.get("route_progress_goal_distance_m", sample.get("goal_distance_m", math.inf))) <= args.goal_tolerance_m
            for sample in samples
        )
        min_sample_goal_distance_m = min(
            [float(sample.get("goal_distance_m", math.inf)) for sample in samples],
            default=math.inf,
        )
        min_goal_distance_m = min(
            [
                float(sample.get("route_progress_goal_distance_m", sample.get("goal_distance_m", math.inf)))
                for sample in samples
            ],
            default=math.inf,
        )
        max_speed_mps = max(
            [float((sample.get("ego") or {}).get("speed_mps", 0.0)) for sample in samples],
            default=0.0,
        )
        max_samples = max(1, int(args.max_duration_sec / sample_period))
        for index in range(max_samples):
            elapsed = time.time() - start_t
            if reached_near_goal and elapsed >= args.min_duration_sec:
                break
            sample_record = record_ego_sample("route_tracking")
            ego_sample = sample_record["ego"]
            goal_distance = float(sample_record["goal_distance_m"])
            route_progress_goal_distance = float(sample_record["route_progress_goal_distance_m"])
            reached_near_goal = reached_near_goal or route_progress_goal_distance <= args.goal_tolerance_m
            min_sample_goal_distance_m = min(min_sample_goal_distance_m, goal_distance)
            min_goal_distance_m = min(min_goal_distance_m, route_progress_goal_distance)
            max_speed_mps = max(max_speed_mps, float(ego_sample["speed_mps"]))
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
            ("/system/operation_mode/availability", None),
            ("/system/fail_safe/mrm_state", None),
            ("/autoware/state", None),
            ("/sensing/imu/tamagawa/imu_raw", None),
            ("/diagnostics", None),
        ):
            topic_samples.append(call_topic_echo(topic, env, field))

        total_delta_m = 0.0
        if len(samples) > 1:
            first = samples[0]["ego"]
            last = samples[-1]["ego"]
            total_delta_m = math.hypot(float(last["x"]) - float(first["x"]), float(last["y"]) - float(first["y"]))
        last_location = samples[-1]["ego"] if samples else None
        moved = total_delta_m > args.min_delta_m or max_speed_mps > args.min_speed_mps
        ego_z_values = [
            float((sample.get("ego") or {}).get("z", 0.0))
            for sample in samples
        ]
        ego_pitch_values = [
            abs(float((sample.get("ego") or {}).get("pitch", 0.0)))
            for sample in samples
        ]
        ego_roll_values = [
            abs(float((sample.get("ego") or {}).get("roll", 0.0)))
            for sample in samples
        ]
        min_ego_z_m = min(ego_z_values) if ego_z_values else None
        max_ego_z_m = max(ego_z_values) if ego_z_values else None
        max_abs_pitch_deg = max(ego_pitch_values) if ego_pitch_values else None
        max_abs_roll_deg = max(ego_roll_values) if ego_roll_values else None
        kinematic_sanity_passed = (
            max_speed_mps <= args.max_speed_mps_for_pass
            and (min_ego_z_m is None or min_ego_z_m >= args.min_ego_z_m_for_pass)
            and (max_abs_pitch_deg is None or max_abs_pitch_deg <= args.max_abs_pitch_deg_for_pass)
            and (max_abs_roll_deg is None or max_abs_roll_deg <= args.max_abs_roll_deg_for_pass)
        )
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
            final_map_x, final_map_y = ego_sample_to_map_xy(last_location, args.carla_y_sign)
            final_map_location = {
                "x": final_map_x,
                "y": final_map_y,
                "z": float(last_location.get("z", 0.0)),
                "yaw": float(last_location.get("yaw", 0.0)),
            }
            route_goal_lateral_error_m = abs(final_map_y - float(final_effective_goal_map["y"]))
            longitudinal_error_m = abs(float(final_effective_goal_map["x"]) - final_map_x)
            final_carla_waypoint = carla_waypoint_context(world, carla, last_location, y_sign=args.carla_y_sign)
            if final_carla_waypoint is not None:
                lateral_error_m = float(final_carla_waypoint["carla_lateral_error_m"])
            else:
                lateral_error_m = route_goal_lateral_error_m
        ros_telemetry = summarize_ros_control_telemetry(samples, telemetry.snapshot())
        max_jerk_mps3 = max_abs_jerk_mps3(samples)
        speed_summary = speed_target_summary(
            max_speed_mps,
            args.target_speed_mps if args.target_speed_mps > 0.0 else None,
            args.target_speed_tolerance_mps,
        )
        speed_target_passed = (
            True if speed_summary["target_speed_reached"] is None else bool(speed_summary["target_speed_reached"])
        )
        summary = {
            "sample_count": len(samples),
            "moved": moved,
            "total_delta_m": total_delta_m,
            "max_speed_mps": max_speed_mps,
            "max_speed_mps_for_pass": args.max_speed_mps_for_pass,
            **speed_summary,
            "min_ego_z_m": min_ego_z_m,
            "max_ego_z_m": max_ego_z_m,
            "min_ego_z_m_for_pass": args.min_ego_z_m_for_pass,
            "max_abs_pitch_deg": max_abs_pitch_deg,
            "max_abs_roll_deg": max_abs_roll_deg,
            "max_abs_pitch_deg_for_pass": args.max_abs_pitch_deg_for_pass,
            "max_abs_roll_deg_for_pass": args.max_abs_roll_deg_for_pass,
            "kinematic_sanity_passed": kinematic_sanity_passed,
            "requested_goal": goal_map,
            "requested_route_waypoints": route_waypoints_map,
            "requested_route_waypoint_count": len(route_waypoints_map),
            "effective_goal": final_effective_goal_map,
            "last_location": last_location,
            "final_map_location": final_map_location,
            "final_carla_waypoint": final_carla_waypoint,
            "min_goal_distance_m": min_goal_distance_m if math.isfinite(min_goal_distance_m) else None,
            "min_sample_goal_distance_m": min_sample_goal_distance_m if math.isfinite(min_sample_goal_distance_m) else None,
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
            "setup_checks_passed": all(bool(check.get("passed")) for check in setup_checks),
            "ego_start_pose_preparation": ego_start_pose_preparation,
            "ego_start_traffic_guard": ego_start_guard.snapshot() if ego_start_guard is not None else None,
            "setup_sampling_error_count": len(setup_sampling_errors),
            "setup_sampling_errors": setup_sampling_errors,
            "route_goal_modification_allowed": not args.disable_goal_modification,
            "stop_ego_after_goal": bool(args.stop_ego_after_goal),
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
            "route_waypoints": route_waypoints_map,
            "service_calls": service_calls,
            "setup_checks": setup_checks,
            "topic_samples": topic_samples,
            "samples": samples,
            "summary": summary,
            "verdict": {
                "overall_passed": route_valid
                and moved
                and reached_near_goal
                and speed_target_passed
                and kinematic_sanity_passed,
                "route_passed": route_valid and reached_near_goal,
                "movement_passed": moved,
                "target_speed_passed": speed_target_passed,
                "kinematic_sanity_passed": kinematic_sanity_passed,
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
        if ego_start_guard is not None:
            ego_start_guard.stop()
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
    parser.add_argument("--ros-domain-id", type=int, default=env_int("ROS_DOMAIN_ID", 21))
    parser.add_argument("--rmw-implementation", default=os.environ.get("RMW_IMPLEMENTATION", "rmw_cyclonedds_cpp"))
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=env_int("SIMCTL_CARLA_RPC_PORT", 2000))
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
    parser.add_argument(
        "--stop-ego-after-goal",
        action="store_true",
        help="Continuously brake the CARLA ego once any sample reaches the goal tolerance.",
    )
    parser.add_argument("--min-delta-m", type=float, default=5.0)
    parser.add_argument("--min-speed-mps", type=float, default=1.0)
    parser.add_argument(
        "--target-speed-mps",
        type=float,
        default=0.0,
        help="Optional target speed evidence gate. When set, overall_passed also requires max_speed_mps to reach it within tolerance.",
    )
    parser.add_argument("--target-speed-tolerance-mps", type=float, default=0.5)
    parser.add_argument(
        "--max-speed-mps-for-pass",
        type=float,
        default=30.0,
        help="Fail overall_passed when CARLA ego exceeds this speed, catching physics explosions.",
    )
    parser.add_argument(
        "--min-ego-z-m-for-pass",
        type=float,
        default=-20.0,
        help="Fail overall_passed when CARLA ego drops below this z height.",
    )
    parser.add_argument(
        "--max-abs-pitch-deg-for-pass",
        type=float,
        default=45.0,
        help="Fail overall_passed when absolute ego pitch exceeds this threshold.",
    )
    parser.add_argument(
        "--max-abs-roll-deg-for-pass",
        type=float,
        default=45.0,
        help="Fail overall_passed when absolute ego roll exceeds this threshold.",
    )
    parser.add_argument("--carla-z-offset", type=float, default=0.08)
    parser.add_argument(
        "--carla-y-sign",
        type=float,
        default=env_float("SIMCTL_CARLA_ROS_Y_SIGN", env_float("PIX_CARLA_ROS_Y_SIGN", -1.0)),
        choices=[-1.0, 1.0],
        help="Map-to-CARLA y sign. Default -1 keeps CARLA's standard ROS y flip; use 1 for CARLA-frame XODR/lanelet bundles.",
    )
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
    parser.add_argument(
        "--operation-mode-ready-timeout-sec",
        type=float,
        default=45.0,
        help="Wait this long for /api/operation_mode/state.is_autonomous_mode_available before autonomous mode service retry.",
    )
    parser.add_argument(
        "--operation-mode-ready-poll-sec",
        type=float,
        default=2.0,
        help="Polling interval while waiting for autonomous mode availability.",
    )
    parser.add_argument(
        "--operation-mode-service-retries",
        type=int,
        default=5,
        help="Retry count for change_to_autonomous service calls after readiness wait.",
    )
    parser.add_argument(
        "--ego-start-clear-radius-m",
        type=float,
        default=0.0,
        help="Optional CARLA start guard: delete non-ego vehicles inside this radius while Autoware route setup runs.",
    )
    parser.add_argument(
        "--ego-start-clear-duration-sec",
        type=float,
        default=70.0,
        help="Maximum duration for the ego start traffic guard when --ego-start-clear-radius-m is enabled.",
    )
    parser.add_argument(
        "--ego-start-clear-poll-sec",
        type=float,
        default=0.5,
        help="Polling interval for the ego start traffic guard.",
    )
    parser.add_argument(
        "--skip-ego-reset",
        action="store_true",
        help="Reuse the bridge-spawned ego pose instead of teleporting it before route setup.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_probe(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
