from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.adapters import AdapterContext, load_reconstruction_adapter
from simctl.profiles import load_algorithm_profile, load_sensor_profile


class ProfileLoaderTests(unittest.TestCase):
    def test_load_sensor_profile_from_catalog(self) -> None:
        profile = load_sensor_profile("production_perception", REPO_ROOT)
        self.assertEqual(profile.profile_id, "production_perception")
        self.assertIn("lidar", profile.sensors)
        self.assertEqual(profile.truth_mode, "disabled")

    def test_load_dense_multiview_reconstruction_sensor_profile(self) -> None:
        profile = load_sensor_profile("reconstruction_dense_multiview_capture", REPO_ROOT)
        self.assertEqual(profile.profile_id, "reconstruction_dense_multiview_capture")
        self.assertIn("actor_masks", profile.payload["deliverables"])
        self.assertIn("rear_camera", profile.sensors)

    def test_load_algorithm_profile_from_yaml(self) -> None:
        profile = load_algorithm_profile("planning_control_baseline", REPO_ROOT)
        self.assertEqual(profile.profile_id, "planning_control_baseline")
        self.assertEqual(profile.profile_type, "planning_control")
        self.assertIn("outputs", profile.payload)

    def test_load_dynamic_reconstruction_adapter(self) -> None:
        adapter = load_reconstruction_adapter("reconstruction_dynamic_public_road_gaussians")
        output = adapter.reconstruct(
            AdapterContext(
                run_id="run-1",
                scenario_id="scenario-1",
                stack="stable",
                sensor_profile="reconstruction_dense_multiview_capture",
                algorithm_profile="reconstruction_dynamic_public_road_gaussians",
                metadata={"run_dir": "D:/tmp/run-1"},
            )
        )
        self.assertEqual(output.family, "dynamic_gaussians")
        self.assertIn("dynamic_tracks", output.artifacts)

    def test_load_site_proxy_reconstruction_adapter(self) -> None:
        adapter = load_reconstruction_adapter("reconstruction_site_proxy")
        output = adapter.reconstruct(
            AdapterContext(
                run_id="run-1",
                scenario_id="stable_l2_reconstruction_site_proxy_refresh",
                stack="stable",
                sensor_profile="reconstruction_capture",
                algorithm_profile="reconstruction_site_proxy",
                metadata={"run_dir": "runs/site-proxy"},
            )
        )
        self.assertEqual(output.family, "site_proxy")
        self.assertIn("registered_pointcloud", output.artifacts)
        self.assertIn("lanelet_update", output.artifacts)


if __name__ == "__main__":
    unittest.main()
