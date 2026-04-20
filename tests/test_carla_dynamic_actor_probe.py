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


if __name__ == "__main__":
    unittest.main()
