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
import subprocess
import sys
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
    return all(call.get("returncode") in (None, 0) for call in service_calls)


def setup_route(env: dict[str, str], start_map: dict[str, float], goal_map: dict[str, float], calls: list[dict[str, Any]]) -> None:
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
        ["timeout", "25", "ros2", "service", "call", "/api/routing/set_route_points", "autoware_adapi_v1_msgs/srv/SetRoutePoints", route_yaml(goal_map)],
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

    service_calls: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    topic_samples: list[dict[str, Any]] = []
    video_recorder: CameraVideoRecorder | None = None
    last_spectator_view: dict[str, float] | None = None
    last_camera_view: dict[str, float] | None = None

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
        setup_route(env, start_map, goal_map, service_calls)
        start_t = time.time()
        reached_near_goal = False
        min_goal_distance_m = math.inf
        max_speed_mps = 0.0
        sample_period = args.sample_period
        max_samples = max(1, int(args.max_duration_sec / sample_period))
        for index in range(max_samples):
            elapsed = time.time() - start_t
            ego_sample = sample_actor(ego)
            goal_distance = distance_to_goal_m(ego_sample, goal_map)
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
            samples.append(
                {
                    "i": index,
                    "t": elapsed,
                    "frame": world.get_snapshot().frame,
                    "ego": ego_sample,
                    "goal_distance_m": goal_distance,
                }
            )
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
        route_valid = service_call_successful(service_calls)
        summary = {
            "sample_count": len(samples),
            "moved": moved,
            "total_delta_m": total_delta_m,
            "max_speed_mps": max_speed_mps,
            "last_location": last_location,
            "min_goal_distance_m": min_goal_distance_m if math.isfinite(min_goal_distance_m) else None,
            "reached_near_goal": reached_near_goal,
            "route_service_calls_successful": route_valid,
            "topic_sample_count": len(topic_samples),
            "topic_samples_received": sum(1 for item in topic_samples if item.get("sample_received")),
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_probe(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
