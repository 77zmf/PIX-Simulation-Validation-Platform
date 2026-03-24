from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.profiles import load_algorithm_profile, load_sensor_profile


class ProfileLoaderTests(unittest.TestCase):
    def test_load_sensor_profile_from_catalog(self) -> None:
        profile = load_sensor_profile("production_perception", REPO_ROOT)
        self.assertEqual(profile.profile_id, "production_perception")
        self.assertIn("lidar", profile.sensors)
        self.assertEqual(profile.truth_mode, "disabled")

    def test_load_algorithm_profile_from_yaml(self) -> None:
        profile = load_algorithm_profile("planning_control_baseline", REPO_ROOT)
        self.assertEqual(profile.profile_id, "planning_control_baseline")
        self.assertEqual(profile.profile_type, "planning_control")
        self.assertIn("outputs", profile.payload)


if __name__ == "__main__":
    unittest.main()
