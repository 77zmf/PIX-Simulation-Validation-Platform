#!/usr/bin/env python3
"""Bridge CARLA ego pose/status topics into Autoware localization topics."""

from __future__ import annotations

import math
import os

import rclpy
from autoware_vehicle_msgs.msg import VelocityReport
from geometry_msgs.msg import AccelWithCovarianceStamped
from geometry_msgs.msg import PoseWithCovarianceStamped
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tf2_ros import TransformBroadcaster


class CarlaLocalizationBridge(Node):
    """Publish CARLA-derived localization in the topic shape Autoware expects."""

    def __init__(self) -> None:
        super().__init__("carla_localization_bridge")
        self.source = os.environ.get("SIMCTL_CARLA_LOCALIZATION_SOURCE", "topics").strip().lower()
        self.carla_host = os.environ.get("SIMCTL_CARLA_HOST", "127.0.0.1")
        self.carla_port = int(os.environ.get("SIMCTL_CARLA_RPC_PORT", "2000"))
        self.ego_role_name = os.environ.get("SIMCTL_CARLA_EGO_ROLE_NAME", "ego_vehicle")
        self.ros_y_sign = _float_env("SIMCTL_CARLA_ROS_Y_SIGN", _float_env("PIX_CARLA_ROS_Y_SIGN", -1.0))
        self.carla_client = None
        self.carla_world = None
        self.carla_ego = None
        self._last_actor_warning_time = 0.0
        self.pose: PoseWithCovarianceStamped | None = None
        self.velocity = 0.0
        self.heading_rate = 0.0
        self.last_velocity: float | None = None
        self.last_time: float | None = None
        self.acceleration = 0.0

        self.create_subscription(
            PoseWithCovarianceStamped,
            "/sensing/gnss/pose_with_covariance",
            self._on_pose,
            10,
        )
        self.create_subscription(
            VelocityReport,
            "/vehicle/status/velocity_status",
            self._on_velocity,
            10,
        )
        self.odom_pub = self.create_publisher(Odometry, "/localization/kinematic_state", 10)
        self.accel_pub = self.create_publisher(
            AccelWithCovarianceStamped,
            "/localization/acceleration",
            10,
        )
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_timer(0.02, self._publish_state)

    def _on_pose(self, msg: PoseWithCovarianceStamped) -> None:
        if self.source == "carla_actor":
            return
        self.pose = msg

    def _on_velocity(self, msg: VelocityReport) -> None:
        if self.source == "carla_actor":
            return
        now = self.get_clock().now().nanoseconds / 1e9
        velocity = float(msg.longitudinal_velocity)
        if self.last_velocity is not None and self.last_time is not None:
            dt = max(1e-3, now - self.last_time)
            self.acceleration = max(-5.0, min(5.0, (velocity - self.last_velocity) / dt))
        self.last_velocity = velocity
        self.last_time = now
        self.velocity = velocity
        self.heading_rate = float(msg.heading_rate)

    def _publish_state(self) -> None:
        if self.source == "carla_actor":
            self._update_from_carla_actor()
        if self.pose is None:
            return

        stamp = self.get_clock().now().to_msg()
        pose = self.pose.pose

        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = "map"
        odom.child_frame_id = "base_link"
        odom.pose = self.pose.pose
        odom.twist.twist.linear.x = self.velocity
        odom.twist.twist.angular.z = self.heading_rate
        self.odom_pub.publish(odom)

        accel = AccelWithCovarianceStamped()
        accel.header.stamp = stamp
        accel.header.frame_id = "base_link"
        accel.accel.accel.linear.x = self.acceleration
        self.accel_pub.publish(accel)

        tf_msg = TransformStamped()
        tf_msg.header.stamp = stamp
        tf_msg.header.frame_id = "map"
        tf_msg.child_frame_id = "base_link"
        tf_msg.transform.translation.x = pose.pose.position.x
        tf_msg.transform.translation.y = pose.pose.position.y
        tf_msg.transform.translation.z = pose.pose.position.z
        tf_msg.transform.rotation = pose.pose.orientation
        self.tf_broadcaster.sendTransform(tf_msg)

    def _update_from_carla_actor(self) -> None:
        actor = self._get_carla_ego()
        if actor is None:
            return
        try:
            transform = actor.get_transform()
            velocity = actor.get_velocity()
            angular_velocity = actor.get_angular_velocity()
        except Exception as exc:
            self._warn_actor_once(f"failed to sample CARLA ego actor: {exc}")
            self.carla_ego = None
            return

        pose = PoseWithCovarianceStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = "map"
        pose.pose.pose.position.x = float(transform.location.x)
        pose.pose.pose.position.y = self.ros_y_sign * float(transform.location.y)
        pose.pose.pose.position.z = float(transform.location.z)
        quat = _quaternion_from_euler_deg(
            roll=float(transform.rotation.roll),
            pitch=self.ros_y_sign * float(transform.rotation.pitch),
            yaw=self.ros_y_sign * float(transform.rotation.yaw),
        )
        pose.pose.pose.orientation.x = quat["x"]
        pose.pose.pose.orientation.y = quat["y"]
        pose.pose.pose.orientation.z = quat["z"]
        pose.pose.pose.orientation.w = quat["w"]
        pose.pose.covariance[0] = 0.1
        pose.pose.covariance[7] = 0.1
        pose.pose.covariance[35] = 0.02

        now = self.get_clock().now().nanoseconds / 1e9
        yaw_rad = math.radians(float(transform.rotation.yaw))
        longitudinal_velocity = float(velocity.x) * math.cos(yaw_rad) + float(velocity.y) * math.sin(yaw_rad)
        if self.last_velocity is not None and self.last_time is not None:
            dt = max(1e-3, now - self.last_time)
            self.acceleration = max(-5.0, min(5.0, (longitudinal_velocity - self.last_velocity) / dt))
        self.last_velocity = longitudinal_velocity
        self.last_time = now
        self.velocity = longitudinal_velocity
        self.heading_rate = math.radians(float(getattr(angular_velocity, "z", 0.0)))
        self.pose = pose

    def _get_carla_ego(self):
        if self.carla_ego is not None and getattr(self.carla_ego, "is_alive", True):
            return self.carla_ego
        try:
            if self.carla_client is None:
                import carla  # type: ignore[import-not-found]

                self.carla_client = carla.Client(self.carla_host, self.carla_port)
                self.carla_client.set_timeout(2.0)
            self.carla_world = self.carla_client.get_world()
            vehicles = list(self.carla_world.get_actors().filter("vehicle.*"))
        except Exception as exc:
            self._warn_actor_once(f"failed to connect to CARLA {self.carla_host}:{self.carla_port}: {exc}")
            self.carla_client = None
            self.carla_world = None
            return None
        for vehicle in vehicles:
            if vehicle.attributes.get("role_name", "") == self.ego_role_name:
                self.carla_ego = vehicle
                return vehicle
        if len(vehicles) == 1:
            self.carla_ego = vehicles[0]
            return self.carla_ego
        self._warn_actor_once(f"CARLA ego actor '{self.ego_role_name}' not found; vehicles={len(vehicles)}")
        return None

    def _warn_actor_once(self, message: str) -> None:
        now = self.get_clock().now().nanoseconds / 1e9
        if now - self._last_actor_warning_time < 5.0:
            return
        self._last_actor_warning_time = now
        self.get_logger().warn(message)


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _quaternion_from_euler_deg(*, roll: float, pitch: float, yaw: float) -> dict[str, float]:
    cr = math.cos(math.radians(roll) * 0.5)
    sr = math.sin(math.radians(roll) * 0.5)
    cp = math.cos(math.radians(pitch) * 0.5)
    sp = math.sin(math.radians(pitch) * 0.5)
    cy = math.cos(math.radians(yaw) * 0.5)
    sy = math.sin(math.radians(yaw) * 0.5)
    return {
        "w": cr * cp * cy + sr * sp * sy,
        "x": sr * cp * cy - cr * sp * sy,
        "y": cr * sp * cy + sr * cp * sy,
        "z": cr * cp * sy - sr * sp * cy,
    }


def main() -> None:
    rclpy.init()
    node = CarlaLocalizationBridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
