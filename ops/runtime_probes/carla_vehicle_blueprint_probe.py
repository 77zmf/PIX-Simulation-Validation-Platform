#!/usr/bin/env python3
"""Probe the live PIX Robobus CARLA vehicle blueprint without taking control.

This probe is intentionally non-destructive. It connects to an already running
CARLA world, finds the ego vehicle, inspects the blueprint id, bounding box,
wheel geometry, steering limits, and attached sensors, then writes a standard
``metric_probe_*`` artifact that ``simctl finalize`` can fold into KPI gates.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_WHEEL_RADIUS_CM = 32.3
EXPECTED_WHEELBASE_CM = 302.0
EXPECTED_WHEEL_TREAD_CM = 161.0
EXPECTED_FRONT_STEER_DEG = 28.991
EXPECTED_REAR_STEER_DEG = 0.0


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _tail(value: str | bytes | None, limit: int = 2400) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[-limit:]


def _add_carla_python_paths(carla_root: str) -> None:
    if importlib.util.find_spec("carla") is not None:
        return
    root = Path(carla_root).expanduser()
    candidates = [
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.10-linux-x86_64.egg",
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.7-linux-x86_64.egg",
        root / "PythonAPI" / "carla",
    ]
    for candidate in candidates:
        if candidate.exists():
            sys.path.insert(0, str(candidate))


def _round_float(value: Any, digits: int = 6) -> float:
    return round(float(value), digits)


def _bool_metric(value: bool) -> float:
    return 1.0 if value else 0.0


def _within(value: float, expected: float, tolerance: float) -> bool:
    return abs(value - expected) <= tolerance


def _vector_payload(vec: Any) -> dict[str, float]:
    return {"x": _round_float(vec.x), "y": _round_float(vec.y), "z": _round_float(vec.z)}


def _rotation_payload(rot: Any) -> dict[str, float]:
    return {
        "pitch": _round_float(rot.pitch),
        "yaw": _round_float(rot.yaw),
        "roll": _round_float(rot.roll),
    }


def _actor_role(actor: Any) -> str:
    return str(getattr(actor, "attributes", {}).get("role_name", ""))


def _speed_mps(actor: Any) -> float:
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x * velocity.x + velocity.y * velocity.y + velocity.z * velocity.z)


def _wheel_local_position_cm(carla: Any, actor: Any, wheel: Any) -> dict[str, float]:
    raw = getattr(wheel, "position", None)
    if raw is None:
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    if max(abs(float(raw.x)), abs(float(raw.y)), abs(float(raw.z))) > 1000.0:
        world_location_m = carla.Location(x=float(raw.x) / 100.0, y=float(raw.y) / 100.0, z=float(raw.z) / 100.0)
        transform = actor.get_transform()
        dx = world_location_m.x - transform.location.x
        dy = world_location_m.y - transform.location.y
        dz = world_location_m.z - transform.location.z
        yaw_rad = math.radians(transform.rotation.yaw)
        cos_yaw = math.cos(yaw_rad)
        sin_yaw = math.sin(yaw_rad)
        local_x_m = cos_yaw * dx + sin_yaw * dy
        local_y_m = -sin_yaw * dx + cos_yaw * dy
        return {
            "x": _round_float(local_x_m * 100.0),
            "y": _round_float(local_y_m * 100.0),
            "z": _round_float(dz * 100.0),
        }

    return {"x": _round_float(raw.x), "y": _round_float(raw.y), "z": _round_float(raw.z)}


def _wheel_geometry(wheel_positions: list[dict[str, float]]) -> dict[str, Any]:
    if len(wheel_positions) < 4:
        return {
            "wheel_positions_local_cm": wheel_positions,
            "wheelbase_cm": 0.0,
            "front_tread_cm": 0.0,
            "rear_tread_cm": 0.0,
        }
    front_x = (wheel_positions[0]["x"] + wheel_positions[1]["x"]) / 2.0
    rear_x = (wheel_positions[2]["x"] + wheel_positions[3]["x"]) / 2.0
    return {
        "wheel_positions_local_cm": wheel_positions,
        "wheelbase_cm": _round_float(abs(front_x - rear_x)),
        "front_tread_cm": _round_float(abs(wheel_positions[1]["y"] - wheel_positions[0]["y"])),
        "rear_tread_cm": _round_float(abs(wheel_positions[3]["y"] - wheel_positions[2]["y"])),
    }


def _vehicle_sensor_summary(world: Any, ego_actor: Any) -> dict[str, Any]:
    sensors = []
    for actor in world.get_actors().filter("sensor.*"):
        parent = getattr(actor, "parent", None)
        if getattr(parent, "id", None) != ego_actor.id:
            continue
        sensors.append(
            {
                "id": int(actor.id),
                "type_id": str(actor.type_id),
                "role_name": _actor_role(actor),
            }
        )
    return {
        "attached_sensor_count": len(sensors),
        "attached_camera_count": sum(1 for item in sensors if item["type_id"].startswith("sensor.camera.")),
        "attached_lidar_count": sum(1 for item in sensors if item["type_id"] == "sensor.lidar.ray_cast"),
        "attached_sensors": sensors,
    }


def _find_ego_actor(world: Any, args: argparse.Namespace) -> tuple[Any | None, int]:
    vehicles = list(world.get_actors().filter("vehicle.*"))
    for actor in vehicles:
        if _actor_role(actor) == args.ego_role_name:
            return actor, len(vehicles)
    for actor in vehicles:
        if str(actor.type_id) == args.actor_id:
            return actor, len(vehicles)
    return None, len(vehicles)


def _advance_world_for_probe(world: Any) -> str:
    """Flush pending CARLA spawns before reading actor/sensor registries."""
    try:
        settings = world.get_settings()
    except RuntimeError as exc:
        return f"settings_error:{exc}"

    try:
        if getattr(settings, "synchronous_mode", False):
            frame = world.tick()
            return f"tick:{frame}"
        snapshot = world.wait_for_tick()
        return f"wait_for_tick:{getattr(snapshot, 'frame', 'unknown')}"
    except RuntimeError as exc:
        return f"advance_error:{exc}"


def _query_vehicle_summary(carla: Any, world: Any, args: argparse.Namespace, blueprint_found: bool) -> dict[str, Any]:
    probe_observations = []
    ego_actor, vehicle_count = _find_ego_actor(world, args)
    probe_observations.append({"attempt": 0, "vehicle_count": vehicle_count})

    for attempt in range(1, args.carla_probe_tick_attempts + 1):
        if ego_actor is not None:
            break
        advance_result = _advance_world_for_probe(world)
        time.sleep(args.carla_probe_tick_wait_sec)
        ego_actor, vehicle_count = _find_ego_actor(world, args)
        probe_observations.append(
            {
                "attempt": attempt,
                "advance_result": advance_result,
                "vehicle_count": vehicle_count,
            }
        )

    if ego_actor is None:
        return {
            "blueprint_found": blueprint_found,
            "ego_actor_seen": False,
            "actor_type_match": False,
            "vehicle_count": vehicle_count,
            "probe_observations": probe_observations,
            "checks": {
                "blueprint_found": blueprint_found,
                "ego_actor_seen": False,
                "actor_type_match": False,
                "pose_height_plausible": False,
                "bbox_plausible": False,
                "wheel_count": False,
                "wheel_radius_match": False,
                "wheelbase_match": False,
                "front_tread_match": False,
                "rear_tread_match": False,
                "front_steer_limit_match": False,
                "rear_steer_limit_match": False,
                "attached_sensor_count": False,
                "attached_camera_count": False,
                "attached_lidar_count": False,
            },
        }

    transform = ego_actor.get_transform()
    bbox = ego_actor.bounding_box.extent
    physics = ego_actor.get_physics_control()
    wheels = list(physics.wheels)
    wheel_positions = [_wheel_local_position_cm(carla, ego_actor, wheel) for wheel in wheels]
    geometry = _wheel_geometry(wheel_positions)
    sensor_summary = _vehicle_sensor_summary(world, ego_actor)
    wheel_payload = [
        {
            "index": index,
            "radius_cm": _round_float(getattr(wheel, "radius", 0.0)),
            "width_cm": _round_float(getattr(wheel, "width", 0.0)),
            "max_steer_angle_deg": _round_float(getattr(wheel, "max_steer_angle", 0.0)),
            "position_local_cm": wheel_positions[index],
        }
        for index, wheel in enumerate(wheels)
    ]
    front_wheels = wheel_payload[:2]
    rear_wheels = wheel_payload[2:]
    checks = {
        "blueprint_found": blueprint_found,
        "ego_actor_seen": True,
        "actor_type_match": str(ego_actor.type_id) == args.actor_id,
        "pose_height_plausible": args.min_pose_z_m <= float(transform.location.z) <= args.max_pose_z_m,
        "bbox_plausible": (
            float(bbox.x) >= args.min_bbox_extent_x_m
            and float(bbox.y) >= args.min_bbox_extent_y_m
            and float(bbox.z) >= args.min_bbox_extent_z_m
        ),
        "wheel_count": len(wheels) == 4,
        "wheel_radius_match": all(_within(float(wheel["radius_cm"]), EXPECTED_WHEEL_RADIUS_CM, 1.0) for wheel in wheel_payload),
        "wheelbase_match": _within(float(geometry["wheelbase_cm"]), EXPECTED_WHEELBASE_CM, args.wheelbase_tolerance_cm),
        "front_tread_match": _within(float(geometry["front_tread_cm"]), EXPECTED_WHEEL_TREAD_CM, args.tread_tolerance_cm),
        "rear_tread_match": _within(float(geometry["rear_tread_cm"]), EXPECTED_WHEEL_TREAD_CM, args.tread_tolerance_cm),
        "front_steer_limit_match": all(
            _within(abs(float(wheel["max_steer_angle_deg"])), EXPECTED_FRONT_STEER_DEG, 2.0)
            for wheel in front_wheels
        ),
        "rear_steer_limit_match": all(
            _within(abs(float(wheel["max_steer_angle_deg"])), EXPECTED_REAR_STEER_DEG, 1.0)
            for wheel in rear_wheels
        ),
        "attached_sensor_count": sensor_summary["attached_sensor_count"] >= args.min_attached_sensors,
        "attached_camera_count": sensor_summary["attached_camera_count"] >= args.min_attached_cameras,
        "attached_lidar_count": sensor_summary["attached_lidar_count"] >= args.min_attached_lidars,
    }

    return {
        "blueprint_found": blueprint_found,
        "ego_actor_seen": True,
        "actor_type_match": checks["actor_type_match"],
        "actor": {
            "id": int(ego_actor.id),
            "type_id": str(ego_actor.type_id),
            "role_name": _actor_role(ego_actor),
            "location_m": _vector_payload(transform.location),
            "rotation_deg": _rotation_payload(transform.rotation),
            "speed_mps": _round_float(_speed_mps(ego_actor)),
            "bbox_extent_m": _vector_payload(bbox),
            "mass_kg": _round_float(physics.mass),
        },
        "wheel_geometry": geometry,
        "wheels": wheel_payload,
        **sensor_summary,
        "probe_observations": probe_observations,
        "checks": checks,
    }


def build_metrics(summary: dict[str, Any]) -> dict[str, float]:
    checks = summary.get("checks") if isinstance(summary.get("checks"), dict) else {}
    actor = summary.get("actor") if isinstance(summary.get("actor"), dict) else {}
    bbox = actor.get("bbox_extent_m") if isinstance(actor.get("bbox_extent_m"), dict) else {}
    geometry = summary.get("wheel_geometry") if isinstance(summary.get("wheel_geometry"), dict) else {}
    return {
        "robobus_blueprint_found": _bool_metric(bool(checks.get("blueprint_found"))),
        "robobus_ego_actor_seen": _bool_metric(bool(checks.get("ego_actor_seen"))),
        "robobus_actor_type_match": _bool_metric(bool(checks.get("actor_type_match"))),
        "robobus_pose_height_plausible": _bool_metric(bool(checks.get("pose_height_plausible"))),
        "robobus_bbox_plausible": _bool_metric(bool(checks.get("bbox_plausible"))),
        "robobus_bbox_extent_x_m": float(bbox.get("x") or 0.0),
        "robobus_bbox_extent_y_m": float(bbox.get("y") or 0.0),
        "robobus_bbox_extent_z_m": float(bbox.get("z") or 0.0),
        "robobus_wheel_count": float(len(summary.get("wheels") or [])),
        "robobus_wheel_radius_match": _bool_metric(bool(checks.get("wheel_radius_match"))),
        "robobus_wheelbase_cm": float(geometry.get("wheelbase_cm") or 0.0),
        "robobus_wheelbase_match": _bool_metric(bool(checks.get("wheelbase_match"))),
        "robobus_front_tread_cm": float(geometry.get("front_tread_cm") or 0.0),
        "robobus_front_tread_match": _bool_metric(bool(checks.get("front_tread_match"))),
        "robobus_rear_tread_cm": float(geometry.get("rear_tread_cm") or 0.0),
        "robobus_rear_tread_match": _bool_metric(bool(checks.get("rear_tread_match"))),
        "robobus_front_steer_limit_match": _bool_metric(bool(checks.get("front_steer_limit_match"))),
        "robobus_rear_steer_limit_match": _bool_metric(bool(checks.get("rear_steer_limit_match"))),
        "robobus_attached_sensor_count": float(summary.get("attached_sensor_count") or 0.0),
        "robobus_attached_camera_count": float(summary.get("attached_camera_count") or 0.0),
        "robobus_attached_lidar_count": float(summary.get("attached_lidar_count") or 0.0),
    }


def _failed_checks(summary: dict[str, Any]) -> list[str]:
    checks = summary.get("checks") if isinstance(summary.get("checks"), dict) else {}
    return [name for name, passed in checks.items() if not passed]


def _payload_from_summary(args: argparse.Namespace, summary: dict[str, Any]) -> dict[str, Any]:
    metrics = build_metrics(summary)
    failed_checks = _failed_checks(summary)
    overall_passed = not failed_checks
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "robobus_vehicle_blueprint_probe",
        "profile": args.profile,
        "overall_passed": overall_passed,
        "blocked_reason": None if overall_passed else "failed_checks:" + ",".join(failed_checks),
        "missing_metrics": [],
        "missing_topics": [],
        "sample_missing_topics": [],
        "metrics": metrics,
        "summary": summary,
        "assumptions": [
            "probe is non-destructive and does not apply VehicleControl",
            "throttle/brake dynamics remain covered by validate_carla_vehicle_acceptance.py in isolated CARLA sessions",
        ],
    }


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    _add_carla_python_paths(args.carla_root)
    try:
        import carla  # type: ignore
    except Exception as exc:
        summary = {
            "blueprint_found": False,
            "ego_actor_seen": False,
            "actor_type_match": False,
            "checks": {
                "blueprint_found": False,
                "ego_actor_seen": False,
                "actor_type_match": False,
                "pose_height_plausible": False,
                "bbox_plausible": False,
                "wheel_count": False,
                "wheel_radius_match": False,
                "wheelbase_match": False,
                "front_tread_match": False,
                "rear_tread_match": False,
                "front_steer_limit_match": False,
                "rear_steer_limit_match": False,
                "attached_sensor_count": False,
                "attached_camera_count": False,
                "attached_lidar_count": False,
            },
            "import_error": str(exc),
        }
        return _payload_from_summary(args, summary)

    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(args.carla_timeout_sec)
    world = client.get_world()
    blueprint_matches = [bp.id for bp in world.get_blueprint_library().filter(args.actor_id)]
    summary = _query_vehicle_summary(carla, world, args, args.actor_id in blueprint_matches)
    summary["map"] = world.get_map().name if world.get_map() else None
    summary["blueprint_matches"] = blueprint_matches
    return _payload_from_summary(args, summary)


def _worker_failure_payload(args: argparse.Namespace, reason: str, details: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "blueprint_found": False,
        "ego_actor_seen": False,
        "actor_type_match": False,
        "pose_height_plausible": False,
        "bbox_plausible": False,
        "wheel_count": False,
        "wheel_radius_match": False,
        "wheelbase_match": False,
        "front_tread_match": False,
        "rear_tread_match": False,
        "front_steer_limit_match": False,
        "rear_steer_limit_match": False,
        "attached_sensor_count": False,
        "attached_camera_count": False,
        "attached_lidar_count": False,
    }
    summary = {"checks": checks, "worker": details}
    payload = _payload_from_summary(args, summary)
    payload["blocked_reason"] = reason
    return payload


def write_artifacts(run_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    stamp = _utc_stamp()
    output_dir = run_dir / "runtime_verification" / f"metric_probe_robobus_vehicle_blueprint_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"metric_probe_robobus_vehicle_blueprint_{stamp}.json"
    summary = output_dir / "metric_probe_robobus_vehicle_blueprint_summary.json"
    artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary.write_text(
        json.dumps(
            {
                "overall_passed": payload["overall_passed"],
                "blocked_reason": payload["blocked_reason"],
                "metrics": payload["metrics"],
                "summary": payload["summary"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"artifact": str(artifact), "summary_path": str(summary)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", default="robobus117th_vehicle_blueprint")
    parser.add_argument("--carla-host", default=os.environ.get("SIMCTL_CARLA_HOST", "127.0.0.1"))
    parser.add_argument("--carla-port", type=int, default=int(os.environ.get("SIMCTL_CARLA_RPC_PORT", "2000")))
    parser.add_argument(
        "--carla-root",
        default=os.environ.get("CARLA_ROOT", os.environ.get("CARLA_0915_ROOT", str(Path.home() / "CARLA_0.9.15"))),
    )
    parser.add_argument("--carla-timeout-sec", type=float, default=15.0)
    parser.add_argument("--actor-id", default="vehicle.pixmoving.robobus")
    parser.add_argument("--ego-role-name", default="ego_vehicle")
    parser.add_argument("--min-pose-z-m", type=float, default=-1.0)
    parser.add_argument("--max-pose-z-m", type=float, default=3.0)
    parser.add_argument("--min-bbox-extent-x-m", type=float, default=1.0)
    parser.add_argument("--min-bbox-extent-y-m", type=float, default=0.4)
    parser.add_argument("--min-bbox-extent-z-m", type=float, default=0.4)
    parser.add_argument("--wheelbase-tolerance-cm", type=float, default=40.0)
    parser.add_argument("--tread-tolerance-cm", type=float, default=30.0)
    parser.add_argument("--min-attached-sensors", type=int, default=13)
    parser.add_argument("--min-attached-cameras", type=int, default=6)
    parser.add_argument("--min-attached-lidars", type=int, default=5)
    parser.add_argument("--carla-probe-tick-attempts", type=int, default=int(os.environ.get("SIMCTL_CARLA_PROBE_TICK_ATTEMPTS", "3")))
    parser.add_argument("--carla-probe-tick-wait-sec", type=float, default=float(os.environ.get("SIMCTL_CARLA_PROBE_TICK_WAIT_SEC", "0.1")))
    parser.add_argument("--worker-timeout-sec", type=float, default=120.0)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_args = list(argv if argv is not None else sys.argv[1:])
    args = build_parser().parse_args(raw_args)
    if not args.worker:
        command = [sys.executable, str(Path(__file__).resolve()), *raw_args, "--worker"]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONFAULTHANDLER"] = "1"
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=args.worker_timeout_sec,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            payload = _worker_failure_payload(
                args,
                "robobus_vehicle_blueprint_worker_timeout",
                {
                    "command": command,
                    "timeout_sec": args.worker_timeout_sec,
                    "stdout_tail": _tail(exc.stdout),
                    "stderr_tail": _tail(exc.stderr),
                },
            )
            outputs = write_artifacts(Path(args.run_dir), payload)
            print(json.dumps({**payload, "artifacts": outputs}, indent=2, ensure_ascii=False))
            return 1

        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
        if completed.returncode < 0 or completed.returncode >= 128:
            payload = _worker_failure_payload(
                args,
                "robobus_vehicle_blueprint_worker_crashed",
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout_tail": _tail(completed.stdout),
                    "stderr_tail": _tail(completed.stderr),
                },
            )
            outputs = write_artifacts(Path(args.run_dir), payload)
            print(json.dumps({**payload, "artifacts": outputs}, indent=2, ensure_ascii=False))
            return 1
        return completed.returncode

    payload = run_probe(args)
    outputs = write_artifacts(Path(args.run_dir), payload)
    print(json.dumps({**payload, "artifacts": outputs}, indent=2, ensure_ascii=False))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
