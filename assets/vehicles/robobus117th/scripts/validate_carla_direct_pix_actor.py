"""Validate ``vehicle.pixmoving.robobus`` as a real CARLA vehicle actor.

This check intentionally does not use an external carrier or visual overlay.
It connects to an already-running CARLA server, spawns the PIX Robobus actor
from CARLA's blueprint library, drives it with normal VehicleControl commands,
and writes visual/runtime evidence.
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
    parser.add_argument("--actor-id", default="vehicle.pixmoving.robobus", help="PIX vehicle blueprint id.")
    parser.add_argument("--role-name", default="hero", help="Role name assigned to the PIX actor.")
    parser.add_argument("--spawn-index", type=int, default=30, help="Preferred CARLA spawn point index.")
    parser.add_argument("--ticks", type=int, default=180, help="Validation drive duration in synchronous ticks.")
    parser.add_argument("--fixed-delta-sec", type=float, default=0.05, help="Synchronous mode fixed delta seconds.")
    parser.add_argument("--throttle", type=float, default=0.75, help="Vehicle throttle command.")
    parser.add_argument("--left-steer", type=float, default=0.16, help="First steering pulse.")
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


def speed_mps(actor: Any) -> float:
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)


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

    def attach_camera(actor: Any) -> tuple[Any, queue.Queue[Any]]:
        camera_bp = blueprint_library.find("sensor.camera.rgb")
        camera_bp.set_attribute("image_size_x", "1280")
        camera_bp.set_attribute("image_size_y", "720")
        camera_bp.set_attribute("fov", "70")
        camera = world.spawn_actor(
            camera_bp,
            carla.Transform(
                carla.Location(x=-7.8, y=3.4, z=3.4),
                carla.Rotation(pitch=-16.0, yaw=-20.0, roll=0.0),
            ),
            attach_to=actor,
        )
        spawned.append(camera)
        images: queue.Queue[Any] = queue.Queue()
        camera.listen(images.put)
        return camera, images

    def save_camera_frame(image_queue: queue.Queue[Any], name: str) -> str:
        for _ in range(3):
            world.tick()
        image = image_queue.get(timeout=5)
        path = run_dir / f"{name}.png"
        image.save_to_disk(str(path))
        return str(path)

    def encode_video() -> str | None:
        if not args.record_video:
            return None
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None
        video_path = run_dir / f"{args.actor_id.replace('.', '_')}_direct_drive.mp4"
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

    def spawn_pix_actor(bp: Any) -> tuple[Any, int, float]:
        preferred_indices = [args.spawn_index, 0, 5, 10, 20, 30, 40, 60, 80, 100, 120]
        seen: set[int] = set()
        z_offsets = [0.0, 0.05, 0.15, 0.30]
        for index in preferred_indices:
            if index in seen or index >= len(spawn_points):
                continue
            seen.add(index)
            base = spawn_points[index]
            for z_offset in z_offsets:
                transform = carla.Transform(
                    base.location + carla.Vector3D(0.0, 0.0, z_offset),
                    base.rotation,
                )
                actor = world.try_spawn_actor(bp, transform)
                if actor is not None:
                    return actor, index, z_offset
        raise RuntimeError(f"Failed to spawn {args.actor_id} at normal map spawn points")

    try:
        world.apply_settings(settings)
        if not args.no_cleanup_existing:
            cleanup_existing()

        actor_bp = blueprint_library.find(args.actor_id)
        if actor_bp.has_attribute("role_name"):
            actor_bp.set_attribute("role_name", args.role_name)
        actor, spawn_index, spawn_z_offset = spawn_pix_actor(actor_bp)
        spawned.append(actor)

        camera, image_queue = attach_camera(actor)
        for _ in range(8):
            world.tick()
        start_screenshot = save_camera_frame(image_queue, "pix_robobus_direct_start")

        start_location = actor.get_transform().location
        samples: list[dict[str, Any]] = []
        frame_count = 0
        for tick in range(args.ticks):
            if args.ticks * 0.15 <= tick < args.ticks * 0.45:
                steer = args.left_steer
            elif args.ticks * 0.45 <= tick < args.ticks * 0.70:
                steer = args.right_steer
            else:
                steer = 0.0
            actor.apply_control(carla.VehicleControl(throttle=args.throttle, steer=steer, brake=0.0))
            world.tick()
            if args.record_video:
                image = image_queue.get(timeout=5)
                if tick % max(args.frame_stride, 1) == 0:
                    image.save_to_disk(str(frames_dir / f"frame_{frame_count:05d}.png"))
                    frame_count += 1
            if tick % 20 == 0 or tick == args.ticks - 1:
                transform = actor.get_transform()
                control = actor.get_control()
                samples.append(
                    {
                        "tick": tick,
                        "location": round_vector3(transform.location),
                        "rotation": round_rotation(transform.rotation),
                        "speed_mps": round(speed_mps(actor), 6),
                        "control": {
                            "throttle": round(float(control.throttle), 6),
                            "steer": round(float(control.steer), 6),
                            "brake": round(float(control.brake), 6),
                        },
                    }
                )

        final_screenshot = save_camera_frame(image_queue, "pix_robobus_direct_after_drive")
        camera.stop()
        final_location = actor.get_transform().location
        bbox = actor.bounding_box.extent
        max_speed = max(sample["speed_mps"] for sample in samples)
        max_pitch = max(abs(sample["rotation"][0]) for sample in samples)
        max_roll = max(abs(sample["rotation"][2]) for sample in samples)
        distance = vector_norm_xy(final_location, start_location)
        video_path = encode_video()

        summary = {
            "run_dir": str(run_dir),
            "map": world.get_map().name,
            "mode": "direct_pix_vehicle_actor",
            "actor_id": args.actor_id,
            "spawn_index": spawn_index,
            "spawn_z_offset_m": spawn_z_offset,
            "passed": bool(distance > 5.0 and max_speed > 1.5 and max_pitch < 12.0 and max_roll < 12.0),
            "distance_m": round(distance, 6),
            "max_speed_mps": round(max_speed, 6),
            "max_abs_pitch_deg": round(max_pitch, 6),
            "max_abs_roll_deg": round(max_roll, 6),
            "bbox_extent_m": round_vector3(bbox),
            "start_screenshot": start_screenshot,
            "final_screenshot": final_screenshot,
            "video": video_path,
            "frame_count": frame_count,
            "samples": samples,
        }
        (run_dir / "direct_pix_actor_summary.json").write_text(
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
        "actor_id",
        "passed",
        "distance_m",
        "max_speed_mps",
        "max_abs_pitch_deg",
        "max_abs_roll_deg",
        "bbox_extent_m",
        "start_screenshot",
        "final_screenshot",
        "video",
    )}, indent=2, ensure_ascii=False))
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
