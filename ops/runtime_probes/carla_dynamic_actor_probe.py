#!/usr/bin/env python3
"""Run CARLA dynamic-actor probes against a live Autoware stack.

This runner is intentionally host-side: execute it on the company Ubuntu
runtime host after `simctl run --execute` has brought up CARLA + Autoware.
It records a JSON artifact, a concise summary, an optional rosbag, and a
CARLA recorder log under `<run-dir>/runtime_verification/`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOPICS = [
    "/clock",
    "/tf",
    "/localization/kinematic_state",
    "/perception/object_recognition/detection/objects",
    "/perception/object_recognition/tracking/objects",
    "/perception/object_recognition/objects",
    "/simulation/dummy_perception_publisher/output/debug/ground_truth_objects",
    "/planning/scenario_planning/trajectory",
    "/control/command/control_cmd",
    "/control/command/actuation_cmd",
    "/vehicle/status/velocity_status",
    "/api/operation_mode/state",
    "/autoware/state",
]

START_CARLA = {"x": 229.78167724609375, "y": 2.0201120376586914, "z": 0.08, "yaw": 0.0}
START_MAP = {"x": 229.78167724609375, "y": -2.0201120376586914, "z": 0.0, "yaw": 0.0}
GOAL_MAP = {"x": 314.2434997558594, "y": -1.982629656791687, "z": 0.0, "yaw_deg": -0.03045654296875}


@dataclass(frozen=True)
class ActorSpec:
    name: str
    target_type: str
    start: dict[str, float]
    final_y: float
    speed_x: float
    cut_in_duration: float
    static_target: bool = False
    activation_sec: float = 0.0


@dataclass(frozen=True)
class ProbeConfig:
    kind: str
    classification: str
    target_type: str
    target_start: dict[str, float]
    target_final_y: float
    target_speed_x: float
    cut_in_duration: float
    max_duration: float
    static_target: bool = False
    safe_distance_m: float = 5.0
    safe_ttc_sec: float = 2.0
    actors: tuple[ActorSpec, ...] = ()


PROBES: dict[str, ProbeConfig] = {
    "l1_static": ProbeConfig(
        kind="l1_static",
        classification="l1_static_obstacle_with_dummy_perception_injection",
        target_type="vehicle.audi.tt",
        target_start={"x": 275.0, "y": 2.0, "z": 0.08, "yaw": 0.0},
        target_final_y=2.0,
        target_speed_x=0.0,
        cut_in_duration=0.0,
        max_duration=34.0,
        static_target=True,
    ),
    "l2_cut_in": ProbeConfig(
        kind="l2_cut_in",
        classification="l2_cut_in_with_dummy_perception_injection",
        target_type="vehicle.audi.tt",
        target_start={"x": 255.0, "y": 6.0, "z": 0.15, "yaw": 0.0},
        target_final_y=2.0,
        target_speed_x=2.8,
        cut_in_duration=8.0,
        max_duration=42.0,
    ),
    "l2_merge": ProbeConfig(
        kind="l2_merge",
        classification="l2_merge_actor_with_perception_pipeline",
        target_type="vehicle.audi.tt",
        target_start={"x": 252.0, "y": 5.5, "z": 0.15, "yaw": 0.0},
        target_final_y=2.0,
        target_speed_x=2.4,
        cut_in_duration=9.0,
        max_duration=48.0,
        safe_ttc_sec=1.8,
    ),
    "l2_close_cut_in": ProbeConfig(
        kind="l2_close_cut_in",
        classification="l2_close_cut_in_with_dummy_perception_injection",
        target_type="vehicle.audi.tt",
        target_start={"x": 260.0, "y": 6.0, "z": 0.15, "yaw": 0.0},
        target_final_y=2.0,
        target_speed_x=0.5,
        cut_in_duration=5.0,
        max_duration=45.0,
    ),
    "l2_multi_actor_cut_in_lead_brake": ProbeConfig(
        kind="l2_multi_actor_cut_in_lead_brake",
        classification="l2_multi_actor_cut_in_lead_brake_with_perception_pipeline",
        target_type="vehicle.audi.tt",
        target_start={"x": 286.0, "y": 2.0, "z": 0.15, "yaw": 0.0},
        target_final_y=2.0,
        target_speed_x=0.0,
        cut_in_duration=0.0,
        max_duration=50.0,
        static_target=True,
        safe_ttc_sec=1.8,
        actors=(
            ActorSpec(
                name="lead_brake",
                target_type="vehicle.audi.tt",
                start={"x": 286.0, "y": 2.0, "z": 0.15, "yaw": 0.0},
                final_y=2.0,
                speed_x=0.0,
                cut_in_duration=0.0,
                static_target=True,
            ),
            ActorSpec(
                name="side_cut_in",
                target_type="vehicle.audi.tt",
                start={"x": 260.0, "y": 6.0, "z": 0.15, "yaw": 0.0},
                final_y=2.0,
                speed_x=0.6,
                cut_in_duration=6.5,
                activation_sec=1.0,
            ),
            ActorSpec(
                name="adjacent_background",
                target_type="vehicle.audi.tt",
                start={"x": 250.0, "y": -5.8, "z": 0.15, "yaw": 0.0},
                final_y=-5.8,
                speed_x=1.8,
                cut_in_duration=0.0,
            ),
        ),
    ),
}


def q_from_yaw(deg: float) -> dict[str, float]:
    rad = math.radians(deg)
    return {"x": 0.0, "y": 0.0, "z": math.sin(rad / 2.0), "w": math.cos(rad / 2.0)}


def pose_yaml(pose: dict[str, float]) -> str:
    q = q_from_yaw(pose.get("yaw_deg", pose.get("yaw", 0.0)))
    covariance = [0.0] * 36
    covariance[0] = 0.25
    covariance[7] = 0.25
    covariance[35] = 0.01
    return (
        "{pose: [{header: {frame_id: map}, pose: {pose: {position: "
        "{x: %.9f, y: %.9f, z: %.3f}, orientation: {x: %.9f, y: %.9f, z: %.12f, w: %.12f}}, "
        "covariance: [%s]}}]}"
        % (
            pose["x"],
            pose["y"],
            pose.get("z", 0.0),
            q["x"],
            q["y"],
            q["z"],
            q["w"],
            ", ".join(str(value) for value in covariance),
        )
    )


def route_yaml(goal: dict[str, float]) -> str:
    q = q_from_yaw(goal.get("yaw_deg", 0.0))
    return (
        "{header: {frame_id: map}, option: {allow_goal_modification: true}, "
        "goal: {position: {x: %.9f, y: %.9f, z: %.3f}, orientation: {x: 0.0, y: 0.0, z: %.12f, w: %.12f}}, "
        "waypoints: []}"
        % (goal["x"], goal["y"], goal.get("z", 0.0), q["z"], q["w"])
    )


def run_cmd(step: str, args: list[str], env: dict[str, str], calls: list[dict[str, Any]], timeout_sec: int = 20) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    try:
        completed = subprocess.run(
            args,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_sec,
        )
        item = {
            "step": step,
            "returncode": completed.returncode,
            "output": completed.stdout,
            "args": args,
            "started_at": started,
        }
    except subprocess.TimeoutExpired as exc:
        item = {
            "step": step,
            "returncode": 124,
            "output": (exc.stdout or "") + (exc.stderr or ""),
            "args": args,
            "started_at": started,
        }
    calls.append(item)
    return item


def load_runtime_modules() -> dict[str, Any]:
    try:
        import carla  # type: ignore[import-not-found]
        import rclpy  # type: ignore[import-not-found]
        from autoware_perception_msgs.msg import ObjectClassification, Shape  # type: ignore[import-not-found]
        from geometry_msgs.msg import Vector3  # type: ignore[import-not-found]
        from tier4_simulation_msgs.msg import DummyObject  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Missing CARLA/ROS Python modules. Run this on the Ubuntu runtime host after sourcing "
            "ROS 2 and the Autoware install setup.bash."
        ) from exc
    return {
        "carla": carla,
        "rclpy": rclpy,
        "ObjectClassification": ObjectClassification,
        "Shape": Shape,
        "Vector3": Vector3,
        "DummyObject": DummyObject,
    }


def sample_actor(actor: Any) -> dict[str, Any]:
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    control = actor.get_control()
    speed = math.sqrt(velocity.x * velocity.x + velocity.y * velocity.y + velocity.z * velocity.z)
    return {
        "x": transform.location.x,
        "y": transform.location.y,
        "z": transform.location.z,
        "yaw": transform.rotation.yaw,
        "speed_mps": speed,
        "throttle": getattr(control, "throttle", None),
        "brake": getattr(control, "brake", None),
        "steer": getattr(control, "steer", None),
    }


def wait_for_ego(client: Any, timeout_sec: int = 20) -> tuple[Any, Any]:
    deadline = time.time() + timeout_sec
    last_seen: list[tuple[int, str, str]] = []
    while time.time() < deadline:
        world = client.get_world()
        _ = world.get_snapshot()
        vehicles = list(world.get_actors().filter("vehicle.*"))
        last_seen = [(vehicle.id, vehicle.type_id, vehicle.attributes.get("role_name", "")) for vehicle in vehicles]
        for vehicle in vehicles:
            if vehicle.attributes.get("role_name", "") in {"ego_vehicle", "hero", "autoware_v1"}:
                return world, vehicle
        if len(vehicles) == 1:
            return world, vehicles[0]
        time.sleep(1.0)
    raise RuntimeError(f"Cannot identify ego vehicle after retry from {last_seen}")


def make_dummy_msg(modules: dict[str, Any], node: Any, action: int, x: float, map_y: float, yaw_deg: float, vx: float, vy: float) -> Any:
    DummyObject = modules["DummyObject"]
    ObjectClassification = modules["ObjectClassification"]
    Shape = modules["Shape"]
    Vector3 = modules["Vector3"]
    msg = DummyObject()
    msg.header.frame_id = "map"
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.id.uuid = [0x43, 0x43, 0x43, 0x43, 0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80, 0x90, 0xA0, 0xB0, 0xC0]
    msg.action = action
    if action == DummyObject.DELETEALL:
        return msg
    q = q_from_yaw(yaw_deg)
    pose = msg.initial_state.pose_covariance.pose
    pose.position.x = float(x)
    pose.position.y = float(map_y)
    pose.position.z = 0.0
    pose.orientation.x = q["x"]
    pose.orientation.y = q["y"]
    pose.orientation.z = q["z"]
    pose.orientation.w = q["w"]
    msg.initial_state.pose_covariance.covariance[0] = 0.2
    msg.initial_state.pose_covariance.covariance[7] = 0.2
    msg.initial_state.pose_covariance.covariance[35] = 0.05
    msg.initial_state.twist_covariance.twist.linear.x = float(vx)
    msg.initial_state.twist_covariance.twist.linear.y = float(vy)
    msg.classification.label = ObjectClassification.CAR
    msg.classification.probability = 1.0
    msg.shape.type = Shape.BOUNDING_BOX
    msg.shape.dimensions = Vector3(x=4.5, y=2.0, z=1.7)
    msg.max_velocity = max(0.1, float(abs(vx) + abs(vy)))
    msg.min_velocity = 0.0
    return msg


def probe_actor_specs(config: ProbeConfig) -> tuple[ActorSpec, ...]:
    if config.actors:
        return config.actors
    return (
        ActorSpec(
            name="target",
            target_type=config.target_type,
            start=config.target_start,
            final_y=config.target_final_y,
            speed_x=config.target_speed_x,
            cut_in_duration=config.cut_in_duration,
            static_target=config.static_target,
        ),
    )


def actor_motion(spec: ActorSpec, elapsed: float) -> dict[str, float]:
    active_elapsed = max(0.0, elapsed - spec.activation_sec)
    if spec.static_target:
        return {"x": spec.start["x"], "y": spec.start["y"], "z": spec.start["z"], "vx": 0.0, "vy": 0.0}
    x = spec.start["x"] + spec.speed_x * active_elapsed
    if spec.cut_in_duration > 0.0:
        ratio = min(1.0, active_elapsed / spec.cut_in_duration)
        ratio = 3 * ratio * ratio - 2 * ratio * ratio * ratio
        y = spec.start["y"] + (spec.final_y - spec.start["y"]) * ratio
        vy = (spec.final_y - spec.start["y"]) / spec.cut_in_duration if active_elapsed < spec.cut_in_duration else 0.0
    else:
        y = spec.final_y
        vy = 0.0
    return {"x": x, "y": y, "z": spec.start["z"], "vx": spec.speed_x, "vy": vy}


def spectator_transform_params(
    mode: str,
    ego_sample: dict[str, Any],
    target_samples: list[dict[str, Any]],
) -> dict[str, float] | None:
    """Return a CARLA spectator transform that makes visual evidence readable."""
    normalized = mode.lower()
    if normalized == "none":
        return None
    ego_x = float(ego_sample["x"])
    ego_y = float(ego_sample["y"])
    ego_yaw = float(ego_sample.get("yaw") or 0.0)
    if normalized == "ego_chase":
        yaw_rad = math.radians(ego_yaw)
        return {
            "x": ego_x - math.cos(yaw_rad) * 14.0,
            "y": ego_y - math.sin(yaw_rad) * 14.0,
            "z": float(ego_sample.get("z") or 0.0) + 7.0,
            "pitch": -22.0,
            "yaw": ego_yaw,
            "roll": 0.0,
        }
    if normalized == "overview":
        points = [(ego_x, ego_y)] + [
            (float(item["x"]), float(item["y"]))
            for item in target_samples
            if item.get("x") is not None and item.get("y") is not None
        ]
        center_x = sum(item[0] for item in points) / len(points)
        center_y = sum(item[1] for item in points) / len(points)
        span = max(math.hypot(x - center_x, y - center_y) for x, y in points) if points else 0.0
        return {
            "x": center_x,
            "y": center_y,
            "z": max(38.0, min(85.0, span * 2.4 + 24.0)),
            "pitch": -90.0,
            "yaw": 0.0,
            "roll": 0.0,
        }
    raise ValueError(f"Unsupported spectator mode: {mode}")


def apply_spectator_view(
    *,
    world: Any,
    carla: Any,
    mode: str,
    ego_sample: dict[str, Any],
    target_samples: list[dict[str, Any]],
) -> dict[str, float] | None:
    params = spectator_transform_params(mode, ego_sample, target_samples)
    if params is None:
        return None
    world.get_spectator().set_transform(
        carla.Transform(
            carla.Location(x=params["x"], y=params["y"], z=params["z"]),
            carla.Rotation(pitch=params["pitch"], yaw=params["yaw"], roll=params["roll"]),
        )
    )
    return params


def carla_transform_from_params(carla: Any, params: dict[str, float]) -> Any:
    return carla.Transform(
        carla.Location(x=params["x"], y=params["y"], z=params["z"]),
        carla.Rotation(pitch=params["pitch"], yaw=params["yaw"], roll=params["roll"]),
    )


class CameraVideoRecorder:
    """Record CARLA RGB camera frames to an mp4 without relying on desktop capture."""

    def __init__(
        self,
        *,
        output_path: Path,
        width: int,
        height: int,
        fps: int,
    ) -> None:
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.frames_written = 0
        self.frames_dropped = 0
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=max(4, fps * 3))
        self._proc: subprocess.Popen[bytes] | None = None
        self._camera: Any | None = None

    def start(self, *, world: Any, carla: Any, blueprint_library: Any, transform_params: dict[str, float]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgra",
            "-s",
            f"{self.width}x{self.height}",
            "-r",
            str(self.fps),
            "-i",
            "-",
            "-an",
            "-vcodec",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(self.output_path),
        ]
        self._proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        camera_bp = blueprint_library.find("sensor.camera.rgb")
        camera_bp.set_attribute("image_size_x", str(self.width))
        camera_bp.set_attribute("image_size_y", str(self.height))
        camera_bp.set_attribute("fov", "90")
        camera_bp.set_attribute("sensor_tick", str(1.0 / self.fps))
        self._camera = world.spawn_actor(camera_bp, carla_transform_from_params(carla, transform_params))
        self._camera.listen(self._enqueue_frame)

    def _enqueue_frame(self, image: Any) -> None:
        try:
            self._queue.put_nowait(bytes(image.raw_data))
        except queue.Full:
            self.frames_dropped += 1

    def set_transform(self, *, carla: Any, transform_params: dict[str, float]) -> None:
        if self._camera is not None:
            self._camera.set_transform(carla_transform_from_params(carla, transform_params))

    def drain(self) -> None:
        if self._proc is None or self._proc.stdin is None:
            return
        while True:
            try:
                frame = self._queue.get_nowait()
            except queue.Empty:
                return
            try:
                self._proc.stdin.write(frame)
                self.frames_written += 1
            except BrokenPipeError:
                return

    def close(self) -> None:
        if self._camera is not None:
            try:
                self._camera.stop()
                self._camera.destroy()
            except Exception:
                pass
        self.drain()
        if self._proc is not None:
            if self._proc.stdin is not None:
                try:
                    self._proc.stdin.close()
                except Exception:
                    pass
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.terminate()


def object_topic_sample(env: dict[str, str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["timeout", "6", "ros2", "topic", "echo", "--once", "/perception/object_recognition/objects"],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=8,
        )
    except Exception:
        return {"nonempty": False, "count": 0}
    nonempty = "objects:" in completed.stdout and "objects: []" not in completed.stdout
    count = max(
        completed.stdout.count("object_id:"),
        completed.stdout.count("existence_probability:"),
        completed.stdout.count("classification:"),
    )
    if nonempty and count == 0:
        count = 1
    return {"nonempty": nonempty, "count": count}


def object_topic_nonempty(env: dict[str, str]) -> bool:
    return bool(object_topic_sample(env)["nonempty"])


def setup_route(env: dict[str, str], calls: list[dict[str, Any]]) -> None:
    run_cmd("engage_false", ["timeout", "15", "ros2", "service", "call", "/api/autoware/set/engage", "tier4_external_api_msgs/srv/Engage", "{engage: false}"], env, calls, 18)
    run_cmd("clear_route", ["timeout", "15", "ros2", "service", "call", "/api/routing/clear_route", "autoware_adapi_v1_msgs/srv/ClearRoute", "{}"], env, calls, 18)
    run_cmd("change_to_stop", ["timeout", "15", "ros2", "service", "call", "/api/operation_mode/change_to_stop", "autoware_adapi_v1_msgs/srv/ChangeOperationMode", "{}"], env, calls, 18)
    run_cmd("initialize_localization", ["timeout", "25", "ros2", "service", "call", "/api/localization/initialize", "autoware_adapi_v1_msgs/srv/InitializeLocalization", pose_yaml(START_MAP)], env, calls, 28)
    time.sleep(4.0)
    run_cmd("set_route_points", ["timeout", "25", "ros2", "service", "call", "/api/routing/set_route_points", "autoware_adapi_v1_msgs/srv/SetRoutePoints", route_yaml(GOAL_MAP)], env, calls, 28)
    time.sleep(2.0)
    run_cmd("enable_autoware_control", ["timeout", "15", "ros2", "service", "call", "/api/operation_mode/enable_autoware_control", "autoware_adapi_v1_msgs/srv/ChangeOperationMode", "{}"], env, calls, 18)
    run_cmd("change_to_autonomous", ["timeout", "25", "ros2", "service", "call", "/api/operation_mode/change_to_autonomous", "autoware_adapi_v1_msgs/srv/ChangeOperationMode", "{}"], env, calls, 28)
    run_cmd("engage_true", ["timeout", "15", "ros2", "service", "call", "/api/autoware/set/engage", "tier4_external_api_msgs/srv/Engage", "{engage: true}"], env, calls, 18)


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    modules = load_runtime_modules()
    carla = modules["carla"]
    rclpy = modules["rclpy"]
    DummyObject = modules["DummyObject"]
    config = PROBES[args.kind]
    run_dir = Path(args.run_dir).resolve()
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    test_dir = run_dir / "runtime_verification" / f"{config.kind}_{args.perception_source}_{stamp}"
    test_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = test_dir / f"{config.kind}_{args.perception_source}_{stamp}.json"
    summary_path = test_dir / f"{config.kind}_{args.perception_source}_summary.json"
    bag_dir = test_dir / f"rosbag_{config.kind}_{stamp}"
    carla_recorder = str(test_dir / f"carla_{config.kind}_{stamp}.log")

    env = os.environ.copy()
    env["ROS_DOMAIN_ID"] = str(args.ros_domain_id)
    env["RMW_IMPLEMENTATION"] = args.rmw_implementation

    service_calls: list[dict[str, Any]] = []
    collision_events: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    actor_specs = probe_actor_specs(config)
    actor_handles: list[dict[str, Any]] = []
    bag_proc: subprocess.Popen[str] | None = None
    client = None
    collision_sensor = None
    node = None
    pub = None
    video_recorder: CameraVideoRecorder | None = None
    recording_started = False
    objects_nonempty = False
    max_object_count = 0
    object_check_count = 0
    object_nonempty_check_count = 0
    last_spectator_view: dict[str, float] | None = None
    last_camera_view: dict[str, float] | None = None
    use_dummy_injection = args.perception_source == "dummy_injection"
    if config.actors and use_dummy_injection:
        raise SystemExit("Multi-actor probes require --perception-source actor_bridge.")

    try:
        if args.record_rosbag:
            bag_log = open(test_dir / "rosbag_record.log", "w", encoding="utf-8")
            bag_proc = subprocess.Popen(
                ["ros2", "bag", "record", "-o", str(bag_dir), *TOPICS],
                env=env,
                stdout=bag_log,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                text=True,
            )
            time.sleep(1.5)

        client = carla.Client(args.carla_host, args.carla_port)
        client.set_timeout(args.carla_timeout)
        world, ego = wait_for_ego(client, timeout_sec=args.ego_timeout)
        ego.set_transform(
            carla.Transform(
                carla.Location(x=START_CARLA["x"], y=START_CARLA["y"], z=START_CARLA["z"]),
                carla.Rotation(yaw=START_CARLA["yaw"]),
            )
        )
        ego.set_target_velocity(carla.Vector3D(0, 0, 0))
        ego.set_target_angular_velocity(carla.Vector3D(0, 0, 0))
        ego.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))
        time.sleep(1.0)

        bp_lib = world.get_blueprint_library()
        for spec in actor_specs:
            target_bp = bp_lib.find(spec.target_type)
            target_bp.set_attribute("role_name", f"{config.kind}_{spec.name}")
            target = world.try_spawn_actor(
                target_bp,
                carla.Transform(
                    carla.Location(x=spec.start["x"], y=spec.start["y"], z=spec.start["z"]),
                    carla.Rotation(yaw=spec.start["yaw"]),
                ),
            )
            if target is None:
                raise RuntimeError(f"Failed to spawn target {spec.name} for {config.kind} at {spec.start}")
            target.set_simulate_physics(False)
            actor_handles.append({"spec": spec, "actor": target})

        collision_sensor = world.spawn_actor(bp_lib.find("sensor.other.collision"), carla.Transform(), attach_to=ego)
        collision_sensor.listen(
            lambda event: collision_events.append(
                {
                    "frame": event.frame,
                    "timestamp": time.time(),
                    "other_actor_id": event.other_actor.id,
                    "other_actor_type": event.other_actor.type_id,
                    "normal_impulse": {"x": event.normal_impulse.x, "y": event.normal_impulse.y, "z": event.normal_impulse.z},
                }
            )
        )
        client.start_recorder(carla_recorder)
        recording_started = True

        if use_dummy_injection:
            rclpy.init(args=None)
            node = rclpy.create_node(f"pix_{config.kind}_dummy_perception_probe")
            pub = node.create_publisher(DummyObject, "/simulation/dummy_perception_publisher/object_info", 10)
            time.sleep(0.5)
            pub.publish(
                make_dummy_msg(
                    modules,
                    node,
                    DummyObject.ADD,
                    actor_specs[0].start["x"],
                    -actor_specs[0].start["y"],
                    0.0,
                    actor_specs[0].speed_x,
                    0.0,
                )
            )
            rclpy.spin_once(node, timeout_sec=0.05)

        setup_route(env, service_calls)

        if args.camera_video_output:
            initial_ego_sample = sample_actor(ego)
            initial_target_samples = []
            for item in actor_handles:
                spec = item["spec"]
                target_sample = sample_actor(item["actor"])
                initial_target_samples.append({**target_sample, "name": spec.name})
            initial_camera_view = spectator_transform_params(args.camera_video_mode, initial_ego_sample, initial_target_samples)
            if initial_camera_view is not None:
                video_recorder = CameraVideoRecorder(
                    output_path=Path(args.camera_video_output).resolve(),
                    width=args.camera_video_width,
                    height=args.camera_video_height,
                    fps=args.camera_video_fps,
                )
                video_recorder.start(
                    world=world,
                    carla=carla,
                    blueprint_library=bp_lib,
                    transform_params=initial_camera_view,
                )
                last_camera_view = initial_camera_view

        start_t = time.time()
        min_distance = None
        min_ttc = None
        max_speed = 0.0
        min_speed_after_reaction = None
        reaction_seen = False
        reaction_reason = None
        target_in_lane = any(spec.static_target and abs(spec.start["y"] - START_CARLA["y"]) < 0.7 for spec in actor_specs)
        last_object_check_index = -1
        sample_period = args.sample_period

        for index in range(int(config.max_duration / sample_period)):
            elapsed = time.time() - start_t
            motions: list[dict[str, Any]] = []
            for item in actor_handles:
                spec = item["spec"]
                actor = item["actor"]
                motion = actor_motion(spec, elapsed)
                actor.set_transform(
                    carla.Transform(
                        carla.Location(x=motion["x"], y=motion["y"], z=motion["z"]),
                        carla.Rotation(yaw=0.0),
                    )
                )
                actor.set_target_velocity(carla.Vector3D(motion["vx"], motion["vy"], 0.0))
                motions.append({"spec": spec, "motion": motion})
            if use_dummy_injection and node is not None and pub is not None and motions:
                primary_motion = motions[0]["motion"]
                primary_spec = motions[0]["spec"]
                pub.publish(
                    make_dummy_msg(
                        modules,
                        node,
                        DummyObject.MODIFY,
                        primary_motion["x"],
                        -primary_motion["y"],
                        0.0,
                        primary_spec.speed_x,
                        -primary_motion["vy"],
                    )
                )
                rclpy.spin_once(node, timeout_sec=0.02)

            ego_sample = sample_actor(ego)
            target_samples: list[dict[str, Any]] = []
            primary_target_sample: dict[str, Any] | None = None
            for item in actor_handles:
                spec = item["spec"]
                actor = item["actor"]
                target_sample = sample_actor(actor)
                dx = target_sample["x"] - ego_sample["x"]
                dy = target_sample["y"] - ego_sample["y"]
                distance = math.sqrt(dx * dx + dy * dy)
                closing_speed = ego_sample["speed_mps"] - spec.speed_x if dx > 0 else None
                ttc = distance / closing_speed if closing_speed and closing_speed > 0.1 else None
                min_distance = distance if min_distance is None else min(min_distance, distance)
                if ttc is not None:
                    min_ttc = ttc if min_ttc is None else min(min_ttc, ttc)
                enriched = {**target_sample, "name": spec.name, "distance_m": distance, "ttc_sec": ttc}
                target_samples.append(enriched)
                if primary_target_sample is None:
                    primary_target_sample = enriched
            if args.spectator_mode != "none":
                last_spectator_view = apply_spectator_view(
                    world=world,
                    carla=carla,
                    mode=args.spectator_mode,
                    ego_sample=ego_sample,
                    target_samples=target_samples,
                )
            if video_recorder is not None:
                camera_view = spectator_transform_params(args.camera_video_mode, ego_sample, target_samples)
                if camera_view is not None:
                    video_recorder.set_transform(carla=carla, transform_params=camera_view)
                    last_camera_view = camera_view
                video_recorder.drain()
            max_speed = max(max_speed, ego_sample["speed_mps"])
            if any(abs(item["y"] - START_CARLA["y"]) < 0.7 for item in target_samples):
                target_in_lane = True
            if target_in_lane and max_speed > 1.0:
                min_speed_after_reaction = ego_sample["speed_mps"] if min_speed_after_reaction is None else min(min_speed_after_reaction, ego_sample["speed_mps"])
                slowed_by_ratio = ego_sample["speed_mps"] <= max_speed * args.reaction_speed_ratio
                brake_applied = ego_sample.get("brake") is not None and ego_sample["brake"] > 0.2
                near_stop = ego_sample["speed_mps"] < 1.0
                if near_stop or brake_applied or slowed_by_ratio:
                    reaction_seen = True
                    if reaction_reason is None:
                        if near_stop:
                            reaction_reason = "near_stop"
                        elif brake_applied:
                            reaction_reason = "brake_applied"
                        else:
                            reaction_reason = "speed_reduction_ratio"

            samples.append(
                {
                    "i": index,
                    "t": elapsed,
                    "frame": world.get_snapshot().frame,
                    "ego": ego_sample,
                    "target": primary_target_sample,
                    "targets": target_samples,
                    "collision_count": len(collision_events),
                    "target_in_lane": target_in_lane,
                }
            )
            if not objects_nonempty and index > 10 and index - last_object_check_index >= 10:
                object_sample = object_topic_sample(env)
                object_check_count += 1
                object_nonempty_check_count += int(bool(object_sample["nonempty"]))
                objects_nonempty = objects_nonempty or bool(object_sample["nonempty"])
                max_object_count = max(max_object_count, int(object_sample["count"]))
                last_object_check_index = index
            if collision_events:
                break
            if elapsed > args.min_runtime_sec and reaction_seen and len(samples) > args.min_samples_after_reaction:
                break
            time.sleep(sample_period)

        if video_recorder is not None:
            video_recorder.drain()

        if not objects_nonempty:
            object_sample = object_topic_sample(env)
            object_check_count += 1
            object_nonempty_check_count += int(bool(object_sample["nonempty"]))
            objects_nonempty = bool(object_sample["nonempty"])
            max_object_count = max(max_object_count, int(object_sample["count"]))
        elif max_object_count == 0:
            object_sample = object_topic_sample(env)
            object_check_count += 1
            object_nonempty_check_count += int(bool(object_sample["nonempty"]))
            max_object_count = max(max_object_count, int(object_sample["count"]))

        summary = {
            "sample_count": len(samples),
            "moved": max_speed > 1.0,
            "collision_count": len(collision_events),
            "min_distance_m": min_distance,
            "min_ttc_sec": min_ttc if min_ttc is not None else 999.0,
            "autoware_reacted": reaction_seen,
            "reaction_reason": reaction_reason,
            "target_in_lane": target_in_lane,
            "max_speed_mps": max_speed,
            "min_speed_after_target_in_lane_mps": min_speed_after_reaction,
            "final_speed_mps": samples[-1]["ego"]["speed_mps"] if samples else None,
            "total_delta_m": math.sqrt((samples[-1]["ego"]["x"] - samples[0]["ego"]["x"]) ** 2 + (samples[-1]["ego"]["y"] - samples[0]["ego"]["y"]) ** 2) if len(samples) > 1 else 0.0,
            "actor_count_spawned": len(actor_handles),
            "actor_count_observed": max_object_count,
            "object_pipeline_nonempty_duration_ratio": object_nonempty_check_count / object_check_count if object_check_count else (1.0 if objects_nonempty else 0.0),
            "last_ego": samples[-1]["ego"] if samples else None,
            "last_target": samples[-1]["target"] if samples else None,
            "last_targets": samples[-1]["targets"] if samples else [],
            "spectator_mode": args.spectator_mode,
            "last_spectator_view": last_spectator_view,
            "camera_video": {
                "path": str(video_recorder.output_path) if video_recorder is not None else None,
                "mode": args.camera_video_mode if video_recorder is not None else None,
                "width": video_recorder.width if video_recorder is not None else None,
                "height": video_recorder.height if video_recorder is not None else None,
                "fps": video_recorder.fps if video_recorder is not None else None,
                "frames_written": video_recorder.frames_written if video_recorder is not None else 0,
                "frames_dropped": video_recorder.frames_dropped if video_recorder is not None else 0,
                "last_camera_view": last_camera_view,
            },
        }
        safety_passed = summary["collision_count"] == 0 and (summary["min_distance_m"] or 0) >= config.safe_distance_m and summary["min_ttc_sec"] >= config.safe_ttc_sec
        actor_count_passed = not config.actors or summary["actor_count_observed"] >= min(2, len(actor_handles))
        response_passed = objects_nonempty and actor_count_passed and summary["autoware_reacted"] and summary["moved"] and summary["target_in_lane"]
        result = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "classification": f"{config.classification}:{args.perception_source}",
            "run_dir": str(run_dir),
            "test_dir": str(test_dir),
            "start": {"carla": START_CARLA, "map": START_MAP},
            "goal": GOAL_MAP,
            "target": {
                "type_id": config.target_type,
                "start_carla": config.target_start,
                "final_carla_y": config.target_final_y,
                "speed_x_mps": config.target_speed_x,
                "cut_in_duration_sec": config.cut_in_duration,
            },
            "actors": [
                {
                    "name": spec.name,
                    "type_id": spec.target_type,
                    "start_carla": spec.start,
                    "final_carla_y": spec.final_y,
                    "speed_x_mps": spec.speed_x,
                    "cut_in_duration_sec": spec.cut_in_duration,
                    "static_target": spec.static_target,
                    "activation_sec": spec.activation_sec,
                }
                for spec in actor_specs
            ],
            "service_calls": service_calls,
            "collision_events": collision_events,
            "samples": samples,
            "summary": summary,
            "object_pipeline": {
                "perception_source": args.perception_source,
                "dummy_object_injected": use_dummy_injection,
                "actor_bridge_expected": args.perception_source == "actor_bridge",
                "objects_topic_nonempty_after_injection": objects_nonempty,
                "actor_count_observed": max_object_count,
                "expected_actor_count": len(actor_handles),
            },
            "recording": {"rosbag_dir": str(bag_dir), "carla_recorder": carla_recorder},
            "diagnostics": {
                "safe_distance_threshold_m": config.safe_distance_m,
                "safe_ttc_threshold_sec": config.safe_ttc_sec,
                "reaction_speed_ratio_threshold": args.reaction_speed_ratio,
                "expected_actor_count": len(actor_handles),
            },
            "verdict": {
                "overall_passed": safety_passed and response_passed,
                "safety_passed": safety_passed,
                "autoware_dynamic_actor_response_passed": response_passed,
            },
        }
        artifact_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        summary_payload = {
            **result["verdict"],
            "summary": summary,
            "object_pipeline": result["object_pipeline"],
            "artifact": str(artifact_path),
            "rosbag_dir": str(bag_dir),
            "carla_recorder": carla_recorder,
        }
        summary_path.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return summary_payload
    finally:
        if node is not None:
            try:
                pub = node.create_publisher(DummyObject, "/simulation/dummy_perception_publisher/object_info", 10)
                for _ in range(5):
                    pub.publish(make_dummy_msg(modules, node, DummyObject.DELETEALL, 0.0, 0.0, 0.0, 0.0, 0.0))
                    rclpy.spin_once(node, timeout_sec=0.05)
                    time.sleep(0.1)
                node.destroy_node()
                rclpy.shutdown()
            except Exception as exc:
                print(f"cleanup dummy failed: {exc}", file=sys.stderr)
        try:
            run_cmd("engage_false_cleanup", ["timeout", "15", "ros2", "service", "call", "/api/autoware/set/engage", "tier4_external_api_msgs/srv/Engage", "{engage: false}"], env, service_calls, 18)
            run_cmd("change_to_stop_cleanup", ["timeout", "15", "ros2", "service", "call", "/api/operation_mode/change_to_stop", "autoware_adapi_v1_msgs/srv/ChangeOperationMode", "{}"], env, service_calls, 18)
        except Exception as exc:
            print(f"cleanup services failed: {exc}", file=sys.stderr)
        if client is not None and recording_started:
            try:
                client.stop_recorder()
            except Exception as exc:
                print(f"stop recorder failed: {exc}", file=sys.stderr)
        if video_recorder is not None:
            try:
                video_recorder.close()
            except Exception as exc:
                print(f"close camera video failed: {exc}", file=sys.stderr)
        if collision_sensor is not None:
            try:
                collision_sensor.stop()
                collision_sensor.destroy()
            except Exception:
                pass
        for item in actor_handles:
            try:
                item["actor"].destroy()
            except Exception:
                pass
        if bag_proc is not None and bag_proc.poll() is None:
            try:
                os.killpg(os.getpgid(bag_proc.pid), signal.SIGINT)
                bag_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(bag_proc.pid), signal.SIGTERM)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Existing simctl run directory on the runtime host")
    parser.add_argument("--kind", choices=sorted(PROBES), required=True, help="Probe type to execute")
    parser.add_argument("--ros-domain-id", type=int, default=21)
    parser.add_argument("--rmw-implementation", default="rmw_cyclonedds_cpp")
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=2000)
    parser.add_argument("--carla-timeout", type=float, default=10.0)
    parser.add_argument("--ego-timeout", type=int, default=20)
    parser.add_argument("--sample-period", type=float, default=0.2)
    parser.add_argument("--min-runtime-sec", type=float, default=20.0)
    parser.add_argument("--min-samples-after-reaction", type=int, default=120)
    parser.add_argument(
        "--spectator-mode",
        choices=["none", "ego_chase", "overview"],
        default="none",
        help="Move the CARLA spectator during the probe so screen recordings show ego/actor motion.",
    )
    parser.add_argument(
        "--camera-video-output",
        help="Optional mp4 path for CARLA RGB camera evidence recorded directly during the probe.",
    )
    parser.add_argument(
        "--camera-video-mode",
        choices=["ego_chase", "overview"],
        default="ego_chase",
        help="Camera view used when --camera-video-output is set.",
    )
    parser.add_argument("--camera-video-width", type=int, default=1280)
    parser.add_argument("--camera-video-height", type=int, default=720)
    parser.add_argument("--camera-video-fps", type=int, default=10)
    parser.add_argument(
        "--reaction-speed-ratio",
        type=float,
        default=0.4,
        help="Count response when ego speed after target enters lane falls below this fraction of observed max speed.",
    )
    parser.add_argument(
        "--perception-source",
        choices=["dummy_injection", "actor_bridge"],
        default="dummy_injection",
        help="Use probe-local DummyObject injection or require the stack CARLA actor object bridge to publish objects.",
    )
    parser.add_argument("--no-rosbag", dest="record_rosbag", action="store_false", help="Skip rosbag recording")
    parser.set_defaults(record_rosbag=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_probe(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
