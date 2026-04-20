#!/usr/bin/env python3
"""Bridge CARLA ego pose/status topics into Autoware localization topics."""

from __future__ import annotations

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
        self.pose = msg

    def _on_velocity(self, msg: VelocityReport) -> None:
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
