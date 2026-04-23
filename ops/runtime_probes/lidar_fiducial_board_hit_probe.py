#!/usr/bin/env python3
"""Verify lidar rays intersect imported fiducial calibration-board surfaces."""

from __future__ import annotations

import argparse
import json
import math
import queue
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment error path
    raise SystemExit("Missing PyYAML. Install python3-yaml or pip install pyyaml.") from exc


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def find_scene_spawn_artifact(run_dir: Path, explicit_path: Optional[str]) -> Optional[Path]:
    if explicit_path:
        path = Path(explicit_path)
        return path if path.exists() else None
    scene_dir = run_dir / "runtime_verification" / "calibration_scene"
    candidates = sorted(scene_dir.glob("*_spawn.json")) if scene_dir.exists() else []
    return candidates[-1] if candidates else None


def _arg(args: argparse.Namespace, name: str, default: Any) -> Any:
    return getattr(args, name, default)


def vector_add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vector_sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vector_scale(a: tuple[float, float, float], value: float) -> tuple[float, float, float]:
    return (a[0] * value, a[1] * value, a[2] * value)


def dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a: tuple[float, float, float]) -> float:
    return math.sqrt(dot(a, a))


def normalized(a: tuple[float, float, float]) -> tuple[float, float, float]:
    length = norm(a)
    if length <= 1e-9:
        return (0.0, 0.0, 0.0)
    return (a[0] / length, a[1] / length, a[2] / length)


def board_axes(local_pose: dict[str, Any]) -> dict[str, tuple[float, float, float]]:
    yaw = math.radians(float(local_pose.get("yaw_deg") or 0.0))
    normal = (math.cos(yaw), math.sin(yaw), 0.0)
    lateral = (-math.sin(yaw), math.cos(yaw), 0.0)
    up = (0.0, 0.0, 1.0)
    return {"normal": normal, "lateral": lateral, "up": up}


def board_center(local_pose: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(local_pose.get("x") or 0.0),
        float(local_pose.get("y") or 0.0),
        float(local_pose.get("z") or 0.0),
    )


def board_samples(target: dict[str, Any], grid: int) -> list[tuple[float, float, float]]:
    local_pose = target.get("local_pose") or {}
    size_m = target.get("size_m") or [1.2, 1.2]
    width_m = float(size_m[0])
    height_m = float(size_m[1])
    center = board_center(local_pose)
    axes = board_axes(local_pose)
    samples: list[tuple[float, float, float]] = []
    grid = max(2, grid)
    for yi in range(grid):
        lateral_offset = -width_m / 2.0 + width_m * (yi + 0.5) / grid
        for zi in range(grid):
            up_offset = -height_m / 2.0 + height_m * (zi + 0.5) / grid
            point = vector_add(
                vector_add(center, vector_scale(axes["lateral"], lateral_offset)),
                vector_scale(axes["up"], up_offset),
            )
            samples.append(point)
    return samples


def lidar_origin(lidar_payload: dict[str, Any]) -> tuple[float, float, float]:
    transform = lidar_payload.get("transform") or {}
    return (
        float(transform.get("x") or 0.0),
        float(transform.get("y") or 0.0),
        float(transform.get("z") or 0.0),
    )


def point_hits_board_from_lidar(
    lidar: dict[str, Any],
    target: dict[str, Any],
    point: tuple[float, float, float],
    min_range_m: float,
    max_range_m: float,
    min_incidence_cos: float,
) -> bool:
    origin = lidar_origin(lidar)
    ray = vector_sub(point, origin)
    distance = norm(ray)
    if distance < min_range_m or distance > max_range_m:
        return False
    direction = normalized(ray)
    axes = board_axes(target.get("local_pose") or {})
    incidence = abs(dot(direction, normalized(axes["normal"])))
    return incidence >= min_incidence_cos


def fiducial_targets_from_scene(scene_payload: dict[str, Any]) -> list[dict[str, Any]]:
    spawned_by_id = {
        str(target.get("target_id")): target
        for target in scene_payload.get("spawned", [])
        if isinstance(target, dict)
    }
    targets = []
    for target in scene_payload.get("targets") or []:
        if not isinstance(target, dict):
            continue
        if target.get("kind") != "fiducial_board" or not isinstance(target.get("local_pose"), dict):
            continue
        merged = dict(target)
        spawned = spawned_by_id.get(str(target.get("target_id"))) or {}
        if isinstance(spawned.get("world_transform"), dict):
            merged["world_transform"] = spawned["world_transform"]
        targets.append(merged)
    return targets


def load_carla_module() -> Any:
    try:
        import carla  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - host-only path
        raise SystemExit("CARLA PythonAPI is required when --capture-from-carla is set.") from exc
    return carla


def find_ego_actor(world: Any, role_name_value: str, attempts: int = 5, sleep_sec: float = 1.0) -> Any:
    accepted_roles = {role_name_value, "ego_vehicle", "hero", "autoware_v1"}
    last_vehicle_count = 0
    for attempt_index in range(max(1, attempts)):
        vehicles = list(world.get_actors().filter("vehicle.*"))
        last_vehicle_count = len(vehicles)
        candidates = [actor for actor in vehicles if actor.attributes.get("role_name") in accepted_roles]
        if candidates:
            return candidates[0]
        if attempt_index < attempts - 1:
            try:
                world.wait_for_tick()
            except Exception:
                time.sleep(sleep_sec)
    raise RuntimeError(
        f"Unable to find ego vehicle with role_name={role_name_value}; "
        f"vehicle_count={last_vehicle_count}"
    )


def carla_lidar_transform(carla: Any, lidar_payload: dict[str, Any]) -> Any:
    transform = lidar_payload.get("transform") or {}
    return carla.Transform(
        carla.Location(
            x=float(transform.get("x") or 0.0),
            y=-float(transform.get("y") or 0.0),
            z=float(transform.get("z") or 0.0),
        ),
        carla.Rotation(
            roll=math.degrees(float(transform.get("roll") or 0.0)),
            pitch=-math.degrees(float(transform.get("pitch") or 0.0)),
            yaw=-math.degrees(float(transform.get("yaw") or 0.0)),
        ),
    )


def board_axes_from_world_transform(world_transform: dict[str, Any]) -> dict[str, tuple[float, float, float]]:
    yaw = math.radians(float(world_transform.get("yaw") or 0.0))
    normal = (math.cos(yaw), math.sin(yaw), 0.0)
    lateral = (-math.sin(yaw), math.cos(yaw), 0.0)
    up = (0.0, 0.0, 1.0)
    return {"normal": normal, "lateral": lateral, "up": up}


def point_hits_board_surface(
    point: tuple[float, float, float],
    target: dict[str, Any],
    plane_tolerance_m: float,
    edge_margin_m: float,
) -> bool:
    world_transform = target.get("world_transform")
    if not isinstance(world_transform, dict):
        return False
    size_m = target.get("size_m") or [1.2, 1.2]
    width_m = float(size_m[0])
    height_m = float(size_m[1])
    center = (
        float(world_transform.get("x") or 0.0),
        float(world_transform.get("y") or 0.0),
        float(world_transform.get("z") or 0.0),
    )
    axes = board_axes_from_world_transform(world_transform)
    relative = vector_sub(point, center)
    plane_distance_m = abs(dot(relative, normalized(axes["normal"])))
    lateral_m = abs(dot(relative, normalized(axes["lateral"])))
    height_m_abs = abs(dot(relative, axes["up"]))
    return (
        plane_distance_m <= plane_tolerance_m
        and lateral_m <= (width_m / 2.0 + edge_margin_m)
        and height_m_abs <= (height_m / 2.0 + edge_margin_m)
    )


def set_blueprint_attribute(blueprint: Any, name: str, value: Any) -> None:
    if hasattr(blueprint, "has_attribute") and blueprint.has_attribute(name):
        blueprint.set_attribute(name, str(value))


def world_points_from_lidar_measurement(carla: Any, measurement: Any) -> list[tuple[float, float, float, float]]:
    transform = getattr(measurement, "transform", None)
    if transform is None:
        return []
    points: list[tuple[float, float, float, float]] = []
    for x, y, z, intensity in struct.iter_unpack("ffff", bytes(measurement.raw_data)):
        location = transform.transform(carla.Location(x=float(x), y=float(y), z=float(z)))
        points.append((float(location.x), float(location.y), float(location.z), float(intensity)))
    return points


def capture_lidar_points_from_carla(
    args: argparse.Namespace,
    lidars: dict[str, Any],
    fiducial_targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    carla = load_carla_module()
    client = carla.Client(_arg(args, "carla_host", "127.0.0.1"), int(_arg(args, "carla_port", 2000)))
    client.set_timeout(float(_arg(args, "carla_timeout", 10.0)))
    world = client.get_world()
    ego = find_ego_actor(world, str(_arg(args, "ego_vehicle_role_name", "ego_vehicle")))
    blueprint = world.get_blueprint_library().find("sensor.lidar.ray_cast")
    set_blueprint_attribute(blueprint, "channels", int(_arg(args, "lidar_channels", 64)))
    set_blueprint_attribute(blueprint, "range", float(_arg(args, "lidar_range_m", 100.0)))
    set_blueprint_attribute(blueprint, "points_per_second", int(_arg(args, "lidar_points_per_second", 300000)))
    set_blueprint_attribute(blueprint, "rotation_frequency", float(_arg(args, "lidar_rotation_frequency", 10.0)))
    set_blueprint_attribute(blueprint, "upper_fov", float(_arg(args, "lidar_upper_fov", 15.0)))
    set_blueprint_attribute(blueprint, "lower_fov", float(_arg(args, "lidar_lower_fov", -30.0)))

    results: list[dict[str, Any]] = []
    for lidar_id, lidar_payload in lidars.items():
        lidar_queue: queue.Queue[Any] = queue.Queue(maxsize=1)

        def enqueue_lidar(measurement: Any) -> None:
            try:
                lidar_queue.put_nowait(measurement)
            except queue.Full:
                pass

        sensor = world.spawn_actor(blueprint, carla_lidar_transform(carla, lidar_payload), attach_to=ego)
        try:
            sensor.listen(enqueue_lidar)
            measurements = []
            deadline = time.monotonic() + float(_arg(args, "capture_timeout_sec", 20.0))
            while time.monotonic() <= deadline and len(measurements) < int(_arg(args, "lidar_frame_count", 3)):
                try:
                    measurements.append(lidar_queue.get(timeout=1.0))
                except queue.Empty:
                    try:
                        world.wait_for_tick()
                    except RuntimeError:
                        time.sleep(0.1)
            if not measurements:
                results.append(
                    {
                        "lidar_id": lidar_id,
                        "topic": lidar_payload.get("topic"),
                        "capture_status": "timeout",
                        "captured_point_count": 0,
                        "hit_count": 0,
                        "hit_board_count": 0,
                        "boards": [],
                    }
                )
                continue
            points = []
            for measurement in measurements:
                points.extend(world_points_from_lidar_measurement(carla, measurement))
            board_hits = {str(target.get("target_id")): 0 for target in fiducial_targets}
            hit_samples = []
            for point in points:
                xyz = (point[0], point[1], point[2])
                for target in fiducial_targets:
                    target_id = str(target.get("target_id"))
                    if point_hits_board_surface(
                        xyz,
                        target,
                        float(_arg(args, "board_plane_tolerance_m", 0.35)),
                        float(_arg(args, "board_edge_margin_m", 0.25)),
                    ):
                        board_hits[target_id] += 1
                        if len(hit_samples) < int(_arg(args, "max_saved_hit_points", 40)):
                            hit_samples.append(
                                {
                                    "target_id": target_id,
                                    "x": point[0],
                                    "y": point[1],
                                    "z": point[2],
                                    "intensity": point[3],
                                }
                            )
                        break
            boards = [
                {
                    "target_id": target_id,
                    "hit_count": hit_count,
                    "sample_count": len(points),
                    "hit_ratio": hit_count / float(len(points)) if points else 0.0,
                }
                for target_id, hit_count in board_hits.items()
            ]
            results.append(
                {
                    "lidar_id": lidar_id,
                    "topic": lidar_payload.get("topic"),
                    "capture_status": "captured",
                    "frame_count": len(measurements),
                    "frames": [int(getattr(measurement, "frame", 0)) for measurement in measurements],
                    "timestamp_start": float(getattr(measurements[0], "timestamp", 0.0)),
                    "timestamp_end": float(getattr(measurements[-1], "timestamp", 0.0)),
                    "captured_point_count": len(points),
                    "hit_count": sum(board_hits.values()),
                    "hit_board_count": sum(1 for value in board_hits.values() if value > 0),
                    "hit_points_sample": hit_samples,
                    "boards": boards,
                }
            )
        finally:
            try:
                sensor.stop()
            except RuntimeError:
                pass
            try:
                sensor.destroy()
            except RuntimeError:
                pass
    return results


def geometry_lidar_board_hits(
    args: argparse.Namespace,
    lidars: dict[str, Any],
    fiducial_targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lidar_results = []
    for lidar_id, lidar_payload in lidars.items():
        lidar_hit_count = 0
        board_results = []
        for target in fiducial_targets:
            samples = board_samples(target, int(_arg(args, "board_sample_grid", 9)))
            hit_count = sum(
                1
                for point in samples
                if point_hits_board_from_lidar(
                    lidar_payload,
                    target,
                    point,
                    float(_arg(args, "min_range_m", 0.5)),
                    float(_arg(args, "max_range_m", 100.0)),
                    float(_arg(args, "min_incidence_cos", 0.08)),
                )
            )
            lidar_hit_count += hit_count
            board_results.append(
                {
                    "target_id": target.get("target_id"),
                    "hit_count": hit_count,
                    "sample_count": len(samples),
                    "hit_ratio": hit_count / float(len(samples)) if samples else 0.0,
                }
            )
        lidar_results.append(
            {
                "lidar_id": lidar_id,
                "topic": lidar_payload.get("topic"),
                "capture_status": "geometry_only",
                "hit_count": lidar_hit_count,
                "hit_board_count": sum(1 for board in board_results if board["hit_count"] > 0),
                "boards": board_results,
            }
        )
    return lidar_results


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir).resolve()
    scene_artifact_path = find_scene_spawn_artifact(run_dir, args.scene_spawn_artifact)
    scene_payload = load_json(scene_artifact_path) if scene_artifact_path else {}
    sensor_payload = load_yaml(Path(args.sensor_calibration).resolve())
    fiducial_targets = fiducial_targets_from_scene(scene_payload)
    lidars = sensor_payload.get("lidars") or {}
    hit_board_ids: set[str] = set()

    capture_from_carla = bool(_arg(args, "capture_from_carla", False))
    lidar_results = (
        capture_lidar_points_from_carla(args, lidars, fiducial_targets)
        if capture_from_carla
        else geometry_lidar_board_hits(args, lidars, fiducial_targets)
    )

    total_hit_count = sum(int(result.get("hit_count") or 0) for result in lidar_results)
    for result in lidar_results:
        for board in result.get("boards", []):
            hit_count = int(board.get("hit_count") or 0)
            if hit_count > 0:
                hit_board_ids.add(str(board.get("target_id")))

    lidar_hit_count = sum(1 for result in lidar_results if result["hit_count"] > 0)
    board_hit_count = len(hit_board_ids)
    missing_reasons = []
    if not scene_artifact_path:
        missing_reasons.append("missing_scene_spawn_artifact")
    if total_hit_count < args.min_total_hit_count:
        missing_reasons.append("insufficient_total_lidar_board_hits")
    if board_hit_count < args.min_boards_hit:
        missing_reasons.append("insufficient_boards_hit")
    if lidar_hit_count < args.min_lidars_hit:
        missing_reasons.append("insufficient_lidars_hit")

    output_dir = (
        run_dir
        / "runtime_verification"
        / f"metric_probe_lidar_fiducial_board_hits_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": utc_now(),
        "profile": "lidar_fiducial_board_hits",
        "capture_mode": "carla_lidar_ray_cast" if capture_from_carla else "geometry_board_roi",
        "scene_spawn_artifact": str(scene_artifact_path) if scene_artifact_path else None,
        "sensor_calibration": str(Path(args.sensor_calibration).resolve()),
        "overall_passed": not missing_reasons,
        "blocked_reason": ",".join(missing_reasons) if missing_reasons else None,
        "missing_metrics": [],
        "missing_topics": [],
        "sample_missing_topics": [],
        "metrics": {
            "lidar_board_hit_count": float(total_hit_count),
            "lidar_board_hit_board_count": float(board_hit_count),
            "lidar_board_hit_lidar_count": float(lidar_hit_count),
            "lidar_board_hit_coverage": board_hit_count / float(len(fiducial_targets)) if fiducial_targets else 0.0,
        },
        "target_count": len(fiducial_targets),
        "lidar_count": len(lidar_results),
        "lidars": lidar_results,
    }
    output_path = output_dir / "lidar_fiducial_board_hits.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["result_path"] = str(output_path)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--scene-spawn-artifact")
    parser.add_argument("--sensor-calibration", default="assets/calibration/lidar_sensor_kit_truth.yaml")
    parser.add_argument("--board-sample-grid", type=int, default=9)
    parser.add_argument("--min-range-m", type=float, default=0.5)
    parser.add_argument("--max-range-m", type=float, default=100.0)
    parser.add_argument("--min-incidence-cos", type=float, default=0.08)
    parser.add_argument("--min-total-hit-count", type=int, default=80)
    parser.add_argument("--min-boards-hit", type=int, default=4)
    parser.add_argument("--min-lidars-hit", type=int, default=1)
    parser.add_argument("--capture-from-carla", action="store_true")
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=2000)
    parser.add_argument("--carla-timeout", type=float, default=10.0)
    parser.add_argument("--ego-vehicle-role-name", default="ego_vehicle")
    parser.add_argument("--capture-timeout-sec", type=float, default=20.0)
    parser.add_argument("--lidar-frame-count", type=int, default=3)
    parser.add_argument("--lidar-channels", type=int, default=64)
    parser.add_argument("--lidar-range-m", type=float, default=100.0)
    parser.add_argument("--lidar-points-per-second", type=int, default=300000)
    parser.add_argument("--lidar-rotation-frequency", type=float, default=10.0)
    parser.add_argument("--lidar-upper-fov", type=float, default=15.0)
    parser.add_argument("--lidar-lower-fov", type=float, default=-30.0)
    parser.add_argument("--board-plane-tolerance-m", type=float, default=0.35)
    parser.add_argument("--board-edge-margin-m", type=float, default=0.25)
    parser.add_argument("--max-saved-hit-points", type=int, default=40)
    return parser.parse_args()


def main() -> int:
    payload = run_probe(parse_args())
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
