from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.evaluation import load_kpi_gate
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

    def test_uniad_shadow_scenario_loads(self) -> None:
        scenario = load_scenario("scenarios/ue5/e2e_bevfusion_uniad_unprotected_left.yaml", REPO_ROOT)
        self.assertEqual(scenario.algorithm_profile, "e2e_bevfusion_uniad_shadow")
        self.assertEqual(scenario.kpi_gate, "e2e_bevfusion_uniad_shadow_gate")

    def test_vadv2_shadow_gate_contains_uncertainty_metric(self) -> None:
        gate = load_kpi_gate("e2e_bevfusion_vadv2_shadow_gate", REPO_ROOT)
        self.assertIn("shadow_uncertainty_coverage", gate.metrics)
        self.assertIn("cut_in_yield_failures", gate.metrics)

    def test_reconstruction_public_road_scenario_uses_capture_profile(self) -> None:
        scenario = load_scenario("scenarios/l2/reconstruction_public_road_map_refresh.yaml", REPO_ROOT)
        self.assertEqual(scenario.sensor_profile, "reconstruction_capture")
        self.assertEqual(scenario.algorithm_profile, "reconstruction_public_road_map_refresh")


if __name__ == "__main__":
    unittest.main()
