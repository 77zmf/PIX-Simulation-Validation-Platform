from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_probe(module_name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


carla_sensor_topic_probe = _load_probe(
    "carla_sensor_topic_probe",
    "ops/runtime_probes/carla_sensor_topic_probe.py",
)
perception_readiness_probe = _load_probe(
    "perception_readiness_probe",
    "ops/runtime_probes/perception_readiness_probe.py",
)


class RuntimeProbeSerializationTests(unittest.TestCase):
    def test_sensor_probe_has_bridge_only_profile(self) -> None:
        profile = carla_sensor_topic_probe.PROFILES["robobus117th_bridge_only"]
        topics = {spec.topic for spec in profile}

        self.assertIn("/sensing/camera/CAM_FRONT/image_raw", topics)
        self.assertIn("/sensing/lidar/top/pointcloud_before_sync", topics)
        self.assertIn("/sensing/imu/tamagawa/imu_raw", topics)
        self.assertIn("/vehicle/status/velocity_status", topics)
        self.assertNotIn("/tf", topics)
        self.assertNotIn("/vehicle/status/steering_status", topics)
        self.assertNotIn("/perception/object_recognition/objects", topics)
        self.assertNotIn("/control/command/control_cmd", topics)

    def test_sensor_probe_has_l0_closed_loop_profile(self) -> None:
        profile = carla_sensor_topic_probe.PROFILES["robobus117th_l0_closed_loop"]
        topics = {spec.topic for spec in profile}

        self.assertIn("/sensing/camera/CAM_FRONT/image_raw", topics)
        self.assertIn("/sensing/lidar/rear_top/pointcloud_before_sync", topics)
        self.assertIn("/vehicle/status/velocity_status", topics)
        self.assertIn("/control/command/control_cmd", topics)
        self.assertIn("/tf", topics)
        self.assertNotIn("/simulation/dummy_perception_publisher/object_info", topics)
        self.assertNotIn("/perception/object_recognition/objects", topics)

    def test_sensor_topic_tail_normalizes_timeout_bytes(self) -> None:
        self.assertEqual(
            carla_sensor_topic_probe._tail(b"prefix-\xe4\xb8\xad\xe6\x96\x87", limit=6),
            "fix-中文",
        )

    def test_perception_tail_normalizes_timeout_bytes(self) -> None:
        self.assertEqual(perception_readiness_probe._tail(None), "")
        self.assertEqual(perception_readiness_probe._tail(b"abc", limit=2), "bc")


if __name__ == "__main__":
    unittest.main()
