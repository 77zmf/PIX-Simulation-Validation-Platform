from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeActor:
    def __init__(self, type_id: str = "vehicle.pixmoving.robobus", role_name: str = "ego_vehicle") -> None:
        self.type_id = type_id
        self.attributes = {"role_name": role_name}


class _FakeActorList(list):
    def filter(self, pattern: str):
        return self


class _FakeSettings:
    synchronous_mode = True


class _FakeWorld:
    def __init__(self) -> None:
        self.ticks = 0

    def get_actors(self):
        if self.ticks <= 0:
            return _FakeActorList([])
        return _FakeActorList([_FakeActor()])

    def get_settings(self):
        return _FakeSettings()

    def tick(self):
        self.ticks += 1


def _load_probe():
    path = REPO_ROOT / "ops" / "runtime_probes" / "carla_vehicle_dynamics_probe.py"
    spec = importlib.util.spec_from_file_location("carla_vehicle_dynamics_probe", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class VehicleDynamicsProbeTests(unittest.TestCase):
    def test_payload_passes_when_direct_throttle_moves_vehicle(self) -> None:
        probe = _load_probe()
        summary = {
            "vehicle_count_before": 1,
            "vehicle_count_after": 1,
            "direct_throttle_delta_m": 8.5,
            "direct_throttle_max_speed_mps": 3.4,
            "direct_throttle_max_speed_kph": 12.24,
            "final_speed_mps": 0.2,
            "checks": {
                "ego_actor_seen": True,
                "actor_type_match": True,
                "actor_persisted": True,
                "moved_enough": True,
                "speed_enough": True,
                "direct_throttle_passed": True,
            },
        }

        payload = probe._payload_from_summary(SimpleNamespace(profile="robobus117th_vehicle_dynamics"), summary)

        self.assertTrue(payload["overall_passed"])
        self.assertIsNone(payload["blocked_reason"])
        self.assertEqual(payload["metrics"]["robobus_dynamics_direct_throttle_passed"], 1.0)
        self.assertEqual(payload["metrics"]["robobus_dynamics_direct_throttle_delta_m"], 8.5)
        self.assertEqual(payload["metrics"]["robobus_dynamics_direct_throttle_max_speed_kph"], 12.24)

    def test_payload_fails_when_actor_disappears_or_does_not_move(self) -> None:
        probe = _load_probe()
        summary = {
            "vehicle_count_before": 1,
            "vehicle_count_after": 0,
            "direct_throttle_delta_m": 0.0,
            "direct_throttle_max_speed_mps": 0.0,
            "checks": {
                "ego_actor_seen": True,
                "actor_type_match": True,
                "actor_persisted": False,
                "moved_enough": False,
                "speed_enough": False,
                "direct_throttle_passed": False,
            },
        }

        payload = probe._payload_from_summary(SimpleNamespace(profile="robobus117th_vehicle_dynamics"), summary)

        self.assertFalse(payload["overall_passed"])
        self.assertIn("actor_persisted", payload["blocked_reason"])
        self.assertIn("moved_enough", payload["blocked_reason"])
        self.assertEqual(payload["metrics"]["robobus_dynamics_actor_persisted"], 0.0)
        self.assertEqual(payload["metrics"]["robobus_dynamics_direct_throttle_passed"], 0.0)

    def test_wait_for_ego_ticks_synchronous_world_before_failing_actor_lookup(self) -> None:
        probe = _load_probe()
        world = _FakeWorld()
        args = SimpleNamespace(
            actor_id="vehicle.pixmoving.robobus",
            ego_role_name="ego_vehicle",
            actor_wait_sec=1.0,
            sample_period_sec=0.05,
        )

        actor, vehicle_count, attempts = probe._wait_for_ego(world, args)

        self.assertIsNotNone(actor)
        self.assertEqual(vehicle_count, 1)
        self.assertGreaterEqual(attempts, 2)
        self.assertGreaterEqual(world.ticks, 1)

    def test_write_artifacts_uses_metric_probe_contract(self) -> None:
        probe = _load_probe()
        payload = {
            "overall_passed": False,
            "blocked_reason": "failed_checks:moved_enough",
            "metrics": {"robobus_dynamics_direct_throttle_passed": 0.0},
            "summary": {"checks": {"moved_enough": False}},
        }
        with tempfile.TemporaryDirectory() as tempdir:
            outputs = probe.write_artifacts(Path(tempdir), payload)
            artifact = Path(outputs["artifact"])
            summary = Path(outputs["summary_path"])

            self.assertIn("metric_probe_robobus_vehicle_dynamics_", str(artifact.parent))
            self.assertTrue(artifact.exists())
            self.assertTrue(summary.exists())
            saved = json.loads(artifact.read_text())
            self.assertEqual(saved["metrics"]["robobus_dynamics_direct_throttle_passed"], 0.0)


if __name__ == "__main__":
    unittest.main()
