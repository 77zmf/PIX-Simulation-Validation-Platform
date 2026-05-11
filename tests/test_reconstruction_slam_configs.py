from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.config import load_yaml
from simctl.evaluation import load_kpi_gate
from simctl.profiles import load_algorithm_profile
from simctl.scenarios import load_scenario


class ReconstructionSlamConfigTests(unittest.TestCase):
    def test_fast_lio_slam_scenario_links_profile_and_gate(self) -> None:
        scenario = load_scenario("scenarios/l2/reconstruction_fast_lio_slam_pose_prior.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l2" / "reconstruction_fast_lio_slam_pose_prior.yaml")
        profile = load_algorithm_profile("reconstruction_fast_lio_slam_pose_prior", REPO_ROOT)
        gate = load_kpi_gate("reconstruction_slam_pose_prior_gate", REPO_ROOT)

        self.assertEqual(scenario.sensor_profile, "reconstruction_capture")
        self.assertEqual(scenario.algorithm_profile, "reconstruction_fast_lio_slam_pose_prior")
        self.assertEqual(scenario.kpi_gate, "reconstruction_slam_pose_prior_gate")
        self.assertEqual(profile.payload["inputs"]["rgb_pointcloud_cache"]["implementation"], "color_pointscloud")
        self.assertEqual(profile.payload["inputs"]["slam_producer"]["implementation"], "liorf")
        self.assertIn(
            "/electronic_rearview_mirror/front_3mm/camera_image_jpeg",
            profile.payload["inputs"]["required_topics"]["rgb_camera"],
        )
        self.assertIn(
            "/electronic_rearview_mirror/rear_3mm/camera_image_jpeg",
            profile.payload["inputs"]["required_topics"]["rgb_camera"],
        )
        self.assertEqual(profile.payload["boundaries"]["execution_phase"], "offline_producer")
        self.assertEqual(profile.payload["boundaries"]["stable_runtime_control_loop"], "excluded")
        self.assertIn("external/liorf/config/lio_sam_robobus_ros2.yaml", payload["metadata"]["source_assets"])
        self.assertIn("--capture-profile rgb-map-camera", payload["metadata"]["validation_command"])
        self.assertIn("run_robobus_mapping.launch.py", payload["metadata"]["validation_command"])
        self.assertIn("slam_trajectory_present", gate.metrics)
        self.assertIn("lidar_imu_time_sync_error_ms", gate.metrics)


if __name__ == "__main__":
    unittest.main()
