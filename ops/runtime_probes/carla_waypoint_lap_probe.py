#!/usr/bin/env python3
"""Drive the live CARLA ego actor around a trajectory-defined lap.

This probe is CARLA-only. It validates road mesh, collision, and robobus
physics over a full public-road lap before promoting the route back into
Autoware planning/control validation.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def add_carla_python_paths(carla_root: str) -> None:
    if importlib.util.find_spec("carla") is not None:
        return
    root = Path(carla_root).expanduser()
    for candidate in (
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.10-linux-x86_64.egg",
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.7-linux-x86_64.egg",
        root / "PythonAPI" / "carla",
    ):
        if candidate.exists():
            sys.path.insert(0, str(candidate))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def xy_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def bool_metric(value: bool) -> float:
    return 1.0 if value else 0.0


def load_origin_from_preflight(path: Path | None) -> tuple[float, float, float] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    origin = (
        payload.get("local_frame", {})
        .get("origin_map_xyz_from_input_manifest")
    )
    if not isinstance(origin, list) or len(origin) < 3:
        return None
    return float(origin[0]), float(origin[1]), float(origin[2])


def parse_origin(raw: str | None, preflight_path: Path | None) -> tuple[float, float, float]:
    if raw:
        values = [float(item.strip()) for item in raw.split(",") if item.strip()]
        if len(values) != 3:
            raise SystemExit("--origin-map-xyz must contain x,y,z")
        return values[0], values[1], values[2]
    origin = load_origin_from_preflight(preflight_path)
    if origin is not None:
        return origin
    return 0.0, 0.0, 0.0


def parse_triplet(raw: str, *, name: str) -> tuple[float, float, float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if len(values) != 3:
        raise SystemExit(f"{name} must contain three comma-separated values")
    return values[0], values[1], values[2]


def parse_float_list(raw: str, *, name: str) -> list[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise SystemExit(f"{name} must contain at least one numeric value")
    return values


@dataclass(frozen=True)
class RoutePoint:
    x: float
    y: float
    z: float
    yaw_deg: float
    s_m: float


def yaw_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def dedupe_and_space(points: list[tuple[float, float, float]], min_spacing_m: float) -> list[tuple[float, float, float]]:
    selected: list[tuple[float, float, float]] = []
    for point in points:
        if not selected or xy_distance((point[0], point[1]), (selected[-1][0], selected[-1][1])) >= min_spacing_m:
            selected.append(point)
    if len(selected) >= 2 and xy_distance((selected[-1][0], selected[-1][1]), (selected[0][0], selected[0][1])) <= min_spacing_m:
        selected[-1] = selected[0]
    elif len(selected) >= 2:
        selected.append(selected[0])
    return selected


def load_trajectory_route(
    trajectory_csv: Path,
    origin_xyz: tuple[float, float, float],
    *,
    min_spacing_m: float,
    z_offset_m: float,
    reverse: bool = False,
) -> list[RoutePoint]:
    raw_points: list[tuple[float, float, float]] = []
    with trajectory_csv.open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw_points.append(
                (
                    float(row["x"]) - origin_xyz[0],
                    float(row["y"]) - origin_xyz[1],
                    float(row["z"]) - origin_xyz[2] + z_offset_m,
                )
            )
    if reverse:
        raw_points = list(reversed(raw_points))
    spaced = dedupe_and_space(raw_points, min_spacing_m)
    if len(spaced) < 4:
        raise SystemExit(f"trajectory route has too few points after spacing: {len(spaced)}")
    result: list[RoutePoint] = []
    cumulative = 0.0
    for index, point in enumerate(spaced):
        if index > 0:
            cumulative += xy_distance((spaced[index - 1][0], spaced[index - 1][1]), (point[0], point[1]))
        next_point = spaced[min(index + 1, len(spaced) - 1)]
        if index == len(spaced) - 1 and len(result) > 0:
            yaw_deg = result[-1].yaw_deg
        else:
            yaw_deg = yaw_between((point[0], point[1]), (next_point[0], next_point[1]))
        result.append(RoutePoint(point[0], point[1], point[2], yaw_deg, cumulative))
    return result


def load_carla_module(carla_root: str) -> Any:
    add_carla_python_paths(carla_root)
    try:
        import carla  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit("Missing CARLA Python module; provide --carla-root or PYTHONPATH.") from exc
    return carla


def actor_role(actor: Any) -> str:
    return str(getattr(actor, "attributes", {}).get("role_name", ""))


def find_ego(world: Any, actor_id: str, ego_role_name: str, timeout_sec: float) -> Any:
    deadline = time.time() + max(0.0, timeout_sec)
    while True:
        vehicles = list(world.get_actors().filter("vehicle.*"))
        for actor in vehicles:
            if actor_role(actor) == ego_role_name:
                return actor
        for actor in vehicles:
            if str(getattr(actor, "type_id", "")) == actor_id:
                return actor
        if len(vehicles) == 1:
            return vehicles[0]
        if time.time() >= deadline:
            raise SystemExit(f"ego actor not found: role={ego_role_name}, type={actor_id}, vehicles={len(vehicles)}")
        time.sleep(0.5)


def destroy_matching_vehicles(world: Any, actor_id: str, ego_role_name: str) -> None:
    for actor in list(world.get_actors().filter("vehicle.*")):
        role_name = actor_role(actor)
        if str(getattr(actor, "type_id", "")) == actor_id or role_name == ego_role_name:
            try:
                actor.destroy()
            except Exception:
                pass


def spawn_ego_at_route_start(
    carla: Any,
    world: Any,
    *,
    actor_id: str,
    ego_role_name: str,
    first: RoutePoint,
    spawn_z_offsets: list[float],
) -> tuple[Any, dict[str, Any]]:
    try:
        blueprint = world.get_blueprint_library().find(actor_id)
    except Exception as exc:
        raise SystemExit(f"ego blueprint not found: actor_id={actor_id}, error={exc}") from exc
    if getattr(blueprint, "has_attribute", lambda _name: False)("role_name"):
        blueprint.set_attribute("role_name", ego_role_name)

    for z_offset in spawn_z_offsets:
        transform = carla.Transform(
            carla.Location(x=first.x, y=first.y, z=first.z + z_offset),
            carla.Rotation(yaw=first.yaw_deg),
        )
        actor = world.try_spawn_actor(blueprint, transform)
        if actor is None:
            continue
        actor.set_target_velocity(carla.Vector3D(0.0, 0.0, 0.0))
        actor.set_target_angular_velocity(carla.Vector3D(0.0, 0.0, 0.0))
        actor.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))
        return actor, {
            "source": "spawned",
            "actor_id": actor_id,
            "ego_role_name": ego_role_name,
            "spawn_z_offset_m": z_offset,
            "spawn_transform": {
                "x": first.x,
                "y": first.y,
                "z": first.z + z_offset,
                "yaw_deg": first.yaw_deg,
            },
        }

    raise SystemExit(
        "ego spawn failed: "
        f"actor_id={actor_id}, role={ego_role_name}, "
        f"route_start=({first.x},{first.y},{first.z}), z_offsets={spawn_z_offsets}"
    )


def find_or_spawn_ego(carla: Any, world: Any, args: argparse.Namespace, first: RoutePoint) -> tuple[Any, dict[str, Any]]:
    if args.destroy_existing_ego:
        destroy_matching_vehicles(world, args.actor_id, args.ego_role_name)
        time.sleep(args.settle_sec)
    if not args.destroy_existing_ego:
        find_timeout = args.actor_wait_sec
        if args.spawn_if_missing:
            find_timeout = min(args.actor_wait_sec, args.spawn_find_timeout_sec)
        try:
            actor = find_ego(world, args.actor_id, args.ego_role_name, find_timeout)
            return actor, {
                "source": "existing",
                "actor_id": str(getattr(actor, "type_id", args.actor_id)),
                "ego_role_name": actor_role(actor),
            }
        except SystemExit:
            if not args.spawn_if_missing:
                raise

    if not args.spawn_if_missing:
        raise SystemExit(f"ego actor not found: role={args.ego_role_name}, type={args.actor_id}")
    return spawn_ego_at_route_start(
        carla,
        world,
        actor_id=args.actor_id,
        ego_role_name=args.ego_role_name,
        first=first,
        spawn_z_offsets=parse_float_list(args.spawn_z_offsets, name="--spawn-z-offsets"),
    )


def speed_mps(actor: Any) -> float:
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x * velocity.x + velocity.y * velocity.y + velocity.z * velocity.z)


def actor_sample(actor: Any) -> dict[str, Any]:
    transform = actor.get_transform()
    control = actor.get_control()
    speed = speed_mps(actor)
    return {
        "x": float(transform.location.x),
        "y": float(transform.location.y),
        "z": float(transform.location.z),
        "pitch": float(transform.rotation.pitch),
        "yaw": float(transform.rotation.yaw),
        "roll": float(transform.rotation.roll),
        "speed_mps": speed,
        "speed_kph": speed * 3.6,
        "throttle": float(control.throttle),
        "brake": float(control.brake),
        "steer": float(control.steer),
    }


def reset_to_route_start(carla: Any, actor: Any, first: RoutePoint) -> None:
    actor.set_transform(
        carla.Transform(
            carla.Location(x=first.x, y=first.y, z=first.z),
            carla.Rotation(yaw=first.yaw_deg),
        )
    )
    actor.set_target_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    actor.set_target_angular_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    actor.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))


def set_actor_route_pose(carla: Any, actor: Any, point: RoutePoint, speed_mps: float) -> None:
    yaw_rad = math.radians(point.yaw_deg)
    actor.set_transform(
        carla.Transform(
            carla.Location(x=point.x, y=point.y, z=point.z),
            carla.Rotation(yaw=point.yaw_deg),
        )
    )
    actor.set_target_velocity(
        carla.Vector3D(
            speed_mps * math.cos(yaw_rad),
            speed_mps * math.sin(yaw_rad),
            0.0,
        )
    )
    actor.set_target_angular_velocity(carla.Vector3D(0.0, 0.0, 0.0))


def nearest_route_index(
    route: list[RoutePoint],
    point: tuple[float, float],
    current_index: int,
    search_window: int,
    terminal_guard_ratio: float = 0.85,
) -> tuple[int, float]:
    end = min(len(route), current_index + max(2, search_window))
    indices = range(current_index, end)
    best_index = current_index
    best_dist = float("inf")
    for index in indices:
        if not route_candidate_allowed(
            route,
            current_index,
            index,
            terminal_guard_ratio=terminal_guard_ratio,
        ):
            continue
        dist = xy_distance(point, (route[index].x, route[index].y))
        if dist < best_dist:
            best_index = index
            best_dist = dist
    if best_dist > 60.0:
        for index in range(current_index, len(route)):
            if not route_candidate_allowed(
                route,
                current_index,
                index,
                terminal_guard_ratio=terminal_guard_ratio,
            ):
                continue
            dist = xy_distance(point, (route[index].x, route[index].y))
            if dist < best_dist:
                best_index = index
                best_dist = dist
    return best_index, best_dist


def normalize_angle_rad(value: float) -> float:
    return (value + math.pi) % (2.0 * math.pi) - math.pi


def route_candidate_allowed(
    route: list[RoutePoint],
    current_index: int,
    candidate_index: int,
    *,
    terminal_guard_ratio: float,
) -> bool:
    if not route:
        return False
    route_length = route[-1].s_m
    if route_length <= 0.0:
        return True
    guard_s = clamp(terminal_guard_ratio, 0.0, 1.0) * route_length
    if route[current_index].s_m < guard_s and route[candidate_index].s_m >= guard_s:
        return False
    return True


def target_index_for_lookahead(route: list[RoutePoint], current_index: int, lookahead_m: float) -> int:
    target_s = route[current_index].s_m + max(1.0, lookahead_m)
    for index in range(current_index, len(route)):
        if route[index].s_m >= target_s:
            return index
    return len(route) - 1


def interpolate_route_point(route: list[RoutePoint], s_m: float) -> RoutePoint:
    if not route:
        raise ValueError("route is empty")
    if s_m <= route[0].s_m:
        return route[0]
    for index in range(1, len(route)):
        prev = route[index - 1]
        next_point = route[index]
        if next_point.s_m < s_m:
            continue
        segment_length = max(0.001, next_point.s_m - prev.s_m)
        ratio = clamp((s_m - prev.s_m) / segment_length, 0.0, 1.0)
        yaw_rad = math.radians(prev.yaw_deg)
        return RoutePoint(
            x=prev.x + (next_point.x - prev.x) * ratio,
            y=prev.y + (next_point.y - prev.y) * ratio,
            z=prev.z + (next_point.z - prev.z) * ratio,
            yaw_deg=math.degrees(yaw_rad),
            s_m=s_m,
        )
    return route[-1]


def route_index_for_s(route: list[RoutePoint], s_m: float) -> int:
    for index, point in enumerate(route):
        if point.s_m >= s_m:
            return index
    return len(route) - 1


def apply_route_yaw_offset(route: list[RoutePoint], yaw_offset_deg: float) -> list[RoutePoint]:
    if yaw_offset_deg == 0.0:
        return route
    return [
        RoutePoint(
            point.x,
            point.y,
            point.z,
            point.yaw_deg + yaw_offset_deg,
            point.s_m,
        )
        for point in route
    ]


def local_target_xy(sample: dict[str, Any], target: RoutePoint) -> tuple[float, float]:
    yaw_rad = math.radians(float(sample["yaw"]))
    dx = target.x - float(sample["x"])
    dy = target.y - float(sample["y"])
    local_x = math.cos(yaw_rad) * dx + math.sin(yaw_rad) * dy
    local_y = -math.sin(yaw_rad) * dx + math.cos(yaw_rad) * dy
    return local_x, local_y


def target_index_for_forward_lookahead(
    route: list[RoutePoint],
    sample: dict[str, Any],
    current_index: int,
    *,
    lookahead_m: float,
    search_window: int,
    min_forward_m: float,
) -> tuple[int, dict[str, Any]]:
    target_s = route[current_index].s_m + max(1.0, lookahead_m)
    end = min(len(route), current_index + max(3, search_window))
    fallback_index = target_index_for_lookahead(route, current_index, lookahead_m)
    fallback_local = local_target_xy(sample, route[fallback_index])
    best_forward_index: int | None = None
    best_forward_score = float("inf")
    for index in range(current_index + 1, end):
        local_x, local_y = local_target_xy(sample, route[index])
        if local_x < min_forward_m:
            continue
        score = abs(route[index].s_m - target_s) + 0.25 * abs(local_y)
        if route[index].s_m < route[current_index].s_m:
            score += 1_000.0
        if score < best_forward_score:
            best_forward_index = index
            best_forward_score = score
    if best_forward_index is not None:
        local_x, local_y = local_target_xy(sample, route[best_forward_index])
        return best_forward_index, {
            "target_selection": "forward_lookahead",
            "target_local_x_m": local_x,
            "target_local_y_m": local_y,
        }

    best_index = fallback_index
    best_score = float("inf")
    for index in range(current_index + 1, end):
        local_x, local_y = local_target_xy(sample, route[index])
        heading_error = abs(math.atan2(local_y, local_x if abs(local_x) > 0.1 else math.copysign(0.1, local_x or 1.0)))
        score = heading_error + 0.02 * max(0.0, target_s - route[index].s_m)
        if score < best_score:
            best_index = index
            best_score = score
            fallback_local = (local_x, local_y)
    return best_index, {
        "target_selection": "min_heading_fallback",
        "target_local_x_m": fallback_local[0],
        "target_local_y_m": fallback_local[1],
    }


def control_towards_target(
    carla: Any,
    sample: dict[str, Any],
    target: RoutePoint,
    *,
    target_speed_mps: float,
    turn_speed_mps: float,
    steer_gain: float,
    steer_sign: float,
    throttle_gain: float,
    brake_gain: float,
    max_throttle: float,
    max_brake: float,
    brake_heading_error_rad: float,
    overspeed_brake_margin_mps: float,
    pure_pursuit_wheelbase_m: float | None = None,
    pure_pursuit_max_steer_angle_rad: float | None = None,
) -> tuple[Any, dict[str, float]]:
    local_x, local_y = local_target_xy(sample, target)
    heading_error = math.atan2(local_y, max(0.1, local_x))
    if pure_pursuit_wheelbase_m is None or pure_pursuit_max_steer_angle_rad is None:
        steer = clamp(steer_sign * steer_gain * heading_error, -1.0, 1.0)
        curvature = 0.0
        steering_angle = 0.0
    else:
        lookahead_distance = max(1.0, math.hypot(local_x, local_y))
        curvature = 2.0 * local_y / (lookahead_distance * lookahead_distance)
        steering_angle = math.atan(pure_pursuit_wheelbase_m * curvature)
        steer = clamp(steer_sign * steer_gain * steering_angle / pure_pursuit_max_steer_angle_rad, -1.0, 1.0)
    desired_speed = turn_speed_mps if abs(heading_error) > 0.45 else target_speed_mps
    speed_error = desired_speed - float(sample["speed_mps"])
    throttle = clamp(throttle_gain * speed_error, 0.0, max_throttle)
    brake = 0.0
    if speed_error < -abs(overspeed_brake_margin_mps) or abs(heading_error) > brake_heading_error_rad:
        throttle = 0.0
        brake = clamp(brake_gain * abs(speed_error), 0.0, max_brake)
    return (
        carla.VehicleControl(throttle=throttle, brake=brake, steer=steer),
        {
            "target_x": target.x,
            "target_y": target.y,
            "target_s_m": target.s_m,
            "local_x_m": local_x,
            "local_y_m": local_y,
            "heading_error_rad": heading_error,
            "curvature": curvature,
            "steering_angle_rad": steering_angle,
            "desired_speed_mps": desired_speed,
            "steer": steer,
            "throttle": throttle,
            "brake": brake,
        },
    )


def control_along_route_heading(
    carla: Any,
    sample: dict[str, Any],
    route_point: RoutePoint,
    *,
    target_speed_mps: float,
    turn_speed_mps: float,
    steer_gain: float,
    steer_sign: float,
    throttle_gain: float,
    brake_gain: float,
    max_throttle: float,
    max_brake: float,
    brake_heading_error_rad: float,
    overspeed_brake_margin_mps: float,
    route_heading_cross_track_gain: float,
    route_heading_softening_mps: float,
    route_heading_max_steer_angle_rad: float,
) -> tuple[Any, dict[str, float]]:
    route_yaw_rad = math.radians(route_point.yaw_deg)
    ego_yaw_rad = math.radians(float(sample["yaw"]))
    heading_error = normalize_angle_rad(route_yaw_rad - ego_yaw_rad)
    dx = float(sample["x"]) - route_point.x
    dy = float(sample["y"]) - route_point.y
    cross_track_error = -math.sin(route_yaw_rad) * dx + math.cos(route_yaw_rad) * dy
    stanley_term = math.atan2(
        route_heading_cross_track_gain * cross_track_error,
        max(0.1, float(sample["speed_mps"]) + route_heading_softening_mps),
    )
    steering_angle = -(steer_gain * heading_error + stanley_term)
    steer = clamp(
        steer_sign * steering_angle / max(0.05, route_heading_max_steer_angle_rad),
        -1.0,
        1.0,
    )
    desired_speed = (
        turn_speed_mps
        if abs(heading_error) > 0.45 or abs(cross_track_error) > 3.0
        else target_speed_mps
    )
    speed_error = desired_speed - float(sample["speed_mps"])
    throttle = clamp(throttle_gain * speed_error, 0.0, max_throttle)
    brake = 0.0
    if speed_error < -abs(overspeed_brake_margin_mps) or abs(heading_error) > brake_heading_error_rad:
        throttle = 0.0
        brake = clamp(brake_gain * abs(speed_error), 0.0, max_brake)
    return (
        carla.VehicleControl(throttle=throttle, brake=brake, steer=steer),
        {
            "route_x": route_point.x,
            "route_y": route_point.y,
            "route_s_m": route_point.s_m,
            "route_yaw_deg": route_point.yaw_deg,
            "heading_error_rad": heading_error,
            "cross_track_error_m": cross_track_error,
            "stanley_term_rad": stanley_term,
            "steering_angle_rad": steering_angle,
            "desired_speed_mps": desired_speed,
            "steer": steer,
            "throttle": throttle,
            "brake": brake,
        },
    )


def make_pid_controller(ego: Any, args: argparse.Namespace) -> Any:
    from agents.navigation.controller import VehiclePIDController  # type: ignore[import-not-found]

    return VehiclePIDController(
        ego,
        args_lateral={
            "K_P": args.pid_lateral_kp,
            "K_I": args.pid_lateral_ki,
            "K_D": args.pid_lateral_kd,
            "dt": args.sample_period_sec,
        },
        args_longitudinal={
            "K_P": args.pid_longitudinal_kp,
            "K_I": args.pid_longitudinal_ki,
            "K_D": args.pid_longitudinal_kd,
            "dt": args.sample_period_sec,
        },
        max_throttle=args.max_throttle,
        max_brake=args.max_brake,
        max_steering=args.pid_max_steering,
    )


def route_point_to_waypoint(carla: Any, point: RoutePoint) -> Any:
    transform = carla.Transform(
        carla.Location(x=point.x, y=point.y, z=point.z),
        carla.Rotation(yaw=point.yaw_deg),
    )
    return SimpleNamespace(transform=transform)


class VideoRecorder:
    def __init__(
        self,
        carla: Any,
        world: Any,
        ego: Any,
        run_dir: Path,
        args: argparse.Namespace,
    ) -> None:
        self.carla = carla
        self.world = world
        self.ego = ego
        self.fps = max(0.1, float(args.video_fps))
        self.frames_dir = (
            Path(args.video_frame_dir).expanduser()
            if args.video_frame_dir
            else run_dir / "runtime_verification" / "video_frames"
        )
        self.output_path = (
            Path(args.video_output).expanduser()
            if args.video_output
            else run_dir / "runtime_verification" / "qiyu_robobus_lap.mp4"
        )
        self.width = int(args.video_width)
        self.height = int(args.video_height)
        self.fov = float(args.video_fov_deg)
        self.camera_location = parse_triplet(args.video_camera_location, name="--video-camera-location")
        self.camera_rotation = parse_triplet(args.video_camera_rotation, name="--video-camera-rotation")
        self.keep_frames = bool(args.keep_video_frames)
        self.sensor: Any | None = None
        self.frames_saved = 0
        self.errors: list[str] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
        blueprint.set_attribute("image_size_x", str(self.width))
        blueprint.set_attribute("image_size_y", str(self.height))
        blueprint.set_attribute("fov", str(self.fov))
        blueprint.set_attribute("sensor_tick", str(1.0 / self.fps))
        loc = self.camera_location
        rot = self.camera_rotation
        transform = self.carla.Transform(
            self.carla.Location(x=loc[0], y=loc[1], z=loc[2]),
            self.carla.Rotation(pitch=rot[0], yaw=rot[1], roll=rot[2]),
        )
        self.sensor = self.world.spawn_actor(blueprint, transform, attach_to=self.ego)
        self.sensor.listen(self._save_frame)

    def _save_frame(self, image: Any) -> None:
        try:
            from PIL import Image

            with self._lock:
                self.frames_saved += 1
                frame_index = self.frames_saved
            frame_path = self.frames_dir / f"frame_{frame_index:06d}.jpg"
            rgba = Image.frombuffer(
                "RGBA",
                (image.width, image.height),
                bytes(image.raw_data),
                "raw",
                "BGRA",
                0,
                1,
            )
            rgba.convert("RGB").save(frame_path, format="JPEG", quality=88)
        except Exception as exc:  # pragma: no cover - depends on CARLA callback thread.
            with self._lock:
                if len(self.errors) < 5:
                    self.errors.append(str(exc))

    def stop(self) -> None:
        if self.sensor is None:
            return
        try:
            self.sensor.stop()
            self.sensor.destroy()
        finally:
            self.sensor = None

    def encode(self) -> dict[str, Any]:
        frame_count = len(list(self.frames_dir.glob("frame_*.jpg")))
        result: dict[str, Any] = {
            "frames_dir": str(self.frames_dir),
            "output_path": str(self.output_path),
            "fps": self.fps,
            "frame_count": frame_count,
            "encoded": False,
            "errors": self.errors,
        }
        if frame_count <= 0:
            result["errors"] = [*self.errors, "no camera frames captured"]
            return result
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(self.fps),
            "-pattern_type",
            "glob",
            "-i",
            str(self.frames_dir / "frame_*.jpg"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(self.output_path),
        ]
        completed = subprocess.run(command, check=False, text=True, capture_output=True)
        result.update(
            {
                "encoded": completed.returncode == 0 and self.output_path.exists(),
                "ffmpeg_returncode": completed.returncode,
                "ffmpeg_stderr": completed.stderr[-2000:],
                "output_size_bytes": self.output_path.stat().st_size if self.output_path.exists() else 0,
            }
        )
        if result["encoded"] and not self.keep_frames:
            shutil.rmtree(self.frames_dir, ignore_errors=True)
            result["frames_retained"] = False
        else:
            result["frames_retained"] = True
        return result


def build_metrics(summary: dict[str, Any]) -> dict[str, float]:
    return {
        "route_completion": float(summary["route_completion_ratio"]),
        "collision_count": 0.0 if summary["kinematic_sanity_passed"] else 1.0,
        "min_ttc_sec": 999.0,
        "kinematic_sanity_passed": bool_metric(bool(summary["kinematic_sanity_passed"])),
        "max_speed_mps": float(summary["max_speed_mps"]),
        "max_speed_kph": float(summary["max_speed_mps"]) * 3.6,
        "min_ego_z_m": float(summary["min_ego_z_m"]),
        "max_abs_pitch_deg": float(summary["max_abs_pitch_deg"]),
        "max_abs_roll_deg": float(summary["max_abs_roll_deg"]),
        "qiyu_lap_route_length_m": float(summary["route_length_m"]),
        "qiyu_lap_progress_m": float(summary["progress_m"]),
        "qiyu_lap_max_lateral_error_m": float(summary["max_lateral_error_m"]),
    }


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    carla = load_carla_module(args.carla_root)
    origin = parse_origin(args.origin_map_xyz, args.import_preflight_report)
    route = load_trajectory_route(
        args.trajectory_csv,
        origin,
        min_spacing_m=args.route_min_spacing_m,
        z_offset_m=args.route_z_offset_m,
        reverse=args.reverse_route,
    )
    route = apply_route_yaw_offset(route, args.route_yaw_offset_deg)
    route_length_m = route[-1].s_m
    run_dir = Path(args.run_dir).resolve()

    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(args.carla_timeout)
    world = client.get_world()
    ego, ego_source = find_or_spawn_ego(carla, world, args, route[0])
    if args.reset_to_route_start:
        reset_to_route_start(carla, ego, route[0])
        time.sleep(args.settle_sec)
    if args.controller == "kinematic_route":
        ego.set_simulate_physics(False)
    pid_controller = make_pid_controller(ego, args) if args.controller == "pid" else None
    video_recorder: VideoRecorder | None = None
    if args.record_video:
        video_recorder = VideoRecorder(carla, world, ego, run_dir, args)
        video_recorder.start()

    current_index = 0
    max_speed = 0.0
    min_z = float("inf")
    max_abs_pitch = 0.0
    max_abs_roll = 0.0
    max_lateral_error = 0.0
    progress_m = 0.0
    samples: list[dict[str, Any]] = []
    started = time.time()
    completed = False
    failed_reason = None
    max_samples = max(1, int(args.max_duration_sec / args.sample_period_sec))
    for sample_index in range(max_samples):
        now = time.time()
        elapsed = now - started
        kinematic_target_s: float | None = None
        kinematic_pose: RoutePoint | None = None
        if args.controller == "kinematic_route":
            kinematic_target_s = min(route_length_m, elapsed * max(0.1, args.target_speed_mps))
            kinematic_pose = interpolate_route_point(route, kinematic_target_s)
            set_actor_route_pose(carla, ego, kinematic_pose, args.target_speed_mps)
        sample = actor_sample(ego)
        if kinematic_target_s is not None and kinematic_pose is not None:
            current_index = route_index_for_s(route, kinematic_target_s)
            lateral_error = xy_distance(
                (float(sample["x"]), float(sample["y"])),
                (kinematic_pose.x, kinematic_pose.y),
            )
            progress_m = max(progress_m, kinematic_target_s)
        else:
            current_index, lateral_error = nearest_route_index(
                route,
                (float(sample["x"]), float(sample["y"])),
                current_index,
                args.route_search_window,
                terminal_guard_ratio=args.closed_route_terminal_guard_ratio,
            )
            progress_m = max(progress_m, route[current_index].s_m)
        completion = min(1.0, progress_m / route_length_m) if route_length_m > 0.0 else 0.0
        target_debug: dict[str, Any] = {"target_selection": "lookahead"}
        if args.controller == "kinematic_route":
            target_index = current_index
            target_debug = {
                "target_selection": "kinematic_route",
                "target_s_m": kinematic_target_s,
            }
        elif args.controller == "pure_pursuit":
            target_index, target_debug = target_index_for_forward_lookahead(
                route,
                sample,
                current_index,
                lookahead_m=args.lookahead_m,
                search_window=args.pure_pursuit_target_search_window,
                min_forward_m=args.pure_pursuit_min_forward_m,
            )
        else:
            target_index = target_index_for_lookahead(route, current_index, args.lookahead_m)
        if args.controller == "kinematic_route":
            control = carla.VehicleControl(throttle=0.0, brake=0.0, steer=0.0)
            control_debug = {
                "controller": "kinematic_route",
                "desired_speed_mps": args.target_speed_mps,
                "steer": 0.0,
                "throttle": 0.0,
                "brake": 0.0,
            }
        elif args.controller == "route_heading":
            control, control_debug = control_along_route_heading(
                carla,
                sample,
                route[current_index],
                target_speed_mps=args.target_speed_mps,
                turn_speed_mps=args.turn_speed_mps,
                steer_gain=args.steer_gain,
                steer_sign=args.steer_sign,
                throttle_gain=args.throttle_gain,
                brake_gain=args.brake_gain,
                max_throttle=args.max_throttle,
                max_brake=args.max_brake,
                brake_heading_error_rad=args.brake_heading_error_rad,
                overspeed_brake_margin_mps=args.overspeed_brake_margin_mps,
                route_heading_cross_track_gain=args.route_heading_cross_track_gain,
                route_heading_softening_mps=args.route_heading_softening_mps,
                route_heading_max_steer_angle_rad=args.route_heading_max_steer_angle_rad,
            )
        else:
            control, control_debug = control_towards_target(
                carla,
                sample,
                route[target_index],
                target_speed_mps=args.target_speed_mps,
                turn_speed_mps=args.turn_speed_mps,
                steer_gain=args.steer_gain,
                steer_sign=args.steer_sign,
                throttle_gain=args.throttle_gain,
                brake_gain=args.brake_gain,
                max_throttle=args.max_throttle,
                max_brake=args.max_brake,
                brake_heading_error_rad=args.brake_heading_error_rad,
                overspeed_brake_margin_mps=args.overspeed_brake_margin_mps,
                pure_pursuit_wheelbase_m=args.pure_pursuit_wheelbase_m if args.controller == "pure_pursuit" else None,
                pure_pursuit_max_steer_angle_rad=(
                    args.pure_pursuit_max_steer_angle_rad if args.controller == "pure_pursuit" else None
                ),
            )
        if pid_controller is not None:
            target_speed_kph = float(control_debug["desired_speed_mps"]) * 3.6
            control = pid_controller.run_step(
                target_speed_kph,
                route_point_to_waypoint(carla, route[target_index]),
            )
            control_debug.update(
                {
                    "controller": "pid",
                    "target_speed_kph": target_speed_kph,
                    "steer": float(control.steer),
                    "throttle": float(control.throttle),
                    "brake": float(control.brake),
                }
            )
        else:
            control_debug["controller"] = args.controller
        control_debug.update(target_debug)
        ego.apply_control(control)
        max_speed = max(max_speed, float(sample["speed_mps"]))
        min_z = min(min_z, float(sample["z"]))
        max_abs_pitch = max(max_abs_pitch, abs(float(sample["pitch"])))
        max_abs_roll = max(max_abs_roll, abs(float(sample["roll"])))
        max_lateral_error = max(max_lateral_error, lateral_error)
        if sample_index % max(1, args.sample_decimation) == 0:
            samples.append(
                {
                    "i": sample_index,
                    "t": elapsed,
                    "route_index": current_index,
                    "target_index": target_index,
                    "progress_m": progress_m,
                    "route_completion_ratio": completion,
                    "lateral_error_m": lateral_error,
                    "ego": sample,
                    "control": control_debug,
                }
            )
        if float(sample["z"]) < args.min_ego_z_m_for_pass:
            failed_reason = "ego_z_below_threshold"
            break
        if abs(float(sample["pitch"])) > args.max_abs_pitch_deg_for_pass:
            failed_reason = "ego_pitch_exceeded_threshold"
            break
        if abs(float(sample["roll"])) > args.max_abs_roll_deg_for_pass:
            failed_reason = "ego_roll_exceeded_threshold"
            break
        if lateral_error > args.max_lateral_error_m_for_pass:
            failed_reason = "lateral_error_exceeded_threshold"
            break
        if completion >= args.completion_ratio:
            completed = True
            break
        time.sleep(args.sample_period_sec)

    for _ in range(int(max(0.0, args.brake_after_sec) / max(args.sample_period_sec, 0.01))):
        ego.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))
        time.sleep(args.sample_period_sec)
    if video_recorder is not None:
        video_recorder.stop()

    kinematic_sanity_passed = (
        max_speed <= args.max_speed_mps_for_pass
        and min_z >= args.min_ego_z_m_for_pass
        and max_abs_pitch <= args.max_abs_pitch_deg_for_pass
        and max_abs_roll <= args.max_abs_roll_deg_for_pass
        and max_lateral_error <= args.max_lateral_error_m_for_pass
    )
    summary = {
        "completed": completed,
        "failed_reason": failed_reason,
        "route_completion_ratio": min(1.0, progress_m / route_length_m) if route_length_m > 0.0 else 0.0,
        "progress_m": progress_m,
        "route_length_m": route_length_m,
        "route_point_count": len(route),
        "sample_count": len(samples),
        "elapsed_sec": time.time() - started,
        "max_speed_mps": max_speed,
        "min_ego_z_m": min_z,
        "max_abs_pitch_deg": max_abs_pitch,
        "max_abs_roll_deg": max_abs_roll,
        "max_lateral_error_m": max_lateral_error,
        "kinematic_sanity_passed": kinematic_sanity_passed,
        "origin_map_xyz": list(origin),
        "route_start": route[0].__dict__,
        "route_end": route[-1].__dict__,
        "ego_source": ego_source,
    }
    overall_passed = completed and kinematic_sanity_passed and failed_reason is None
    metrics = build_metrics(summary)
    video_artifact = video_recorder.encode() if video_recorder is not None else None
    stamp = utc_stamp()
    probe_dir = run_dir / "runtime_verification" / f"metric_probe_qiyu_robobus_lap_{stamp}"
    probe_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "qiyu_robobus_direct_waypoint_lap_probe",
        "profile": args.profile,
        "scope": (
            "real_carla_kinematic_route_lap"
            if args.controller == "kinematic_route"
            else "real_carla_direct_control_road_mesh_lap"
        ),
        "overall_passed": overall_passed,
        "blocked_reason": None if overall_passed else (failed_reason or "lap_not_completed"),
        "missing_metrics": [],
        "missing_topics": [],
        "sample_missing_topics": [],
        "metrics": metrics,
        "summary": summary,
        "samples": samples,
        "video": video_artifact,
        "assumptions": [
            (
                "CARLA kinematic route replay validates map import, route continuity, and full-lap visualization."
                if args.controller == "kinematic_route"
                else "CARLA-only direct control validates road mesh, collision, and robobus physics."
            ),
            "This is not Autoware planning/control closed-loop acceptance.",
        ],
    }
    metric_path = probe_dir / f"metric_probe_qiyu_robobus_lap_{stamp}.json"
    metric_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary_path = run_dir / "runtime_verification" / "qiyu_robobus_lap_summary.json"
    summary_path.write_text(json.dumps({"metric_probe": str(metric_path), **payload}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"overall_passed": overall_passed, "metric_probe": str(metric_path), "summary": summary}, ensure_ascii=False, indent=2))
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", default="qiyu_rp14_robobus_direct_lap")
    parser.add_argument("--trajectory-csv", type=Path, required=True)
    parser.add_argument("--import-preflight-report", type=Path)
    parser.add_argument("--origin-map-xyz")
    parser.add_argument("--reverse-route", action="store_true")
    parser.add_argument("--carla-root", default=os.environ.get("SIMCTL_CARLA_ROOT", ""))
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=int(os.environ.get("SIMCTL_CARLA_RPC_PORT", "2000")))
    parser.add_argument("--carla-timeout", type=float, default=10.0)
    parser.add_argument("--actor-id", default=os.environ.get("SIMCTL_CARLA_VEHICLE_TYPE", "vehicle.pixmoving.robobus"))
    parser.add_argument("--ego-role-name", default=os.environ.get("SIMCTL_CARLA_EGO_ROLE_NAME", "ego_vehicle"))
    parser.add_argument("--actor-wait-sec", type=float, default=30.0)
    parser.add_argument("--spawn-if-missing", action="store_true")
    parser.add_argument("--destroy-existing-ego", action="store_true")
    parser.add_argument("--spawn-find-timeout-sec", type=float, default=2.0)
    parser.add_argument("--spawn-z-offsets", default="0.0,0.5,1.0")
    parser.add_argument("--reset-to-route-start", action="store_true")
    parser.add_argument("--settle-sec", type=float, default=1.0)
    parser.add_argument("--route-min-spacing-m", type=float, default=20.0)
    parser.add_argument("--route-z-offset-m", type=float, default=0.5)
    parser.add_argument("--route-yaw-offset-deg", type=float, default=0.0)
    parser.add_argument("--route-search-window", type=int, default=45)
    parser.add_argument("--closed-route-terminal-guard-ratio", type=float, default=0.85)
    parser.add_argument("--lookahead-m", type=float, default=28.0)
    parser.add_argument("--sample-period-sec", type=float, default=0.1)
    parser.add_argument("--sample-decimation", type=int, default=5)
    parser.add_argument("--max-duration-sec", type=float, default=900.0)
    parser.add_argument("--completion-ratio", type=float, default=0.98)
    parser.add_argument("--target-speed-mps", type=float, default=9.0)
    parser.add_argument("--turn-speed-mps", type=float, default=5.5)
    parser.add_argument(
        "--controller",
        choices=("heading", "pid", "pure_pursuit", "route_heading", "kinematic_route"),
        default="heading",
    )
    parser.add_argument("--steer-gain", type=float, default=1.25)
    parser.add_argument("--steer-sign", type=float, default=1.0)
    parser.add_argument("--pid-lateral-kp", type=float, default=1.95)
    parser.add_argument("--pid-lateral-ki", type=float, default=0.05)
    parser.add_argument("--pid-lateral-kd", type=float, default=0.2)
    parser.add_argument("--pid-longitudinal-kp", type=float, default=0.5)
    parser.add_argument("--pid-longitudinal-ki", type=float, default=0.05)
    parser.add_argument("--pid-longitudinal-kd", type=float, default=0.0)
    parser.add_argument("--pid-max-steering", type=float, default=0.65)
    parser.add_argument("--pure-pursuit-wheelbase-m", type=float, default=6.0)
    parser.add_argument("--pure-pursuit-max-steer-angle-rad", type=float, default=0.75)
    parser.add_argument("--pure-pursuit-min-forward-m", type=float, default=2.0)
    parser.add_argument("--pure-pursuit-target-search-window", type=int, default=24)
    parser.add_argument("--route-heading-cross-track-gain", type=float, default=0.08)
    parser.add_argument("--route-heading-softening-mps", type=float, default=2.0)
    parser.add_argument("--route-heading-max-steer-angle-rad", type=float, default=0.75)
    parser.add_argument("--throttle-gain", type=float, default=0.22)
    parser.add_argument("--brake-gain", type=float, default=0.20)
    parser.add_argument("--brake-heading-error-rad", type=float, default=1.1)
    parser.add_argument("--overspeed-brake-margin-mps", type=float, default=0.5)
    parser.add_argument("--max-throttle", type=float, default=0.75)
    parser.add_argument("--max-brake", type=float, default=0.8)
    parser.add_argument("--brake-after-sec", type=float, default=2.0)
    parser.add_argument("--max-speed-mps-for-pass", type=float, default=25.0)
    parser.add_argument("--min-ego-z-m-for-pass", type=float, default=-20.0)
    parser.add_argument("--max-abs-pitch-deg-for-pass", type=float, default=30.0)
    parser.add_argument("--max-abs-roll-deg-for-pass", type=float, default=30.0)
    parser.add_argument("--max-lateral-error-m-for-pass", type=float, default=18.0)
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--video-output", type=Path)
    parser.add_argument("--video-frame-dir", type=Path)
    parser.add_argument("--video-fps", type=float, default=8.0)
    parser.add_argument("--video-width", type=int, default=960)
    parser.add_argument("--video-height", type=int, default=540)
    parser.add_argument("--video-fov-deg", type=float, default=90.0)
    parser.add_argument("--video-camera-location", default="-12,0,5")
    parser.add_argument("--video-camera-rotation", default="-18,0,0")
    parser.add_argument("--keep-video-frames", action="store_true")
    return parser.parse_args()


def main() -> int:
    payload = run_probe(parse_args())
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
