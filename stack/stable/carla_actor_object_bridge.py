#!/usr/bin/env python3
"""Bridge non-ego CARLA actors into Autoware dummy perception objects."""

from __future__ import annotations

import argparse
import math
import signal
import time
from typing import Any


STOP_REQUESTED = False


def request_stop(_signum: int, _frame: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def q_from_yaw(deg: float) -> dict[str, float]:
    rad = math.radians(deg)
    return {"x": 0.0, "y": 0.0, "z": math.sin(rad / 2.0), "w": math.cos(rad / 2.0)}


def actor_uuid(actor_id: int) -> list[int]:
    payload = actor_id.to_bytes(4, byteorder="big", signed=False)
    return [0xCA, 0xA0, 0x00, 0x01, *payload, 0x00, 0x00, 0x00, 0x00, 0x17, 0x7A, 0x0B, 0x1E]


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


def is_ego_actor(actor: Any, ego_role_name: str) -> bool:
    role_name = actor.attributes.get("role_name", "")
    return role_name in {ego_role_name, "ego_vehicle", "hero", "autoware_v1"}


def is_visual_only_actor(actor: Any) -> bool:
    return actor.attributes.get("role_name", "").startswith("pix_visual_only_")


def actor_label(actor: Any, ObjectClassification: Any) -> int:
    type_id = str(actor.type_id)
    if type_id.startswith("walker.pedestrian."):
        return ObjectClassification.PEDESTRIAN
    if type_id.startswith("vehicle."):
        if ".bus" in type_id:
            return ObjectClassification.BUS
        if ".truck" in type_id:
            return ObjectClassification.TRUCK
        if ".motorcycle" in type_id:
            return ObjectClassification.MOTORCYCLE
        if ".bicycle" in type_id:
            return ObjectClassification.BICYCLE
        return ObjectClassification.CAR
    return ObjectClassification.UNKNOWN


def apply_actor_shape(msg: Any, actor: Any, Shape: Any, Vector3: Any) -> None:
    type_id = str(actor.type_id)
    if type_id.startswith("walker.pedestrian."):
        msg.shape.type = Shape.CYLINDER
        msg.shape.dimensions = Vector3(x=0.6, y=0.6, z=2.0)
        return
    extent = actor.bounding_box.extent
    msg.shape.type = Shape.BOUNDING_BOX
    msg.shape.dimensions = Vector3(
        x=max(0.1, float(extent.x) * 2.0),
        y=max(0.1, float(extent.y) * 2.0),
        z=max(0.1, float(extent.z) * 2.0),
    )


def make_dummy_object(modules: dict[str, Any], node: Any, actor: Any, action: int) -> Any:
    DummyObject = modules["DummyObject"]
    ObjectClassification = modules["ObjectClassification"]
    Shape = modules["Shape"]
    Vector3 = modules["Vector3"]

    msg = DummyObject()
    msg.header.frame_id = "map"
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.id.uuid = actor_uuid(int(actor.id))
    msg.action = action
    if action == DummyObject.DELETE:
        return msg

    transform = actor.get_transform()
    velocity = actor.get_velocity()
    q = q_from_yaw(-float(transform.rotation.yaw))
    pose = msg.initial_state.pose_covariance.pose
    pose.position.x = float(transform.location.x)
    pose.position.y = -float(transform.location.y)
    pose.position.z = float(transform.location.z)
    pose.orientation.x = q["x"]
    pose.orientation.y = q["y"]
    pose.orientation.z = q["z"]
    pose.orientation.w = q["w"]
    msg.initial_state.pose_covariance.covariance[0] = 0.2
    msg.initial_state.pose_covariance.covariance[7] = 0.2
    msg.initial_state.pose_covariance.covariance[35] = 0.05
    msg.initial_state.twist_covariance.twist.linear.x = float(velocity.x)
    msg.initial_state.twist_covariance.twist.linear.y = -float(velocity.y)
    msg.classification.label = actor_label(actor, ObjectClassification)
    msg.classification.probability = 1.0
    apply_actor_shape(msg, actor, Shape, Vector3)
    speed = math.sqrt(velocity.x * velocity.x + velocity.y * velocity.y + velocity.z * velocity.z)
    msg.max_velocity = max(0.1, float(speed))
    msg.min_velocity = 0.0
    return msg


def publish_delete_all(modules: dict[str, Any], node: Any, publisher: Any) -> None:
    DummyObject = modules["DummyObject"]
    msg = DummyObject()
    msg.header.frame_id = "map"
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.action = DummyObject.DELETEALL
    try:
        publisher.publish(msg)
    except Exception as exc:
        print(f"delete_all publish skipped: {exc}", flush=True)


def spin_once_safe(rclpy: Any, node: Any, timeout_sec: float) -> None:
    try:
        rclpy.spin_once(node, timeout_sec=timeout_sec)
    except Exception as exc:
        print(f"spin_once skipped: {exc}", flush=True)


def iter_target_actors(world: Any, *, ego_role_name: str, include_walkers: bool) -> list[Any]:
    actors = []
    for actor in world.get_actors().filter("vehicle.*"):
        if not is_ego_actor(actor, ego_role_name) and not is_visual_only_actor(actor):
            actors.append(actor)
    if include_walkers:
        actors.extend(
            actor
            for actor in world.get_actors().filter("walker.pedestrian.*")
            if not is_visual_only_actor(actor)
        )
    return actors


def wait_for_carla_client(args: argparse.Namespace, carla: Any) -> Any:
    deadline = time.monotonic() + args.carla_wait_sec
    last_error: Exception | None = None
    attempt = 0
    while not STOP_REQUESTED:
        attempt += 1
        try:
            client = carla.Client(args.carla_host, args.carla_port)
            client.set_timeout(args.carla_timeout)
            world = client.get_world()
            _ = world.get_snapshot()
            print(f"CARLA actor object bridge connected after {attempt} attempt(s)", flush=True)
            return client
        except RuntimeError as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                break
            print(
                f"Waiting for CARLA RPC at {args.carla_host}:{args.carla_port}: {exc}",
                flush=True,
            )
            time.sleep(2.0)
    raise RuntimeError(
        f"CARLA RPC was not ready within {args.carla_wait_sec:.1f}s at "
        f"{args.carla_host}:{args.carla_port}: {last_error}"
    )


def run_bridge(args: argparse.Namespace) -> None:
    modules = load_runtime_modules()
    carla = modules["carla"]
    rclpy = modules["rclpy"]
    DummyObject = modules["DummyObject"]

    client = wait_for_carla_client(args, carla)
    rclpy.init(args=None)
    node = rclpy.create_node("pix_carla_actor_object_bridge")
    publisher = node.create_publisher(DummyObject, args.output_topic, 10)
    seen_ids: set[int] = set()

    if args.delete_all_on_start:
        publish_delete_all(modules, node, publisher)
        spin_once_safe(rclpy, node, timeout_sec=0.05)

    try:
        while not STOP_REQUESTED:
            world = client.get_world()
            actors = iter_target_actors(
                world,
                ego_role_name=args.ego_vehicle_role_name,
                include_walkers=args.include_walkers,
            )
            active_ids = {int(actor.id) for actor in actors}
            for actor in actors:
                action = DummyObject.MODIFY if int(actor.id) in seen_ids else DummyObject.ADD
                publisher.publish(make_dummy_object(modules, node, actor, action))
            for deleted_id in sorted(seen_ids - active_ids):
                proxy = type("DeletedActor", (), {"id": deleted_id})()
                publisher.publish(make_dummy_object(modules, node, proxy, DummyObject.DELETE))
            seen_ids = active_ids
            rclpy.spin_once(node, timeout_sec=0.02)
            if args.print_status:
                print(f"published_actors={len(active_ids)}", flush=True)
            time.sleep(args.poll_sec)
    finally:
        if args.delete_all_on_stop:
            publish_delete_all(modules, node, publisher)
            spin_once_safe(rclpy, node, timeout_sec=0.05)
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception as exc:
            print(f"rclpy shutdown skipped: {exc}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=2000)
    parser.add_argument("--carla-timeout", type=float, default=10.0)
    parser.add_argument("--carla-wait-sec", type=float, default=240.0)
    parser.add_argument("--ego-vehicle-role-name", default="ego_vehicle")
    parser.add_argument("--output-topic", default="/simulation/dummy_perception_publisher/object_info")
    parser.add_argument("--poll-sec", type=float, default=0.2)
    parser.add_argument("--include-walkers", action="store_true")
    parser.add_argument("--delete-all-on-start", action="store_true")
    parser.add_argument("--delete-all-on-stop", action="store_true")
    parser.add_argument("--print-status", action="store_true")
    return parser.parse_args()


def main() -> int:
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    run_bridge(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
