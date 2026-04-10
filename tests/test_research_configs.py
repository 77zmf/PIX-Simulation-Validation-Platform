from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.evaluation import load_kpi_gate
from simctl.profiles import load_algorithm_profile
from simctl.scenarios import load_scenario


class ResearchConfigTests(unittest.TestCase):
    def test_planning_control_public_road_scenario_loads(self) -> None:
        scenario = load_scenario("scenarios/l2/planning_control_public_road_merge_regression.yaml", REPO_ROOT)
        self.assertEqual(scenario.algorithm_profile, "planning_control_research")
        self.assertEqual(scenario.kpi_gate, "planning_control_research_gate")

    def test_perception_public_road_gate_contains_planner_metrics(self) -> None:
        gate = load_kpi_gate("perception_bevfusion_public_road_gate", REPO_ROOT)
        self.assertIn("lane_topology_recall", gate.metrics)
        self.assertIn("planner_interface_disagreement_rate", gate.metrics)

    def test_perception_bevfusion_profile_declares_shadow_contract(self) -> None:
        profile = load_algorithm_profile("perception_bevfusion_public_road", REPO_ROOT)
        self.assertEqual(profile.payload["contract_version"], "2026q2-shadow-v1")
        self.assertFalse(profile.payload["integration_boundary"]["control_takeover"])
        self.assertIn("lane_graph_features", profile.payload["planner_interface_contract"]["required_fields"])

    def test_uniad_shadow_scenario_loads(self) -> None:
        scenario = load_scenario("scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml", REPO_ROOT)
        self.assertEqual(scenario.stack, "stable")
        self.assertEqual(scenario.sensor_profile, "carla0915_high_fidelity")
        self.assertEqual(scenario.algorithm_profile, "e2e_bevfusion_uniad_shadow")
        self.assertEqual(scenario.kpi_gate, "e2e_bevfusion_uniad_shadow_gate")

    def test_uniad_shadow_profile_is_observation_only(self) -> None:
        profile = load_algorithm_profile("e2e_bevfusion_uniad_shadow", REPO_ROOT)
        self.assertEqual(profile.payload["interface_contract"]["mode"], "observation_only")
        self.assertFalse(profile.payload["interface_contract"]["control_takeover"])
        self.assertIn("bevfusion_occupancy", profile.payload["interface_contract"]["required_inputs"])

    def test_vadv2_shadow_gate_contains_uncertainty_metric(self) -> None:
        gate = load_kpi_gate("e2e_bevfusion_vadv2_shadow_gate", REPO_ROOT)
        self.assertIn("shadow_uncertainty_coverage", gate.metrics)
        self.assertIn("cut_in_yield_failures", gate.metrics)

    def test_vadv2_shadow_profile_declares_vectorized_scene_contract(self) -> None:
        profile = load_algorithm_profile("e2e_bevfusion_vadv2_shadow", REPO_ROOT)
        self.assertEqual(profile.payload["interface_contract"]["mode"], "observation_only")
        self.assertIn("vadv2_scene_tokens", profile.payload["interface_contract"]["additional_representation"])
        self.assertEqual(profile.payload["outputs"]["vectorized_scene"], "vadv2_scene_tokens")

    def test_reconstruction_public_road_scenario_uses_capture_profile(self) -> None:
        scenario = load_scenario("scenarios/l2/reconstruction_public_road_map_refresh.yaml", REPO_ROOT)
        self.assertEqual(scenario.sensor_profile, "reconstruction_capture")
        self.assertEqual(scenario.algorithm_profile, "reconstruction_public_road_map_refresh")

    def test_static_gaussian_reconstruction_scenario_loads(self) -> None:
        scenario = load_scenario("scenarios/l2/reconstruction_static_public_road_gaussian_base.yaml", REPO_ROOT)
        self.assertEqual(scenario.sensor_profile, "reconstruction_capture")
        self.assertEqual(scenario.algorithm_profile, "reconstruction_static_public_road_gaussians")
        self.assertEqual(scenario.kpi_gate, "reconstruction_static_public_road_gaussians_gate")

    def test_dynamic_gaussian_reconstruction_gate_contains_temporal_metrics(self) -> None:
        gate = load_kpi_gate("reconstruction_dynamic_public_road_gaussians_gate", REPO_ROOT)
        self.assertIn("temporal_consistency_score", gate.metrics)
        self.assertIn("ghosting_rate", gate.metrics)


if __name__ == "__main__":
    unittest.main()
