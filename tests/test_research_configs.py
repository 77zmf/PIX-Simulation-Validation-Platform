from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.evaluation import load_kpi_gate
from simctl.scenarios import load_scenario


class ResearchConfigTests(unittest.TestCase):
    def test_planning_control_research_scenario_loads(self) -> None:
        scenario = load_scenario("scenarios/l2/planning_control_merge_regression.yaml", REPO_ROOT)
        self.assertEqual(scenario.algorithm_profile, "planning_control_research")
        self.assertEqual(scenario.kpi_gate, "planning_control_research_gate")

    def test_perception_research_gate_contains_shadow_metrics(self) -> None:
        gate = load_kpi_gate("perception_bev_shadow_gate", REPO_ROOT)
        self.assertIn("detection_recall", gate.metrics)
        self.assertIn("vad_shadow_disagreement_rate", gate.metrics)

    def test_reconstruction_scenario_uses_capture_profile(self) -> None:
        scenario = load_scenario("scenarios/l2/reconstruction_site_proxy_refresh.yaml", REPO_ROOT)
        self.assertEqual(scenario.sensor_profile, "reconstruction_capture")
        self.assertEqual(scenario.asset_bundle, "site_gy_qyhx_gsh20260302")


if __name__ == "__main__":
    unittest.main()
