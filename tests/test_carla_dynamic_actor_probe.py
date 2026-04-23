from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = REPO_ROOT / "ops" / "runtime_probes" / "carla_dynamic_actor_probe.py"

spec = importlib.util.spec_from_file_location("carla_dynamic_actor_probe", PROBE_PATH)
carla_dynamic_actor_probe = importlib.util.module_from_spec(spec)
sys.modules["carla_dynamic_actor_probe"] = carla_dynamic_actor_probe
assert spec.loader is not None
spec.loader.exec_module(carla_dynamic_actor_probe)


class CarlaDynamicActorProbeTests(unittest.TestCase):
    def test_overview_spectator_centers_ego_and_targets(self) -> None:
        params = carla_dynamic_actor_probe.spectator_transform_params(
            "overview",
            {"x": 230.0, "y": 2.0, "z": 0.1, "yaw": 0.0},
            [
                {"x": 286.0, "y": 2.0},
                {"x": 260.0, "y": 6.0},
            ],
        )

        self.assertIsNotNone(params)
        assert params is not None
        self.assertAlmostEqual(params["x"], (230.0 + 286.0 + 260.0) / 3.0)
        self.assertAlmostEqual(params["y"], (2.0 + 2.0 + 6.0) / 3.0)
        self.assertEqual(params["pitch"], -90.0)
        self.assertGreaterEqual(params["z"], 38.0)

    def test_ego_chase_spectator_tracks_behind_ego(self) -> None:
        params = carla_dynamic_actor_probe.spectator_transform_params(
            "ego_chase",
            {"x": 230.0, "y": 2.0, "z": 0.1, "yaw": 0.0},
            [],
        )

        self.assertIsNotNone(params)
        assert params is not None
        self.assertAlmostEqual(params["x"], 216.0)
        self.assertAlmostEqual(params["y"], 2.0)
        self.assertAlmostEqual(params["z"], 7.1)
        self.assertEqual(params["pitch"], -22.0)

    def test_l3_occluded_pedestrian_probe_uses_walker_and_occluder(self) -> None:
        config = carla_dynamic_actor_probe.PROBES["l3_occluded_pedestrian"]

        self.assertEqual(config.target_type, "walker.pedestrian.0001")
        actor_types = [actor.target_type for actor in config.actors]
        self.assertIn("vehicle.audi.tt", actor_types)
        self.assertIn("walker.pedestrian.0001", actor_types)
        self.assertEqual(config.safe_ttc_sec, 1.8)
        self.assertEqual(config.min_actor_observed_count, 1)
        occluders = [actor for actor in config.actors if actor.name == "occluding_vehicle"]
        self.assertEqual(len(occluders), 1)
        self.assertFalse(occluders[0].perception_visible)

    def test_l3_dummy_injection_selects_visible_pedestrian(self) -> None:
        config = carla_dynamic_actor_probe.PROBES["l3_occluded_pedestrian"]
        injection_actor = carla_dynamic_actor_probe.dummy_injection_actor(config.actors)
        profile = carla_dynamic_actor_probe.dummy_object_profile("walker.pedestrian.0001")

        self.assertIsNotNone(injection_actor)
        assert injection_actor is not None
        self.assertEqual(injection_actor.name, "crossing_pedestrian")
        self.assertEqual(profile["classification"], "PEDESTRIAN")
        self.assertEqual(profile["shape"], "CYLINDER")
        self.assertEqual(profile["dimensions"], {"x": 0.6, "y": 0.6, "z": 2.0})

    def test_l3_expanded_variants_keep_one_visible_pedestrian(self) -> None:
        for kind in (
            "l3_occluded_pedestrian_close_yield",
            "l3_occluded_pedestrian_double_occluder",
        ):
            with self.subTest(kind=kind):
                config = carla_dynamic_actor_probe.PROBES[kind]
                visible = [actor for actor in config.actors if actor.perception_visible]
                occluders = [actor for actor in config.actors if not actor.perception_visible]

                self.assertEqual(len(visible), 1)
                self.assertTrue(visible[0].target_type.startswith("walker.pedestrian."))
                self.assertGreaterEqual(len(occluders), 1)
                self.assertEqual(config.min_actor_observed_count, 1)
                self.assertEqual(config.safe_ttc_sec, 1.8)


if __name__ == "__main__":
    unittest.main()
