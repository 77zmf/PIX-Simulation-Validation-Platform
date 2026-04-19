"""Run a CARLA-side acceptance probe for ``vehicle.pixmoving.robobus``.

The probe checks the vehicle as a CARLA test target, independent of Autoware:

- blueprint library entry exists
- actor spawns at a normal map spawn point without hovering excessively
- wheel radius/width/steer limits match the 117th vehicle metadata
- CARLA wheel steer API works for left/right steering
- throttle accelerates the vehicle and brake reduces speed

It writes ``vehicle_acceptance_summary.json`` under ``--run-dir``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


EXPECTED_WHEEL_RADIUS_CM = 32.3
EXPECTED_WHEEL_WIDTH_CM = 25.0
EXPECTED_WHEELBASE_CM = 302.0
EXPECTED_WHEEL_TREAD_CM = 161.0
EXPECTED_FRONT_STEER_DEG = 28.991
EXPECTED_REAR_STEER_DEG = 0.0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout-sec", type=float, default=30.0)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--actor-id", default="vehicle.pixmoving.robobus")
    parser.add_argument("--role-name", default="vehicle_acceptance")
    parser.add_argument("--spawn-index", type=int, default=30)
    parser.add_argument("--fixed-delta-sec", type=float, default=0.05)
    parser.add_argument("--throttle", type=float, default=0.55)
    parser.add_argument("--steer", type=float, default=0.8)
    parser.add_argument("--drive-ticks", type=int, default=140)
    parser.add_argument("--brake-ticks", type=int, default=60)
    parser.add_argument("--no-cleanup-existing", action="store_true")
    parser.add_argument("--keep-actors", action="store_true")
    return parser.parse_args(argv)


def import_carla() -> Any:
    try:
        import carla  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Unable to import carla. Set PYTHONPATH to the CARLA 0.9.15 PythonAPI egg before running."
        ) from exc
    return carla


def round_float(value: Any, digits: int = 6) -> float:
    return round(float(value), digits)


def vector3_payload(vec: Any) -> dict[str, float]:
    return {"x": round_float(vec.x), "y": round_float(vec.y), "z": round_float(vec.z)}


def rotation_payload(rot: Any) -> dict[str, float]:
    return {
        "pitch": round_float(rot.pitch),
        "yaw": round_float(rot.yaw),
        "roll": round_float(rot.roll),
    }


def speed_mps(actor: Any) -> float:
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x * velocity.x + velocity.y * velocity.y + velocity.z * velocity.z)


def distance_xy(a: Any, b: Any) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def within(value: float, expected: float, tolerance: float) -> bool:
    return abs(value - expected) <= tolerance


def nullable_round_float(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round_float(value, digits)


def wheel_payload(wheel: Any, index: int) -> dict[str, float | int | None]:
    return {
        "index": index,
        "radius_cm": round_float(getattr(wheel, "radius", 0.0)),
        "width_cm": nullable_round_float(getattr(wheel, "width", None)),
        "max_steer_angle_deg": round_float(getattr(wheel, "max_steer_angle", 0.0)),
    }


def wheel_local_position_cm(carla: Any, actor: Any, wheel: Any) -> dict[str, float]:
    raw = getattr(wheel, "position", None)
    if raw is None:
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    # CARLA 0.9.15 reports wheel position in world centimeters for runtime
    # actors. Older docs/examples sometimes treat it as local centimeters, so
    # keep a magnitude guard to support both representations.
    if max(abs(float(raw.x)), abs(float(raw.y)), abs(float(raw.z))) > 1000.0:
        world_location_m = carla.Location(x=float(raw.x) / 100.0, y=float(raw.y) / 100.0, z=float(raw.z) / 100.0)
        local_m = actor.get_transform().inverse_transform(world_location_m)
        return {"x": round_float(local_m.x * 100.0), "y": round_float(local_m.y * 100.0), "z": round_float(local_m.z * 100.0)}

    return {"x": round_float(raw.x), "y": round_float(raw.y), "z": round_float(raw.z)}


def wheel_geometry_payload(wheel_positions: list[dict[str, float]]) -> dict[str, float | list[dict[str, float]]]:
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
        "wheelbase_cm": round_float(abs(front_x - rear_x)),
        "front_tread_cm": round_float(abs(wheel_positions[1]["y"] - wheel_positions[0]["y"])),
        "rear_tread_cm": round_float(abs(wheel_positions[3]["y"] - wheel_positions[2]["y"])),
    }


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    carla = import_carla()
    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout_sec)
    world = client.get_world()
    original_settings = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = args.fixed_delta_sec
    settings.no_rendering_mode = False
    spawned: list[Any] = []

    def destroy_actor(actor: Any) -> None:
        try:
            actor.destroy()
        except Exception:
            pass

    def tick(count: int = 1) -> None:
        for _ in range(count):
            world.tick()

    def cleanup_existing() -> None:
        for pattern in ("sensor.*", "vehicle.*"):
            for actor in world.get_actors().filter(pattern):
                destroy_actor(actor)
        tick(2)

    def spawn_actor(bp: Any) -> tuple[Any, int, float]:
        spawn_points = world.get_map().get_spawn_points()
        preferred = [args.spawn_index, 0, 5, 10, 20, 30, 40, 60, 80, 100]
        z_offsets = [0.0, 0.05, 0.15, 0.30]
        tried: set[int] = set()
        for index in preferred:
            if index in tried or index >= len(spawn_points):
                continue
            tried.add(index)
            base = spawn_points[index]
            for z_offset in z_offsets:
                transform = carla.Transform(
                    base.location + carla.Vector3D(0.0, 0.0, z_offset),
                    base.rotation,
                )
                actor = world.try_spawn_actor(bp, transform)
                if actor is not None:
                    return actor, index, z_offset
        raise RuntimeError(f"Failed to spawn {args.actor_id} at normal spawn points")

    try:
        world.apply_settings(settings)
        if not args.no_cleanup_existing:
            cleanup_existing()

        blueprints = world.get_blueprint_library()
        bp = blueprints.find(args.actor_id)
        if bp.has_attribute("role_name"):
            bp.set_attribute("role_name", args.role_name)
        actor, spawn_index, spawn_z_offset = spawn_actor(bp)
        spawned.append(actor)
        tick(10)

        start_transform = actor.get_transform()
        start_location = start_transform.location
        bbox = actor.bounding_box.extent
        physics = actor.get_physics_control()
        wheels = [wheel_payload(wheel, index) for index, wheel in enumerate(physics.wheels)]
        wheel_positions = [wheel_local_position_cm(carla, actor, wheel) for wheel in physics.wheels]
        wheel_geometry = wheel_geometry_payload(wheel_positions)
        front_wheels = wheels[:2]
        rear_wheels = wheels[2:]

        actor.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))
        tick(8)
        actor.apply_control(carla.VehicleControl(throttle=0.0, brake=0.0, steer=args.steer))
        tick(20)
        left_steer_api = {
            "fl_deg": round_float(actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FL_Wheel)),
            "fr_deg": round_float(actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FR_Wheel)),
            "rl_deg": round_float(actor.get_wheel_steer_angle(carla.VehicleWheelLocation.BL_Wheel)),
            "rr_deg": round_float(actor.get_wheel_steer_angle(carla.VehicleWheelLocation.BR_Wheel)),
        }
        actor.apply_control(carla.VehicleControl(throttle=0.0, brake=0.0, steer=-args.steer))
        tick(20)
        right_steer_api = {
            "fl_deg": round_float(actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FL_Wheel)),
            "fr_deg": round_float(actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FR_Wheel)),
            "rl_deg": round_float(actor.get_wheel_steer_angle(carla.VehicleWheelLocation.BL_Wheel)),
            "rr_deg": round_float(actor.get_wheel_steer_angle(carla.VehicleWheelLocation.BR_Wheel)),
        }

        drive_samples: list[dict[str, Any]] = []
        for index in range(args.drive_ticks):
            steer = 0.0
            if args.drive_ticks * 0.25 <= index < args.drive_ticks * 0.50:
                steer = 0.18
            elif args.drive_ticks * 0.50 <= index < args.drive_ticks * 0.75:
                steer = -0.14
            actor.apply_control(carla.VehicleControl(throttle=args.throttle, brake=0.0, steer=steer))
            tick()
            if index % 20 == 0 or index == args.drive_ticks - 1:
                transform = actor.get_transform()
                drive_samples.append(
                    {
                        "tick": index,
                        "location": vector3_payload(transform.location),
                        "rotation": rotation_payload(transform.rotation),
                        "speed_mps": round_float(speed_mps(actor)),
                    }
                )
        peak_speed = max(sample["speed_mps"] for sample in drive_samples)
        speed_before_brake = speed_mps(actor)
        for _ in range(args.brake_ticks):
            actor.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))
            tick()
        speed_after_brake = speed_mps(actor)
        final_transform = actor.get_transform()
        traveled = distance_xy(start_location, final_transform.location)

        checks = {
            "blueprint_found": True,
            "spawned": True,
            "spawn_height_plausible": -1.0 <= start_transform.location.z <= 3.0,
            "bbox_plausible": 1.0 <= bbox.x <= 8.0 and 0.4 <= bbox.y <= 4.0 and 0.4 <= bbox.z <= 4.0,
            "wheel_count": len(wheels) == 4,
            "wheel_radius_match": all(within(float(w["radius_cm"]), EXPECTED_WHEEL_RADIUS_CM, 1.0) for w in wheels),
            "wheel_width_match_or_unavailable": all(
                w["width_cm"] is None or within(float(w["width_cm"]), EXPECTED_WHEEL_WIDTH_CM, 2.0)
                for w in wheels
            ),
            "wheelbase_match": within(float(wheel_geometry["wheelbase_cm"]), EXPECTED_WHEELBASE_CM, 40.0),
            "front_tread_match": within(float(wheel_geometry["front_tread_cm"]), EXPECTED_WHEEL_TREAD_CM, 30.0),
            "rear_tread_match": within(float(wheel_geometry["rear_tread_cm"]), EXPECTED_WHEEL_TREAD_CM, 30.0),
            "front_steer_limit_match": all(
                within(abs(float(w["max_steer_angle_deg"])), EXPECTED_FRONT_STEER_DEG, 2.0)
                for w in front_wheels
            ),
            "rear_steer_limit_match": all(
                within(abs(float(w["max_steer_angle_deg"])), EXPECTED_REAR_STEER_DEG, 1.0)
                for w in rear_wheels
            ),
            "wheel_steer_api_left": abs(left_steer_api["fl_deg"]) > 5.0 or abs(left_steer_api["fr_deg"]) > 5.0,
            "wheel_steer_api_right": abs(right_steer_api["fl_deg"]) > 5.0 or abs(right_steer_api["fr_deg"]) > 5.0,
            "drive_response": traveled > 8.0 and peak_speed > 2.0,
            "brake_response": speed_after_brake < max(0.8, speed_before_brake * 0.55),
            "stability": abs(final_transform.rotation.pitch) < 12.0 and abs(final_transform.rotation.roll) < 12.0,
        }

        summary = {
            "run_dir": str(run_dir),
            "map": world.get_map().name,
            "actor_id": args.actor_id,
            "passed": all(checks.values()),
            "checks": checks,
            "spawn": {
                "index": spawn_index,
                "z_offset_m": spawn_z_offset,
                "location": vector3_payload(start_transform.location),
                "rotation": rotation_payload(start_transform.rotation),
            },
            "bbox_extent_m": vector3_payload(bbox),
            "wheels": wheels,
            "wheel_geometry": wheel_geometry,
            "wheel_steer_api": {
                "left": left_steer_api,
                "right": right_steer_api,
            },
            "drive": {
                "distance_m": round_float(traveled),
                "peak_speed_mps": round_float(peak_speed),
                "speed_before_brake_mps": round_float(speed_before_brake),
                "speed_after_brake_mps": round_float(speed_after_brake),
                "final_location": vector3_payload(final_transform.location),
                "final_rotation": rotation_payload(final_transform.rotation),
                "samples": drive_samples,
            },
        }
        (run_dir / "vehicle_acceptance_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary
    finally:
        if not args.keep_actors:
            for actor in list(spawned):
                destroy_actor(actor)
        world.apply_settings(original_settings)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    summary = run_probe(args)
    print(
        json.dumps(
            {
                "run_dir": summary["run_dir"],
                "map": summary["map"],
                "actor_id": summary["actor_id"],
                "passed": summary["passed"],
                "checks": summary["checks"],
                "bbox_extent_m": summary["bbox_extent_m"],
                "wheels": summary["wheels"],
                "wheel_geometry": summary["wheel_geometry"],
                "wheel_steer_api": summary["wheel_steer_api"],
                "drive": {k: v for k, v in summary["drive"].items() if k != "samples"},
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
