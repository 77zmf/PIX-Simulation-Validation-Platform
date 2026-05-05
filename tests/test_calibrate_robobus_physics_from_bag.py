from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "calibrate_robobus_physics_from_bag.py"

spec = importlib.util.spec_from_file_location("calibrate_robobus_physics_from_bag", TOOL_PATH)
assert spec and spec.loader
calibrate = importlib.util.module_from_spec(spec)
sys.modules["calibrate_robobus_physics_from_bag"] = calibrate
spec.loader.exec_module(calibrate)


SAMPLE_METADATA = """rosbag2_bagfile_information:
  topics_with_message_count:
    - topic_metadata:
        name: /sensing/vehicle_velocity_converter/twist_with_covariance
        type: geometry_msgs/msg/TwistWithCovarianceStamped
        serialization_format: cdr
      message_count: 120
    - topic_metadata:
        name: /pix_robobus/va_chassis_wheel_rpm_fb
        type: pix_robobus_driver_msgs/msg/VaChassisWheelRpmFb
        serialization_format: cdr
      message_count: 121
"""


SAMPLE_TRAJECTORY = """cloud_bag_time_ns,cloud_stamp_ns,tf_stamp_ns,frame_id,points,x,y,z,qx,qy,qz,qw
1000000000,1000000000,1000000000,base_link,1,0.0,0.0,0.0,0.0,0.0,0.0,1.0
2000000000,2000000000,2000000000,base_link,1,2.0,0.0,0.0,0.0,0.0,0.0,1.0
3000000000,3000000000,3000000000,base_link,1,5.0,0.0,0.0,0.0,0.0,0.0871557427,0.9961946981
"""


class CalibrateRobobusPhysicsFromBagTests(unittest.TestCase):
    def test_load_metadata_topics_keeps_message_counts_and_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.yaml"
            path.write_text(SAMPLE_METADATA, encoding="utf-8")

            topics = calibrate.load_metadata_topics(path)

        self.assertEqual(
            topics["/sensing/vehicle_velocity_converter/twist_with_covariance"]["type"],
            "geometry_msgs/msg/TwistWithCovarianceStamped",
        )
        self.assertEqual(topics["/pix_robobus/va_chassis_wheel_rpm_fb"]["message_count"], 121)

    def test_trajectory_summary_derives_speed_accel_and_yaw_rate_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory_samples.csv"
            path.write_text(SAMPLE_TRAJECTORY, encoding="utf-8")

            poses = calibrate.load_trajectory_csv(path)
            summary = calibrate.summarize_trajectory(poses)

        self.assertTrue(summary["available"])
        self.assertEqual(summary["pose_count"], 3)
        self.assertAlmostEqual(summary["route_length_m"], 5.0)
        self.assertAlmostEqual(summary["speed_mps"]["max"], 3.0)
        self.assertAlmostEqual(summary["accel_mps2"]["max"], 1.0)
        self.assertGreater(summary["yaw_rate_radps_abs"]["max"], 0.17)

    def test_suggestions_reduce_throttle_when_carla_reference_is_too_fast(self) -> None:
        dynamics_summary = {
            "/sensing/vehicle_velocity_converter/twist_with_covariance": {
                "speed_mps": {"p95": 4.0, "p99": 4.4, "max": 4.6},
                "decel_mps2_abs": {"p95": 1.2},
                "yaw_rate_radps_abs": {"p95": 0.3},
            }
        }

        result = calibrate.suggest_runtime_overrides(
            dynamics_summary,
            current_carla_max_speed_mps=20.0,
            current_throttle_gain=3.8,
            current_max_throttle=1.0,
            current_brake_gain=0.2,
            current_max_brake=0.8,
            current_steer_gain=0.9,
        )

        overrides = result["stable_runtime_overrides"]
        self.assertLess(overrides["pix_carla_throttle_gain"]["suggested"], 3.8)
        self.assertLess(overrides["pix_carla_max_throttle"]["suggested"], 1.0)
        self.assertEqual(overrides["pix_carla_steer_gain"]["suggested"], 0.9)

    def test_planning_speed_and_brake_commands_feed_recommendation(self) -> None:
        dynamics_summary = {
            "/vehicle/status/velocity_status": {
                "speed_mps": {"p95": 8.4, "p99": 8.6, "max": 8.9},
                "decel_mps2_abs": {"p95": 0.91},
            },
            "/control/command/actuation_cmd": {
                "numeric_abs_stats": {
                    "actuation_brake_cmd": {"p95": 0.43, "max": 0.53},
                    "actuation_steer_cmd": {"max": 0.42},
                }
            },
            "/vehicle/status/steering_status": {
                "numeric_abs_stats": {
                    "steering_tire_angle_rad": {"max": 0.42},
                }
            },
        }

        result = calibrate.suggest_runtime_overrides(
            dynamics_summary,
            current_carla_max_speed_mps=8.51,
            current_throttle_gain=3.8,
            current_max_throttle=1.0,
            current_brake_gain=0.2,
            current_max_brake=0.8,
            current_steer_gain=0.9,
        )

        overrides = result["stable_runtime_overrides"]
        self.assertEqual(result["real_speed_p95_mps"], 8.4)
        self.assertEqual(overrides["pix_carla_throttle_gain"]["suggested"], 3.8)
        self.assertGreater(overrides["pix_carla_brake_gain"]["suggested"], 1.0)
        self.assertEqual(overrides["pix_carla_max_brake"]["suggested"], 1.0)

    def test_summary_keeps_signed_and_absolute_planning_command_stats(self) -> None:
        samples = {
            "/control/command/actuation_cmd": [
                {"t_sec": 1.0, "actuation_steer_cmd": -0.3, "actuation_brake_cmd": 0.1},
                {"t_sec": 2.0, "actuation_steer_cmd": 0.2, "actuation_brake_cmd": 0.4},
            ]
        }

        summary = calibrate.summarize_bag_samples(samples)

        self.assertEqual(
            summary["/control/command/actuation_cmd"]["numeric_stats"]["actuation_steer_cmd"]["min"],
            -0.3,
        )
        self.assertEqual(
            summary["/control/command/actuation_cmd"]["numeric_abs_stats"]["actuation_steer_cmd"]["max"],
            0.3,
        )

    def test_parse_planning_control_and_status_messages(self) -> None:
        control = SimpleNamespace(
            lateral=SimpleNamespace(steering_tire_angle=0.12, steering_tire_rotation_rate=0.3),
            longitudinal=SimpleNamespace(velocity=4.5, acceleration=-0.8, jerk=0.1),
        )
        actuation = SimpleNamespace(
            actuation=SimpleNamespace(accel_cmd=0.0, brake_cmd=0.42, steer_cmd=0.11)
        )
        steering = SimpleNamespace(steering_tire_angle=0.10)
        velocity = SimpleNamespace(longitudinal_velocity=3.2, lateral_velocity=0.1, heading_rate=0.02)

        self.assertEqual(
            calibrate.parse_ros_message("/control/command/control_cmd", control, 1.0)[
                "control_steering_tire_angle_rad"
            ],
            0.12,
        )
        self.assertEqual(
            calibrate.parse_ros_message("/control/command/actuation_cmd", actuation, 1.0)[
                "actuation_brake_cmd"
            ],
            0.42,
        )
        self.assertEqual(
            calibrate.parse_ros_message("/vehicle/status/steering_status", steering, 1.0)[
                "steering_tire_angle_rad"
            ],
            0.10,
        )
        self.assertEqual(
            calibrate.parse_ros_message("/vehicle/status/velocity_status", velocity, 1.0)["speed_mps"],
            3.2,
        )


if __name__ == "__main__":
    unittest.main()
