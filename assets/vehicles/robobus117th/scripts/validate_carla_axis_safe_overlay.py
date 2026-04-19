"""Validate the Robobus117th axis-safe visual shell in a running CARLA server.

This script is a pragmatic runtime check for the current Robobus117th import:
use a stable CARLA vehicle as the physics/sensor carrier, attach the
``vehicle.pixmoving.robobus`` actor as a non-physical, non-colliding visual
shell, and capture deterministic evidence.

It does not start CARLA. Start the runtime first, then run for example:

    export PYTHONPATH=/path/to/carla-0.9.15-py3.10-linux-x86_64.egg:${PYTHONPATH:-}
    python3 assets/vehicles/robobus117th/scripts/validate_carla_axis_safe_overlay.py \
      --run-dir runs/robobus_axis_safe_overlay \
      --record-video
"""

from __future__ import annotations

import argparse
import json
import math
import queue
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="CARLA RPC host.")
    parser.add_argument("--port", type=int, default=2000, help="CARLA RPC port.")
    parser.add_argument("--timeout-sec", type=float, default=30.0, help="CARLA client timeout.")
    parser.add_argument("--run-dir", required=True, help="Directory for summary, screenshots, and video frames.")
    parser.add_argument("--carrier-id", default="vehicle.nissan.micra", help="Stable physical carrier blueprint.")
    parser.add_argument("--visual-id", default="vehicle.pixmoving.robobus", help="Robobus visual shell blueprint.")
    parser.add_argument("--role-name", default="hero", help="Role name assigned to the physical carrier.")
    parser.add_argument("--visual-role-name", default="pix_visual_shell", help="Role name assigned to the visual shell.")
    parser.add_argument("--spawn-index", type=int, default=30, help="Preferred CARLA spawn point index.")
    parser.add_argument("--seed-spawn-index", type=int, default=0, help="Safe seed spawn point for the visual shell.")
    parser.add_argument("--z-offset", type=float, default=0.10, help="Visual shell z offset above the carrier.")
    parser.add_argument("--yaw-offset-deg", type=float, default=0.0, help="Visual shell yaw offset relative to carrier.")
    parser.add_argument("--ticks", type=int, default=170, help="Validation drive duration in synchronous ticks.")
    parser.add_argument("--fixed-delta-sec", type=float, default=0.05, help="Synchronous mode fixed delta seconds.")
    parser.add_argument("--throttle", type=float, default=0.34, help="Carrier throttle command.")
    parser.add_argument("--left-steer", type=float, default=0.18, help="First steering pulse.")
    parser.add_argument("--right-steer", type=float, default=-0.12, help="Second steering pulse.")
    parser.add_argument("--frame-stride", type=int, default=2, help="Record every Nth tick when --record-video is set.")
    parser.add_argument("--record-video", action="store_true", help="Record frames and encode MP4 with ffmpeg.")
    parser.add_argument("--video-fps", type=int, default=20, help="Output MP4 frame rate.")
    parser.add_argument("--no-cleanup-existing", action="store_true", help="Do not destroy existing vehicle/sensor actors first.")
    parser.add_argument("--keep-actors", action="store_true", help="Leave spawned actors in CARLA after validation.")
    return parser.parse_args(argv)


def import_carla() -> Any:
    try:
        import carla  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Unable to import carla. Set PYTHONPATH to the CARLA 0.9.15 PythonAPI egg before running."
        ) from exc
    return carla


def vector_norm_xy(a: Any, b: Any) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def round_vector3(vec: Any) -> list[float]:
    return [round(float(vec.x), 6), round(float(vec.y), 6), round(float(vec.z), 6)]


def round_rotation(rot: Any) -> list[float]:
    return [round(float(rot.pitch), 6), round(float(rot.yaw), 6), round(float(rot.roll), 6)]


def run_validation(args: argparse.Namespace) -> dict[str, Any]:
    carla = import_carla()
    run_dir = Path(args.run_dir)
    frames_dir = run_dir / "frames"
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.record_video:
        frames_dir.mkdir(parents=True, exist_ok=True)

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout_sec)
    world = client.get_world()
    blueprint_library = world.get_blueprint_library()
    spawn_points = world.get_map().get_spawn_points()
    if not spawn_points:
        raise RuntimeError("CARLA map has no spawn points")

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

    def cleanup_existing() -> None:
        for pattern in ("sensor.*", "vehicle.*"):
            for actor in world.get_actors().filter(pattern):
                destroy_actor(actor)
        try:
            world.tick()
        except Exception:
            pass

    def visual_transform_from(carrier: Any) -> Any:
        transform = carrier.get_transform()
        rotation = carla.Rotation(
            pitch=transform.rotation.pitch,
            yaw=transform.rotation.yaw + args.yaw_offset_deg,
            roll=transform.rotation.roll,
        )
        return carla.Transform(transform.location + carla.Vector3D(0.0, 0.0, args.z_offset), rotation)

    def capture_screenshot(visual: Any, name: str) -> str:
        transform = visual.get_transform()
        yaw = math.radians(transform.rotation.yaw - args.yaw_offset_deg)
        forward = carla.Vector3D(math.cos(yaw), math.sin(yaw), 0.0)
        right = carla.Vector3D(-math.sin(yaw), math.cos(yaw), 0.0)
        camera_bp = blueprint_library.find("sensor.camera.rgb")
        camera_bp.set_attribute("image_size_x", "1280")
        camera_bp.set_attribute("image_size_y", "720")
        camera_bp.set_attribute("fov", "65")
        camera_transform = carla.Transform(
            transform.location - forward * 7.5 + right * 3.2 + carla.Vector3D(0.0, 0.0, 3.2),
            carla.Rotation(pitch=-16.0, yaw=math.degrees(yaw) - 18.0, roll=0.0),
        )
        camera = world.spawn_actor(camera_bp, camera_transform)
        spawned.append(camera)
        images: queue.Queue[Any] = queue.Queue()
        camera.listen(images.put)
        for _ in range(5):
            world.tick()
        image = images.get(timeout=5)
        screenshot_path = run_dir / f"{name}.png"
        image.save_to_disk(str(screenshot_path))
        camera.stop()
        destroy_actor(camera)
        spawned.remove(camera)
        return str(screenshot_path)

    def encode_video() -> str | None:
        if not args.record_video:
            return None
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None
        video_path = run_dir / f"{args.visual_id.replace('.', '_')}_axis_safe_overlay.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                str(args.video_fps),
                "-i",
                str(frames_dir / "frame_%05d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(video_path),
            ],
            check=True,
        )
        return str(video_path)

    try:
        world.apply_settings(settings)
        if not args.no_cleanup_existing:
            cleanup_existing()

        visual_bp = blueprint_library.find(args.visual_id)
        if visual_bp.has_attribute("role_name"):
            visual_bp.set_attribute("role_name", args.visual_role_name)
        seed_index = min(args.seed_spawn_index, len(spawn_points) - 1)
        seed_source = spawn_points[seed_index]
        seed_transform = carla.Transform(
            seed_source.location + carla.Vector3D(0.0, 0.0, 2.0),
            seed_source.rotation,
        )
        visual = world.try_spawn_actor(visual_bp, seed_transform)
        if visual is None:
            raise RuntimeError(f"Failed to spawn visual shell {args.visual_id} at seed index {seed_index}")
        spawned.append(visual)
        visual.set_simulate_physics(False)
        visual.set_collisions(False)
        try:
            visual.set_enable_gravity(False)
        except Exception:
            pass
        for _ in range(3):
            world.tick()

        carrier_bp = blueprint_library.find(args.carrier_id)
        if carrier_bp.has_attribute("role_name"):
            carrier_bp.set_attribute("role_name", args.role_name)
        preferred_indices = [args.spawn_index, 0, 5, 10, 20, 30, 40, 60, 80, 100, 120]
        carrier = None
        spawn_index = None
        for index in preferred_indices:
            if index >= len(spawn_points):
                continue
            carrier = world.try_spawn_actor(carrier_bp, spawn_points[index])
            if carrier is not None:
                spawn_index = index
                break
        if carrier is None:
            raise RuntimeError(f"Failed to spawn carrier {args.carrier_id}")
        spawned.append(carrier)

        for _ in range(8):
            visual.set_transform(visual_transform_from(carrier))
            world.tick()

        camera = None
        frame_queue: queue.Queue[Any] | None = None
        if args.record_video:
            camera_bp = blueprint_library.find("sensor.camera.rgb")
            camera_bp.set_attribute("image_size_x", "1280")
            camera_bp.set_attribute("image_size_y", "720")
            camera_bp.set_attribute("fov", "70")
            camera = world.spawn_actor(
                camera_bp,
                carla.Transform(
                    carla.Location(x=-7.5, y=3.2, z=3.2),
                    carla.Rotation(pitch=-15.0, yaw=-18.0, roll=0.0),
                ),
                attach_to=visual,
            )
            spawned.append(camera)
            frame_queue = queue.Queue()
            camera.listen(frame_queue.put)

        start_location = carrier.get_transform().location
        samples: list[dict[str, Any]] = []
        frame_count = 0
        for tick in range(args.ticks):
            if args.ticks * 0.15 <= tick < args.ticks * 0.45:
                steer = args.left_steer
            elif args.ticks * 0.45 <= tick < args.ticks * 0.70:
                steer = args.right_steer
            else:
                steer = 0.0
            carrier.apply_control(carla.VehicleControl(throttle=args.throttle, steer=steer, brake=0.0))
            visual.set_transform(visual_transform_from(carrier))
            world.tick()

            if frame_queue is not None:
                image = frame_queue.get(timeout=5)
                if tick % max(args.frame_stride, 1) == 0:
                    image.save_to_disk(str(frames_dir / f"frame_{frame_count:05d}.png"))
                    frame_count += 1

            if tick % 20 == 0 or tick == args.ticks - 1:
                transform = carrier.get_transform()
                visual_transform = visual.get_transform()
                velocity = carrier.get_velocity()
                samples.append(
                    {
                        "tick": tick,
                        "carrier_location": round_vector3(transform.location),
                        "carrier_rotation": round_rotation(transform.rotation),
                        "visual_location": round_vector3(visual_transform.location),
                        "visual_rotation": round_rotation(visual_transform.rotation),
                        "speed_mps": round(math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2), 6),
                    }
                )

        if camera is not None:
            camera.stop()

        screenshot = capture_screenshot(visual, f"{args.carrier_id.replace('.', '_')}_axis_safe_overlay")
        final_location = carrier.get_transform().location
        carrier_box = carrier.bounding_box.extent
        visual_box = visual.bounding_box.extent
        max_speed = max(sample["speed_mps"] for sample in samples)
        max_pitch = max(abs(sample["carrier_rotation"][0]) for sample in samples)
        max_roll = max(abs(sample["carrier_rotation"][2]) for sample in samples)
        distance = vector_norm_xy(final_location, start_location)
        video_path = encode_video()

        summary = {
            "run_dir": str(run_dir),
            "map": world.get_map().name,
            "mode": "axis_safe_visual_shell_overlay_no_collision",
            "carrier_id": args.carrier_id,
            "visual_id": args.visual_id,
            "spawn_index": spawn_index,
            "seed_spawn_index": seed_index,
            "passed": bool(distance > 1.0 and max_speed > 0.5 and max_pitch < 15.0 and max_roll < 15.0),
            "distance_m": round(distance, 6),
            "max_speed_mps": max_speed,
            "max_abs_pitch_deg": max_pitch,
            "max_abs_roll_deg": max_roll,
            "visual_physics_disabled": True,
            "visual_collisions_disabled": True,
            "visual_yaw_offset_deg": args.yaw_offset_deg,
            "carrier_bbox_extent_m": round_vector3(carrier_box),
            "visual_bbox_extent_m": round_vector3(visual_box),
            "screenshot": screenshot,
            "video": video_path,
            "frame_count": frame_count,
            "samples": samples,
        }
        (run_dir / "axis_safe_overlay_summary.json").write_text(
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
    summary = run_validation(args)
    print(json.dumps({key: summary[key] for key in (
        "run_dir",
        "map",
        "carrier_id",
        "visual_id",
        "passed",
        "distance_m",
        "max_speed_mps",
        "visual_bbox_extent_m",
        "screenshot",
        "video",
    )}, indent=2, ensure_ascii=False))
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
