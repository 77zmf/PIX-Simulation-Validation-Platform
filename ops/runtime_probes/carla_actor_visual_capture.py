#!/usr/bin/env python3
"""Capture CARLA actor visual evidence for SUMO/CARLA validation runs.

Run this on the company Ubuntu runtime host after `simctl run --execute` has
started CARLA. The probe finds the ego vehicle and background actors, captures
close-up RGB camera frames for the selected NPC actors, and writes metric-probe
artifacts that `simctl finalize` can fold into `run_result.json`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import queue
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "actor"


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


def _actor_role(actor: Any) -> str:
    return str(getattr(actor, "attributes", {}).get("role_name", ""))


def select_npc_actors(
    actors: list[Any],
    *,
    ego_role_name: str,
    npc_role_name: str,
    npc_role_prefix: str,
    include_non_ego_fallback: bool,
) -> list[Any]:
    """Select background traffic actors, preferring explicit SUMO role names."""

    ego_ids = {int(actor.id) for actor in actors if _actor_role(actor) == ego_role_name}
    selected: list[Any] = []
    for actor in actors:
        role_name = _actor_role(actor)
        if npc_role_name and role_name == npc_role_name:
            selected.append(actor)
        elif npc_role_prefix and role_name.lower().startswith(npc_role_prefix.lower()):
            selected.append(actor)
    if selected or not include_non_ego_fallback:
        return selected
    return [actor for actor in actors if int(actor.id) not in ego_ids]


def poll_vehicle_actors(
    actor_fetcher: Any,
    *,
    ego_role_name: str,
    npc_role_name: str,
    npc_role_prefix: str,
    include_non_ego_fallback: bool,
    max_npcs: int,
    min_npcs: int,
    timeout_sec: float,
    poll_interval_sec: float,
) -> tuple[list[Any], Any | None, list[Any], list[dict[str, Any]]]:
    """Poll CARLA actor state until ego and the required NPC count are visible."""

    deadline = time.monotonic() + max(0.0, timeout_sec)
    attempts: list[dict[str, Any]] = []
    last_actors: list[Any] = []
    last_ego_actor: Any | None = None
    last_npc_actors: list[Any] = []
    required_npcs = max(0, min_npcs)

    while True:
        actors = list(actor_fetcher())
        ego_actor = next((actor for actor in actors if _actor_role(actor) == ego_role_name), None)
        npc_actors = select_npc_actors(
            actors,
            ego_role_name=ego_role_name,
            npc_role_name=npc_role_name,
            npc_role_prefix=npc_role_prefix,
            include_non_ego_fallback=include_non_ego_fallback,
        )[:max_npcs]
        attempts.append(
            {
                "vehicle_count": len(actors),
                "ego_seen": ego_actor is not None,
                "npc_count": len(npc_actors),
            }
        )
        last_actors = actors
        last_ego_actor = ego_actor
        last_npc_actors = npc_actors
        if ego_actor is not None and len(npc_actors) >= required_npcs:
            return actors, ego_actor, npc_actors, attempts
        if time.monotonic() >= deadline:
            return last_actors, last_ego_actor, last_npc_actors, attempts
        time.sleep(max(0.05, poll_interval_sec))


def _location_dict(location: Any) -> dict[str, float]:
    return {"x": float(location.x), "y": float(location.y), "z": float(location.z)}


def _rotation_dict(rotation: Any) -> dict[str, float]:
    return {"pitch": float(rotation.pitch), "yaw": float(rotation.yaw), "roll": float(rotation.roll)}


def _look_at(carla: Any, source: Any, target: Any) -> Any:
    dx = target.x - source.x
    dy = target.y - source.y
    dz = target.z - source.z
    yaw = math.degrees(math.atan2(dy, dx))
    horizontal_distance = max(0.001, math.sqrt(dx * dx + dy * dy))
    pitch = math.degrees(math.atan2(dz, horizontal_distance))
    return carla.Rotation(pitch=pitch, yaw=yaw, roll=0.0)


def _actor_summary(actor: Any) -> dict[str, Any]:
    location = actor.get_location()
    return {
        "id": int(actor.id),
        "type_id": str(actor.type_id),
        "role_name": _actor_role(actor),
        "location": _location_dict(location),
    }


def _draw_actor_label(carla: Any, world: Any, actor: Any, label: str, ego: bool) -> None:
    try:
        location = actor.get_location()
        color = carla.Color(0, 255, 0) if ego else carla.Color(255, 220, 0)
        world.debug.draw_string(
            location + carla.Location(z=3.2),
            label,
            draw_shadow=True,
            color=color,
            life_time=25.0,
            persistent_lines=True,
        )
        world.debug.draw_box(
            actor.bounding_box,
            actor.get_transform().rotation,
            thickness=0.18,
            color=color,
            life_time=25.0,
            persistent_lines=True,
        )
    except Exception:
        return


def _capture_rgb(world: Any, camera_blueprint: Any, transform: Any, output_path: Path, timeout_sec: float) -> None:
    world.get_spectator().set_transform(transform)
    time.sleep(0.35)
    sensor = world.spawn_actor(camera_blueprint, transform)
    image_queue: queue.Queue[Any] = queue.Queue()
    sensor.listen(image_queue.put)
    try:
        image = image_queue.get(timeout=timeout_sec)
        image.save_to_disk(str(output_path))
    finally:
        sensor.stop()
        sensor.destroy()


def _npc_camera_transforms(carla: Any, actor: Any) -> tuple[Any, Any]:
    transform = actor.get_transform()
    location = transform.location
    forward = transform.get_forward_vector()
    right = transform.get_right_vector()
    target = location + carla.Location(z=1.25)
    close_location = carla.Location(
        x=location.x - 8.0 * forward.x + 2.0 * right.x,
        y=location.y - 8.0 * forward.y + 2.0 * right.y,
        z=location.z + 3.3,
    )
    side_location = carla.Location(
        x=location.x - 7.0 * right.x - 2.5 * forward.x,
        y=location.y - 7.0 * right.y - 2.5 * forward.y,
        z=location.z + 3.0,
    )
    return (
        carla.Transform(close_location, _look_at(carla, close_location, target)),
        carla.Transform(side_location, _look_at(carla, side_location, target)),
    )


def _group_topdown_transform(carla: Any, actors: list[Any]) -> Any | None:
    if not actors:
        return None
    locations = [actor.get_location() for actor in actors]
    center_x = sum(location.x for location in locations) / len(locations)
    center_y = sum(location.y for location in locations) / len(locations)
    z = max(location.z for location in locations) + 150.0
    return carla.Transform(
        carla.Location(center_x, center_y, z),
        carla.Rotation(pitch=-90.0, yaw=0.0, roll=0.0),
    )


def _build_metrics(vehicle_count: int, ego_seen: bool, npc_count: int, capture_count: int) -> dict[str, float]:
    return {
        "carla_actor_visual_vehicle_count": float(vehicle_count),
        "carla_actor_visual_ego_seen": 1.0 if ego_seen else 0.0,
        "carla_actor_visual_npc_count": float(npc_count),
        "carla_actor_visual_capture_count": float(capture_count),
    }


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    if args.wait_sec > 0:
        time.sleep(args.wait_sec)

    print("[carla_actor_visual_capture] stage=import_carla", file=sys.stderr, flush=True)
    _add_carla_python_paths(args.carla_root)
    try:
        import carla  # type: ignore
    except Exception as exc:
        metrics = _build_metrics(0, False, 0, 0)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kind": "carla_actor_visual_capture",
            "profile": args.profile,
            "overall_passed": False,
            "blocked_reason": f"carla_import_failed:{exc}",
            "missing_metrics": [],
            "missing_topics": [],
            "sample_missing_topics": [],
            "metrics": metrics,
            "summary": {
                "vehicle_count": 0,
                "ego_seen": False,
                "npc_count": 0,
                "capture_count": 0,
                "image_dir": "",
            },
            "actors": [],
            "captures": [],
        }

    print("[carla_actor_visual_capture] stage=prepare_output", file=sys.stderr, flush=True)
    run_dir = Path(args.run_dir).resolve()
    stamp = _utc_stamp()
    image_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else run_dir / "screenshots" / f"carla_actor_visual_{stamp}"
    )
    image_dir.mkdir(parents=True, exist_ok=True)

    print("[carla_actor_visual_capture] stage=connect_carla", file=sys.stderr, flush=True)
    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(args.carla_timeout_sec)
    world = client.get_world()
    if args.set_weather_clear_noon:
        try:
            world.set_weather(carla.WeatherParameters.ClearNoon)
        except Exception:
            pass

    print("[carla_actor_visual_capture] stage=query_actors", file=sys.stderr, flush=True)
    actors, ego_actor, npc_actors, actor_poll_attempts = poll_vehicle_actors(
        lambda: world.get_actors().filter("vehicle.*"),
        ego_role_name=args.ego_role_name,
        npc_role_name=args.npc_role_name,
        npc_role_prefix=args.npc_role_prefix,
        include_non_ego_fallback=args.include_non_ego_fallback,
        max_npcs=args.max_npcs,
        min_npcs=args.min_npcs,
        timeout_sec=args.actor_poll_timeout_sec,
        poll_interval_sec=args.actor_poll_interval_sec,
    )

    for actor in actors:
        is_ego = ego_actor is not None and int(actor.id) == int(ego_actor.id)
        label = "PIX_EGO" if is_ego else f"SUMO_NPC_{int(actor.id)}"
        _draw_actor_label(carla, world, actor, label, is_ego)

    camera_blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
    camera_blueprint.set_attribute("image_size_x", str(args.image_width))
    camera_blueprint.set_attribute("image_size_y", str(args.image_height))
    camera_blueprint.set_attribute("fov", str(args.fov))

    print(
        f"[carla_actor_visual_capture] stage=capture_npcs npc_count={len(npc_actors)}",
        file=sys.stderr,
        flush=True,
    )
    captures: list[dict[str, Any]] = []
    for index, actor in enumerate(npc_actors, start=1):
        close_transform, side_transform = _npc_camera_transforms(carla, actor)
        base_name = f"npc_{index:02d}_id_{int(actor.id)}_{_safe_name(str(actor.type_id))}"
        close_path = image_dir / f"{base_name}_close.png"
        side_path = image_dir / f"{base_name}_side.png"
        _capture_rgb(world, camera_blueprint, close_transform, close_path, args.image_timeout_sec)
        _capture_rgb(world, camera_blueprint, side_transform, side_path, args.image_timeout_sec)
        captures.append(
            {
                "index": index,
                "actor_id": int(actor.id),
                "type_id": str(actor.type_id),
                "role_name": _actor_role(actor),
                "location": _location_dict(actor.get_location()),
                "close_path": str(close_path),
                "side_path": str(side_path),
                "close_camera": {
                    "location": _location_dict(close_transform.location),
                    "rotation": _rotation_dict(close_transform.rotation),
                },
                "side_camera": {
                    "location": _location_dict(side_transform.location),
                    "rotation": _rotation_dict(side_transform.rotation),
                },
            }
        )

    group_capture: dict[str, Any] | None = None
    if args.capture_group_topdown and npc_actors:
        group_transform = _group_topdown_transform(carla, npc_actors)
        if group_transform is not None:
            group_path = image_dir / "npc_group_topdown_all_sumo_driver.png"
            _capture_rgb(world, camera_blueprint, group_transform, group_path, args.image_timeout_sec)
            group_capture = {
                "path": str(group_path),
                "camera": {
                    "location": _location_dict(group_transform.location),
                    "rotation": _rotation_dict(group_transform.rotation),
                },
            }

    capture_count = (len(captures) * 2) + (1 if group_capture else 0)
    metrics = _build_metrics(len(actors), ego_actor is not None, len(npc_actors), capture_count)
    overall_passed = (
        len(npc_actors) >= args.min_npcs
        and capture_count >= max(args.min_captures, len(npc_actors))
        and all(Path(capture["close_path"]).exists() and Path(capture["side_path"]).exists() for capture in captures)
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "carla_actor_visual_capture",
        "profile": args.profile,
        "overall_passed": overall_passed,
        "blocked_reason": None if overall_passed else "insufficient_actor_visual_evidence",
        "missing_metrics": [],
        "missing_topics": [],
        "sample_missing_topics": [],
        "metrics": metrics,
        "summary": {
            "vehicle_count": len(actors),
            "ego_seen": ego_actor is not None,
            "ego_id": int(ego_actor.id) if ego_actor else None,
            "npc_count": len(npc_actors),
            "capture_count": capture_count,
            "image_dir": str(image_dir),
            "actor_poll_attempt_count": len(actor_poll_attempts),
            "actor_poll_attempts": actor_poll_attempts,
        },
        "actors": [_actor_summary(actor) for actor in actors],
        "captures": captures,
        "group_capture": group_capture,
    }
    return payload


def _worker_failure_payload(args: argparse.Namespace, reason: str, details: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(args.run_dir).resolve()
    image_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else run_dir / "screenshots" / f"carla_actor_visual_failed_{_utc_stamp()}"
    )
    metrics = _build_metrics(0, False, 0, 0)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "carla_actor_visual_capture",
        "profile": args.profile,
        "overall_passed": False,
        "blocked_reason": reason,
        "missing_metrics": [],
        "missing_topics": [],
        "sample_missing_topics": [],
        "metrics": metrics,
        "summary": {
            "vehicle_count": 0,
            "ego_seen": False,
            "ego_id": None,
            "npc_count": 0,
            "capture_count": 0,
            "image_dir": str(image_dir),
        },
        "actors": [],
        "captures": [],
        "group_capture": None,
        "worker": details,
    }


def write_artifacts(run_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    stamp = _utc_stamp()
    output_dir = run_dir / "runtime_verification" / f"metric_probe_carla_actor_visual_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"metric_probe_carla_actor_visual_{stamp}.json"
    summary = output_dir / "metric_probe_carla_actor_visual_summary.json"
    artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary.write_text(
        json.dumps(
            {
                "overall_passed": payload["overall_passed"],
                "blocked_reason": payload["blocked_reason"],
                "metrics": payload["metrics"],
                "summary": payload["summary"],
                "captures": payload["captures"],
                "group_capture": payload["group_capture"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"artifact": str(artifact), "summary_path": str(summary)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="simctl run directory")
    parser.add_argument("--profile", default="sumo_npc_closeups")
    parser.add_argument("--carla-host", default=os.environ.get("SIMCTL_CARLA_HOST", "127.0.0.1"))
    parser.add_argument("--carla-port", type=int, default=int(os.environ.get("SIMCTL_CARLA_RPC_PORT", "2000")))
    parser.add_argument(
        "--carla-root",
        default=os.environ.get("CARLA_ROOT", os.environ.get("CARLA_0915_ROOT", str(Path.home() / "CARLA_0.9.15"))),
    )
    parser.add_argument("--carla-timeout-sec", type=float, default=10.0)
    parser.add_argument("--ego-role-name", default="ego_vehicle")
    parser.add_argument("--npc-role-name", default="sumo_driver")
    parser.add_argument("--npc-role-prefix", default="sumo")
    parser.add_argument("--include-non-ego-fallback", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-npcs", type=int, default=8)
    parser.add_argument("--min-npcs", type=int, default=1)
    parser.add_argument("--min-captures", type=int, default=1)
    parser.add_argument("--image-width", "--camera-width", dest="image_width", type=int, default=1920)
    parser.add_argument("--image-height", "--camera-height", dest="image_height", type=int, default=1080)
    parser.add_argument("--fov", type=float, default=55.0)
    parser.add_argument("--image-timeout-sec", type=float, default=10.0)
    parser.add_argument("--wait-sec", type=float, default=0.0)
    parser.add_argument("--actor-poll-timeout-sec", type=float, default=8.0)
    parser.add_argument("--actor-poll-interval-sec", type=float, default=0.5)
    parser.add_argument("--output-dir", help="Screenshot output dir; default: <run-dir>/screenshots/carla_actor_visual_<stamp>")
    parser.add_argument("--capture-group-topdown", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--set-weather-clear-noon", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--worker-timeout-sec", type=float, default=240.0)
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
            )
        except subprocess.TimeoutExpired as exc:
            payload = _worker_failure_payload(
                args,
                "carla_actor_visual_worker_timeout",
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
                "carla_actor_visual_worker_crashed",
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
