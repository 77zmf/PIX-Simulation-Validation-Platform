from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_probe():
    path = REPO_ROOT / "ops" / "runtime_probes" / "carla_vehicle_blueprint_probe.py"
    spec = importlib.util.spec_from_file_location("carla_vehicle_blueprint_probe", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class VehicleBlueprintProbeTests(unittest.TestCase):
    def test_metrics_expose_strict_bbox_failure(self) -> None:
        probe = _load_probe()
        summary = {
            "checks": {
                "blueprint_found": True,
                "ego_actor_seen": True,
                "actor_type_match": True,
                "pose_height_plausible": True,
                "bbox_plausible": False,
                "wheel_count": True,
                "wheel_radius_match": True,
                "wheelbase_match": True,
                "front_tread_match": True,
                "rear_tread_match": True,
                "front_steer_limit_match": True,
                "rear_steer_limit_match": True,
                "attached_sensor_count": True,
                "attached_camera_count": True,
                "attached_lidar_count": True,
            },
            "actor": {"bbox_extent_m": {"x": 0.0, "y": 1.046481, "z": 0.099537}},
            "wheel_geometry": {
                "wheelbase_cm": 302.010211,
                "front_tread_cm": 161.007822,
                "rear_tread_cm": 160.998667,
            },
            "wheels": [
                {"width_cm": 25.0, "tire_friction": 3.5},
                {"width_cm": 25.0, "tire_friction": 3.5},
                {"width_cm": 25.0, "tire_friction": 3.5},
                {"width_cm": 25.0, "tire_friction": 3.5},
            ],
            "attached_sensor_count": 13,
            "attached_camera_count": 6,
            "attached_lidar_count": 5,
        }

        metrics = probe.build_metrics(summary)
        payload = probe._payload_from_summary(SimpleNamespace(profile="robobus117th_vehicle_blueprint"), summary)

        self.assertEqual(metrics["robobus_bbox_plausible"], 0.0)
        self.assertEqual(metrics["robobus_bbox_extent_x_m"], 0.0)
        self.assertEqual(metrics["robobus_bbox_extent_z_m"], 0.099537)
        self.assertEqual(metrics["robobus_min_wheel_width_cm"], 25.0)
        self.assertFalse(payload["overall_passed"])
        self.assertIn("bbox_plausible", payload["blocked_reason"])

    def test_metrics_pass_when_geometry_and_sensors_are_plausible(self) -> None:
        probe = _load_probe()
        summary = {
            "checks": {
                "blueprint_found": True,
                "ego_actor_seen": True,
                "actor_type_match": True,
                "pose_height_plausible": True,
                "bbox_plausible": True,
                "wheel_count": True,
                "wheel_radius_match": True,
                "wheelbase_match": True,
                "front_tread_match": True,
                "rear_tread_match": True,
                "front_steer_limit_match": True,
                "rear_steer_limit_match": True,
                "attached_sensor_count": True,
                "attached_camera_count": True,
                "attached_lidar_count": True,
            },
            "actor": {"bbox_extent_m": {"x": 1.91, "y": 0.955, "z": 1.1045}},
            "wheel_geometry": {
                "wheelbase_cm": 302.0,
                "front_tread_cm": 161.0,
                "rear_tread_cm": 161.0,
            },
            "wheels": [
                {"width_cm": 25.0, "tire_friction": 3.5},
                {"width_cm": 25.0, "tire_friction": 3.5},
                {"width_cm": 25.0, "tire_friction": 3.5},
                {"width_cm": 25.0, "tire_friction": 3.5},
            ],
            "attached_sensor_count": 13,
            "attached_camera_count": 6,
            "attached_lidar_count": 5,
        }

        payload = probe._payload_from_summary(SimpleNamespace(profile="robobus117th_vehicle_blueprint"), summary)

        self.assertTrue(payload["overall_passed"])
        self.assertIsNone(payload["blocked_reason"])
        self.assertEqual(payload["metrics"]["robobus_bbox_plausible"], 1.0)
        self.assertEqual(payload["metrics"]["robobus_attached_lidar_count"], 5.0)

    def test_zero_width_wheels_are_diagnostic_because_carla_0_9_15_does_not_expose_width(self) -> None:
        probe = _load_probe()
        summary = {
            "checks": {
                "blueprint_found": True,
                "ego_actor_seen": True,
                "actor_type_match": True,
                "pose_height_plausible": True,
                "bbox_plausible": True,
                "wheel_count": True,
                "wheel_radius_match": True,
                "wheelbase_match": True,
                "front_tread_match": True,
                "rear_tread_match": True,
                "front_steer_limit_match": True,
                "rear_steer_limit_match": True,
                "attached_sensor_count": True,
                "attached_camera_count": True,
                "attached_lidar_count": True,
            },
            "actor": {"bbox_extent_m": {"x": 1.91, "y": 0.955, "z": 1.1045}},
            "wheel_geometry": {
                "wheelbase_cm": 302.0,
                "front_tread_cm": 161.0,
                "rear_tread_cm": 161.0,
            },
            "wheels": [
                {"width_cm": 0.0, "tire_friction": 0.0},
                {"width_cm": 0.0, "tire_friction": 0.0},
                {"width_cm": 0.0, "tire_friction": 0.0},
                {"width_cm": 0.0, "tire_friction": 0.0},
            ],
            "attached_sensor_count": 13,
            "attached_camera_count": 6,
            "attached_lidar_count": 5,
        }

        payload = probe._payload_from_summary(SimpleNamespace(profile="robobus117th_vehicle_blueprint"), summary)

        self.assertTrue(payload["overall_passed"])
        self.assertIsNone(payload["blocked_reason"])
        self.assertEqual(payload["metrics"]["robobus_min_wheel_width_cm"], 0.0)

    def test_write_artifacts_uses_metric_probe_contract(self) -> None:
        probe = _load_probe()
        payload = {
            "overall_passed": False,
            "blocked_reason": "failed_checks:bbox_plausible",
            "metrics": {"robobus_bbox_plausible": 0.0},
            "summary": {"checks": {"bbox_plausible": False}},
        }
        with tempfile.TemporaryDirectory() as tempdir:
            outputs = probe.write_artifacts(Path(tempdir), payload)
            artifact = Path(outputs["artifact"])
            summary = Path(outputs["summary_path"])

            self.assertIn("metric_probe_robobus_vehicle_blueprint_", str(artifact.parent))
            self.assertTrue(artifact.exists())
            self.assertTrue(summary.exists())
            saved = json.loads(artifact.read_text())
            self.assertEqual(saved["metrics"]["robobus_bbox_plausible"], 0.0)


if __name__ == "__main__":
    unittest.main()
