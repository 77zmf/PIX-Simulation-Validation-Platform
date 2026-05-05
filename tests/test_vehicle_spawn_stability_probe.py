from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_probe():
    path = REPO_ROOT / "ops" / "runtime_probes" / "carla_vehicle_spawn_stability_probe.py"
    spec = importlib.util.spec_from_file_location("carla_vehicle_spawn_stability_probe", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class VehicleSpawnStabilityProbeTests(unittest.TestCase):
    def test_payload_passes_when_one_variant_is_driveable(self) -> None:
        probe = _load_probe()
        args = SimpleNamespace(profile="robobus117th_qiyu_spawn_stability")
        summary = {
            "blueprint_found": True,
            "passed": True,
            "checks": {
                "blueprint_found": True,
                "spawned": True,
                "stable_variant_available": True,
                "driveable_variant_available": True,
            },
            "variants": [
                {
                    "spawned": True,
                    "stable": True,
                    "driveable": True,
                    "max_abs_pitch_deg": 0.2,
                    "max_abs_roll_deg": 0.3,
                    "min_z_m": -2.6,
                    "max_speed_mps": 2.5,
                    "delta_xy_m": 3.0,
                }
            ],
        }

        payload = probe._payload_from_summary(args, summary)

        self.assertTrue(payload["overall_passed"])
        self.assertIsNone(payload["blocked_reason"])
        self.assertEqual(payload["metrics"]["robobus_qiyu_spawn_stability_passed"], 1.0)
        self.assertEqual(payload["metrics"]["robobus_qiyu_spawn_driveable_count"], 1.0)

    def test_payload_fails_when_spawned_variant_flips(self) -> None:
        probe = _load_probe()
        args = SimpleNamespace(profile="robobus117th_qiyu_spawn_stability")
        summary = {
            "blueprint_found": True,
            "passed": False,
            "checks": {
                "blueprint_found": True,
                "spawned": True,
                "stable_variant_available": False,
                "driveable_variant_available": False,
            },
            "variants": [
                {
                    "spawned": True,
                    "stable": False,
                    "driveable": False,
                    "max_abs_pitch_deg": 75.0,
                    "max_abs_roll_deg": 179.0,
                    "min_z_m": -1.6,
                    "max_speed_mps": 5.3,
                    "delta_xy_m": 5.5,
                }
            ],
        }

        payload = probe._payload_from_summary(args, summary)

        self.assertFalse(payload["overall_passed"])
        self.assertIn("stable_variant_available", payload["blocked_reason"])
        self.assertEqual(payload["metrics"]["robobus_qiyu_spawn_stability_passed"], 0.0)
        self.assertEqual(payload["metrics"]["robobus_qiyu_spawn_stable_count"], 0.0)
        self.assertEqual(payload["metrics"]["robobus_qiyu_spawn_best_max_abs_roll_deg"], 179.0)

    def test_write_artifacts_uses_metric_probe_contract(self) -> None:
        probe = _load_probe()
        payload = {
            "overall_passed": False,
            "blocked_reason": "failed_checks:stable_variant_available",
            "metrics": {"robobus_qiyu_spawn_stability_passed": 0.0},
            "summary": {"checks": {"stable_variant_available": False}},
        }
        with tempfile.TemporaryDirectory() as tempdir:
            outputs = probe.write_artifacts(Path(tempdir), payload)
            artifact = Path(outputs["artifact"])
            summary = Path(outputs["summary_path"])

            self.assertIn("metric_probe_robobus_qiyu_spawn_stability_", str(artifact.parent))
            self.assertTrue(artifact.exists())
            self.assertTrue(summary.exists())
            saved = json.loads(artifact.read_text())
            self.assertEqual(saved["metrics"]["robobus_qiyu_spawn_stability_passed"], 0.0)


if __name__ == "__main__":
    unittest.main()
