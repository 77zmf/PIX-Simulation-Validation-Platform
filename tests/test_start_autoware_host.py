from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "stack" / "stable" / "start_autoware_host.sh"
SCREENSHOT_SCRIPT = REPO_ROOT / "stack" / "stable" / "capture_visual_screenshot_host.sh"


class StartAutowareHostTests(unittest.TestCase):
    def test_renders_planning_control_rviz_config_launch_arg(self) -> None:
        rviz_config = "/opt/autoware/rviz/planning_bev.rviz"

        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
                "--autoware-ws",
                "/opt/autoware",
                "--map-path",
                "/maps/Town01",
                "--vehicle-model",
                "robobus",
                "--sensor-model",
                "robobus_sensor_kit",
                "--rviz",
                "true",
                "--rviz-config",
                rviz_config,
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RVIZ: true", proc.stdout)
        self.assertIn(f"RVIZ config: {rviz_config}", proc.stdout)
        self.assertIn(f"rviz_config:='{rviz_config}'", proc.stdout)
        self.assertIn("export PYTHONNOUSERSITE=1", proc.stdout)

    def test_visual_screenshot_metadata_declares_rviz_config_in_dry_run(self) -> None:
        rviz_config = "/opt/autoware/rviz/planning_bev.rviz"

        proc = subprocess.run(
            [
                "bash",
                str(SCREENSHOT_SCRIPT),
                "--run-dir",
                "/tmp/run",
                "--render-mode",
                "visual",
                "--rviz",
                "true",
                "--rviz-config",
                rviz_config,
                "--display",
                ":0",
                "--wait-sec",
                "0",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Visual screenshot requested", proc.stdout)
        self.assertIn(f"RViz config: {rviz_config}", proc.stdout)


if __name__ == "__main__":
    unittest.main()
