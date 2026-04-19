from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.config import load_yaml
from simctl.evaluation import load_kpi_gate
from simctl.profiles import load_algorithm_profile
from simctl.scenarios import load_scenario


class ResearchConfigTests(unittest.TestCase):
    def test_planning_control_public_road_scenario_loads(self) -> None:
        scenario = load_scenario("scenarios/l2/planning_control_public_road_merge_regression.yaml", REPO_ROOT)
        self.assertEqual(scenario.algorithm_profile, "planning_control_research")
        self.assertEqual(scenario.kpi_gate, "planning_control_research_gate")

    def test_planning_control_merge_scenario_uses_executable_actor_bridge_gate(self) -> None:
        scenario = load_scenario("scenarios/l2/planning_control_merge_regression.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l2" / "planning_control_merge_regression.yaml")
        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "planning_control_actor_bridge_regression")
        self.assertIn("--kind l2_merge", payload["metadata"]["validation_command"])
        self.assertEqual(payload["execution"]["stable_runtime"]["carla_actor_object_bridge_enabled"], "true")

    def test_multi_actor_scenario_uses_actor_bridge_gate(self) -> None:
        scenario = load_scenario("scenarios/l2/planning_control_multi_actor_cut_in_lead_brake.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l2" / "planning_control_multi_actor_cut_in_lead_brake.yaml")
        gate = load_kpi_gate("planning_control_multi_actor_regression", REPO_ROOT)
        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "planning_control_multi_actor_regression")
        self.assertIn("--kind l2_multi_actor_cut_in_lead_brake", payload["metadata"]["validation_command"])
        self.assertEqual(payload["traffic_profile"]["vehicles"], 3)
        stable_runtime = payload["execution"]["stable_runtime"]
        self.assertEqual(stable_runtime["carla_vehicle_type"], "vehicle.pixmoving.robobus")
        self.assertEqual(stable_runtime["carla_root"], "/home/pixmoving/CARLA_0.9.15")
        self.assertEqual(stable_runtime["carla_spawn_point"], "229.7817,2.0201,-0.5,0,0,0")
        self.assertIn("actor_count_observed", gate.metrics)
        self.assertIn("yield_response_count", gate.metrics)

    def test_perception_public_road_gate_contains_planner_metrics(self) -> None:
        gate = load_kpi_gate("perception_bevfusion_public_road_gate", REPO_ROOT)
        self.assertIn("perception_readiness", gate.metrics)
        self.assertIn("lane_topology_recall", gate.metrics)
        self.assertIn("planner_interface_disagreement_rate", gate.metrics)

    def test_perception_occlusion_scenario_requires_real_metrics_artifact(self) -> None:
        scenario = load_scenario("scenarios/l2/perception_bevfusion_public_road_occlusion.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l2" / "perception_bevfusion_public_road_occlusion.yaml")
        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "perception_bevfusion_public_road")
        self.assertEqual(scenario.kpi_gate, "perception_bevfusion_public_road_gate")
        self.assertIn("--require-metrics", payload["metadata"]["validation_command"])
        self.assertEqual(
            payload["metadata"]["metrics_artifact"],
            "runtime_verification/perception_metrics/bevfusion_public_road_metrics.json",
        )

    def test_bevfusion_public_road_profile_freezes_shadow_contract(self) -> None:
        profile = load_algorithm_profile("perception_bevfusion_public_road", REPO_ROOT)
        self.assertEqual(profile.payload["contract_version"], "2026q2-shadow-v1")
        self.assertEqual(profile.payload["integration_boundary"], "production_perception_baseline_and_shadow_input")
        contract = profile.payload["planner_interface_contract"]
        self.assertEqual(contract["target_frame"], "map")
        self.assertEqual(contract["timestamp"]["max_skew_ms"], 100)
        self.assertIn("object_queries", contract["channels"])
        self.assertIn("ego_history", contract["channels"])

    def test_uniad_shadow_scenario_loads(self) -> None:
        scenario = load_scenario("scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml", REPO_ROOT)
        self.assertEqual(scenario.stack, "stable")
        self.assertEqual(scenario.sensor_profile, "carla0915_high_fidelity")
        self.assertEqual(scenario.algorithm_profile, "e2e_bevfusion_uniad_shadow")
        self.assertEqual(scenario.kpi_gate, "e2e_bevfusion_uniad_shadow_gate")

    def test_uniad_shadow_profile_declares_shared_contract(self) -> None:
        profile = load_algorithm_profile("e2e_bevfusion_uniad_shadow", REPO_ROOT)
        contract = profile.payload["interface_contract"]
        self.assertEqual(contract["contract_version"], "2026q2-shadow-v1")
        self.assertEqual(contract["comparison_role"], "primary_shadow_reference")
        self.assertTrue(contract["minimal_inputs"]["object_queries"]["required"])
        self.assertTrue(contract["minimal_inputs"]["route_reference"]["required"])
        self.assertTrue(contract["outputs"]["shadow_control"]["observation_only"])

    def test_vadv2_shadow_gate_contains_uncertainty_metric(self) -> None:
        gate = load_kpi_gate("e2e_bevfusion_vadv2_shadow_gate", REPO_ROOT)
        self.assertIn("shadow_uncertainty_coverage", gate.metrics)
        self.assertIn("cut_in_yield_failures", gate.metrics)

    def test_vadv2_shadow_profile_declares_vectorized_scene_requirement(self) -> None:
        profile = load_algorithm_profile("e2e_bevfusion_vadv2_shadow", REPO_ROOT)
        contract = profile.payload["interface_contract"]
        self.assertEqual(contract["contract_version"], "2026q2-shadow-v1")
        self.assertEqual(contract["comparison_role"], "uncertainty_aware_control_line")
        self.assertTrue(contract["minimal_inputs"]["vectorized_scene_tokens"]["required"])
        self.assertEqual(contract["minimal_inputs"]["vectorized_scene_tokens"]["source"], "vadv2_scene_tokens")
        self.assertTrue(contract["outputs"]["shadow_control"]["observation_only"])

    def test_uniad_and_vadv2_shadow_gates_share_core_metrics(self) -> None:
        uniad_gate = load_kpi_gate("e2e_bevfusion_uniad_shadow_gate", REPO_ROOT)
        vadv2_gate = load_kpi_gate("e2e_bevfusion_vadv2_shadow_gate", REPO_ROOT)
        shared_metrics = {
            "route_completion",
            "collision_count",
            "trajectory_divergence_m",
            "min_ttc_sec",
            "planner_disengagement_triggers",
        }
        self.assertTrue(shared_metrics.issubset(uniad_gate.metrics))
        self.assertTrue(shared_metrics.issubset(vadv2_gate.metrics))

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
