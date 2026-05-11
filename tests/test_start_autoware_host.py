from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "stack" / "stable" / "start_autoware_host.sh"
BEVFUSION_SCRIPT = REPO_ROOT / "stack" / "stable" / "start_bevfusion_perception_host.sh"
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
        self.assertIn("Autoware launch file: planning_simulator.launch.xml", proc.stdout)
        self.assertIn("export PYTHONNOUSERSITE=1", proc.stdout)

    def test_renders_custom_launch_file_data_path_and_extra_args(self) -> None:
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
                "--autoware-ws",
                "/opt/autoware",
                "--map-path",
                "/maps/Town01",
                "--vehicle-model",
                "robobus",
                "--sensor-model",
                "robobus_sensor_kit",
                "--launch-file",
                "autoware.launch.xml",
                "--data-path",
                "/data/pix/autoware_data",
                "--launch-extra-args",
                "launch_detection:=true use_deeplearning_model:=true",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Autoware launch file: autoware.launch.xml", proc.stdout)
        self.assertIn("Autoware data path: /data/pix/autoware_data", proc.stdout)
        self.assertIn("Autoware launch extra args: launch_detection:=true use_deeplearning_model:=true", proc.stdout)
        self.assertIn("ros2 launch autoware_launch autoware.launch.xml", proc.stdout)
        self.assertIn("data_path:='/data/pix/autoware_data'", proc.stdout)
        self.assertIn("launch_detection:=true use_deeplearning_model:=true", proc.stdout)

    def test_renders_standalone_bevfusion_perception_launch(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(BEVFUSION_SCRIPT),
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
                "--extra-setup",
                "/opt/autoware_base/install/setup.bash",
                "--input-pointcloud",
                "/sensing/lidar/top/pointcloud_before_sync",
                "--output-objects",
                "/perception/object_recognition/detection/bevfusion/objects",
                "--data-path",
                "/data/pix/autoware_data",
                "--model-param-path",
                "/opt/autoware/bevfusion_lidar.param.yaml",
                "--common-param-path",
                "/opt/autoware/bevfusion_common.param.yaml",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("BEVFusion extra setup: /opt/autoware_base/install/setup.bash", proc.stdout)
        self.assertIn("source '/opt/autoware_base/install/setup.bash' && source install/setup.bash", proc.stdout)
        self.assertIn("ros2 launch autoware_bevfusion bevfusion.launch.xml", proc.stdout)
        self.assertIn("input/pointcloud:='/sensing/lidar/top/pointcloud_before_sync'", proc.stdout)
        self.assertIn(
            "output/objects:='/perception/object_recognition/detection/bevfusion/objects'",
            proc.stdout,
        )
        self.assertIn("data_path:='/data/pix/autoware_data'", proc.stdout)
        self.assertIn("model_name:='bevfusion_lidar'", proc.stdout)
        self.assertIn("model_param_path:='/opt/autoware/bevfusion_lidar.param.yaml'", proc.stdout)
        self.assertIn("common_param_path:='/opt/autoware/bevfusion_common.param.yaml'", proc.stdout)

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
