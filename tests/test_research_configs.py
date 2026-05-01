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
    def test_robobus_vehicle_blueprint_acceptance_scenario_uses_strict_geometry_gate(self) -> None:
        scenario = load_scenario("scenarios/l0/robobus117th_vehicle_blueprint_acceptance.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l0" / "robobus117th_vehicle_blueprint_acceptance.yaml")
        gate = load_kpi_gate("robobus117th_vehicle_blueprint_acceptance", REPO_ROOT)

        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "robobus117th_vehicle_blueprint_acceptance")
        self.assertIn("carla_vehicle_blueprint_probe.py", payload["metadata"]["validation_command"])
        self.assertIn("--min-bbox-extent-x-m 1.0", payload["metadata"]["validation_command"])
        self.assertEqual(payload["execution"]["stable_runtime"]["carla_vehicle_type"], "vehicle.pixmoving.robobus")
        self.assertIn("robobus_bbox_plausible", gate.metrics)
        self.assertIn("robobus_attached_lidar_count", gate.metrics)

    def test_robobus_vehicle_dynamics_scenario_uses_direct_throttle_gate(self) -> None:
        scenario = load_scenario("scenarios/l0/robobus117th_vehicle_dynamics_acceptance.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l0" / "robobus117th_vehicle_dynamics_acceptance.yaml")
        gate = load_kpi_gate("robobus117th_vehicle_dynamics_acceptance", REPO_ROOT)

        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "robobus117th_vehicle_dynamics_acceptance")
        self.assertIn("carla_vehicle_dynamics_probe.py", payload["metadata"]["validation_command"])
        self.assertIn("--reset-pose", payload["metadata"]["validation_command"])
        self.assertIn("robobus_dynamics_direct_throttle_passed", gate.metrics)
        self.assertIn("robobus_dynamics_actor_persisted", gate.metrics)

    def test_speed40_scenario_uses_target_speed_gate(self) -> None:
        scenario = load_scenario("scenarios/l1/robobus117th_town01_speed40_probe.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l1" / "robobus117th_town01_speed40_probe.yaml")
        gate = load_kpi_gate("planning_control_speed40_probe", REPO_ROOT)

        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "planning_control_speed40_probe")
        self.assertLess(payload["ego_init"]["pose"]["x"], payload["goal"]["pose"]["x"])
        self.assertGreaterEqual(payload["goal"]["pose"]["x"] - payload["ego_init"]["pose"]["x"], 190.0)
        self.assertAlmostEqual(payload["ego_init"]["pose"]["y"], -133.465, places=3)
        self.assertTrue(
            payload["execution"]["stable_runtime"]["carla_spawn_point"].startswith("120.0000,133.4650,")
        )
        self.assertIn("--target-speed-mps 11.111111", payload["metadata"]["validation_command"])
        self.assertIn("target_speed_reached", gate.metrics)
        self.assertIn("max_speed_mps", gate.metrics)

    def test_follow_lane_scenario_disables_goal_modification_and_gates_lane_centering(self) -> None:
        scenario = load_scenario("scenarios/l1/regression_follow_lane.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l1" / "regression_follow_lane.yaml")
        gate = load_kpi_gate("planning_control_follow_lane_regression", REPO_ROOT)

        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "planning_control_follow_lane_regression")
        validation_command = payload["metadata"]["validation_command"]
        self.assertIn("--disable-goal-modification", validation_command)
        self.assertIn("--goal-tolerance-m 0.8", validation_command)
        self.assertLessEqual(gate.metrics["lateral_error_m"]["value"], 0.50)
        self.assertLessEqual(gate.metrics["route_goal_lateral_error_m"]["value"], 0.50)
        self.assertEqual(gate.metrics["longitudinal_error_m"]["value"], 0.8)

    def test_sumo_town01_smoke_scenario_requires_visual_capture_evidence(self) -> None:
        scenario = load_scenario("scenarios/l1/sumo_town01_traffic_smoke.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l1" / "sumo_town01_traffic_smoke.yaml")
        gate = load_kpi_gate("sumo_public_road_smoke", REPO_ROOT)

        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "sumo_public_road_smoke")
        self.assertIn("ops/runtime_probes/carla_actor_visual_capture.py", payload["metadata"]["source_assets"])
        self.assertIn("carla_actor_visual_capture.py", payload["metadata"]["validation_command"])
        self.assertIn("--npc-role-name sumo_driver", payload["metadata"]["validation_command"])
        self.assertIn("--min-captures 3", payload["metadata"]["validation_command"])
        self.assertIn("--profile robobus117th_presence_smoke", payload["metadata"]["validation_command"])
        self.assertEqual(payload["execution"]["stable_runtime"]["sumo_carla_client_timeout_sec"], "60.0")
        self.assertIn("carla_actor_visual_ego_seen", gate.metrics)
        self.assertIn("carla_actor_visual_npc_count", gate.metrics)
        self.assertIn("carla_actor_visual_capture_count", gate.metrics)

    def test_sumo_town01_dense_traffic_scenario_requires_high_actor_counts(self) -> None:
        scenario = load_scenario("scenarios/l2/sumo_town01_dense_traffic.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l2" / "sumo_town01_dense_traffic.yaml")
        gate = load_kpi_gate("sumo_dense_traffic", REPO_ROOT)
        campaign = load_yaml(REPO_ROOT / "ops" / "test_campaigns" / "stable_sumo_traffic.yaml")

        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "sumo_dense_traffic")
        self.assertGreaterEqual(payload["traffic_profile"]["vehicles"], 50)
        self.assertIn("--profile town01_sumo_dense", payload["metadata"]["validation_command"])
        self.assertIn("--actor-source carla-rpc", payload["metadata"]["validation_command"])
        self.assertIn("--min-actors 12", payload["metadata"]["validation_command"])
        self.assertIn("--min-npcs 8", payload["metadata"]["validation_command"])
        self.assertIn("--max-npcs 12", payload["metadata"]["validation_command"])
        self.assertEqual(payload["execution"]["stable_runtime"]["sumo_min_actor_count"], "12")
        self.assertEqual(gate.metrics["sumo_actor_count"]["value"], 12.0)
        self.assertEqual(gate.metrics["carla_actor_visual_npc_count"]["value"], 8.0)
        self.assertIn(
            "stable_l2_sumo_town01_dense_traffic",
            [item["id"] for item in campaign["scenarios"]],
        )

    def test_sumo_dense_route_follow_scenario_joins_planning_control_bughunt(self) -> None:
        scenario = load_scenario("scenarios/l2/sumo_town01_dense_route_follow.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l2" / "sumo_town01_dense_route_follow.yaml")
        gate = load_kpi_gate("sumo_dense_route_follow_bughunt", REPO_ROOT)
        campaign = load_yaml(REPO_ROOT / "ops" / "test_campaigns" / "stable_planning_control_bughunt.yaml")

        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "sumo_dense_route_follow_bughunt")
        self.assertEqual(payload["ego_init"]["pose"]["x"], 250.0)
        self.assertTrue(
            payload["execution"]["stable_runtime"]["carla_spawn_point"].startswith("250.0000,")
        )
        self.assertEqual(payload["traffic_profile"]["mode"], "sumo_dense_route_follow_actor_bridge")
        self.assertGreaterEqual(payload["traffic_profile"]["vehicles"], 50)
        validation_command = payload["metadata"]["validation_command"]
        self.assertIn("sumo_cosim_probe.py", validation_command)
        self.assertIn("--actor-source carla-rpc", validation_command)
        self.assertIn("--min-actors 12", validation_command)
        self.assertIn("carla_actor_visual_capture.py", validation_command)
        self.assertIn("--min-npcs 8", validation_command)
        self.assertIn("carla_sensor_topic_probe.py", validation_command)
        self.assertIn("carla_closed_loop_route_probe.py", validation_command)
        self.assertIn("--max-duration-sec 180", validation_command)
        self.assertIn("--ego-start-clear-radius-m 45", validation_command)
        self.assertIn("--skip-ego-reset", validation_command)
        self.assertIn("--camera-video-output", validation_command)
        self.assertEqual(payload["execution"]["stable_runtime"]["sumo_carla_client_timeout_sec"], "180.0")
        self.assertEqual(payload["execution"]["stable_runtime"]["carla_bridge_timeout"], "180")
        self.assertIn("route_completion", gate.metrics)
        self.assertNotIn("collision_count", gate.metrics)
        self.assertNotIn("min_ttc_sec", gate.metrics)
        self.assertIn("sumo_actor_count", gate.metrics)
        self.assertIn("carla_actor_visual_npc_count", gate.metrics)
        self.assertIn(
            "stable_l2_sumo_dense_route_follow",
            [item["id"] for item in campaign["scenarios"]],
        )

    def test_planning_control_public_road_scenario_uses_stable_actor_bridge_gate(self) -> None:
        scenario = load_scenario("scenarios/l2/planning_control_public_road_merge_regression.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l2" / "planning_control_public_road_merge_regression.yaml")
        gate = load_kpi_gate("planning_control_multi_actor_regression", REPO_ROOT)
        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "planning_control_multi_actor_regression")
        self.assertIn("--kind l2_multi_actor_cut_in_lead_brake", payload["metadata"]["validation_command"])
        self.assertEqual(payload["traffic_profile"]["vehicles"], 3)
        stable_runtime = payload["execution"]["stable_runtime"]
        self.assertEqual(stable_runtime["carla_vehicle_type"], "vehicle.pixmoving.robobus")
        self.assertEqual(stable_runtime["carla_actor_object_bridge_enabled"], "true")
        self.assertIn("actor_count_observed", gate.metrics)

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

    def test_crosswalk_vru_yield_scenario_uses_executable_dummy_injection_gate(self) -> None:
        scenario = load_scenario("scenarios/l2/planning_control_crosswalk_vru_yield.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l2" / "planning_control_crosswalk_vru_yield.yaml")
        gate = load_kpi_gate("planning_control_crosswalk_vru_yield", REPO_ROOT)

        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "planning_control_crosswalk_vru_yield")
        self.assertIn("--kind l2_crosswalk_vru_yield", payload["metadata"]["validation_command"])
        self.assertIn("--perception-source dummy_injection", payload["metadata"]["validation_command"])
        self.assertEqual(payload["traffic_profile"]["pedestrians"], 1)
        self.assertEqual(payload["execution"]["stable_runtime"]["carla_actor_object_bridge_include_walkers"], "true")
        self.assertIn("yield_response_count", gate.metrics)

    def test_planning_control_p1_gap_drafts_define_blocked_contracts(self) -> None:
        for path, gate_id, blocker in (
            (
                "scenarios/l2/planning_control_unprotected_left_intersection_draft.yaml",
                "planning_control_unprotected_left_intersection",
                "blocked_on_route_manifest",
            ),
            (
                "scenarios/l2/planning_control_stop_line_red_light_draft.yaml",
                "planning_control_stop_line_red_light",
                "blocked_on_traffic_light_control",
            ),
        ):
            with self.subTest(path=path):
                scenario = load_scenario(path, REPO_ROOT)
                payload = load_yaml(REPO_ROOT / path)
                gate = load_kpi_gate(gate_id, REPO_ROOT)

                self.assertEqual(scenario.kpi_gate, gate_id)
                self.assertEqual(payload["metadata"]["draft_status"], blocker)
                self.assertIn("blocked:", payload["metadata"]["validation_command"])
                self.assertEqual(payload["execution"]["mode"], "external")
                self.assertIn("route_completion", gate.metrics)

    def test_roadtest_planning_failcases_are_indexed_as_simulation_drafts(self) -> None:
        manifest = load_yaml(REPO_ROOT / "assets" / "manifests" / "planning_road_test_failcases_202604.yaml")
        gate = load_kpi_gate("planning_control_trajectory_stability_replay", REPO_ROOT)
        scenario_paths = (
            "scenarios/l2/planning_control_roadtest_trajectory_jump_replay_draft.yaml",
            "scenarios/l2/planning_control_roadtest_trajectory_dropout_replay_draft.yaml",
            "scenarios/l2/planning_control_roadtest_out_of_lane_brake_takeover_replay_draft.yaml",
        )

        self.assertEqual(manifest["asset_id"], "planning_road_test_failcases_202604")
        self.assertGreaterEqual(len(manifest["cases"]), 5)
        self.assertTrue(all(str(case["local_evidence_root"]).startswith("/Users/cyber/Documents/zmf_test-data") for case in manifest["cases"]))
        self.assertIn("planning_validator_invalid_count", gate.metrics)
        self.assertIn("trajectory_jump_max_m", gate.metrics)
        self.assertIn("trajectory_silence_sec", gate.metrics)

        for path in scenario_paths:
            with self.subTest(path=path):
                scenario = load_scenario(path, REPO_ROOT)
                payload = load_yaml(REPO_ROOT / path)
                self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
                self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
                self.assertEqual(scenario.kpi_gate, "planning_control_trajectory_stability_replay")
                self.assertEqual(payload["asset_bundle"], "planning_road_test_failcases_202604")
                self.assertIn("assets/manifests/planning_road_test_failcases_202604.yaml", payload["metadata"]["source_assets"])
                self.assertIn("planning_roadtest_replay_probe.py", payload["metadata"]["validation_command"])
                self.assertIn("--manifest assets/manifests/planning_road_test_failcases_202604.yaml", payload["metadata"]["validation_command"])
                self.assertEqual(payload["execution"]["mode"], "external")
                self.assertIn("road_test_replay", payload["labels"])

    def test_l3_occluded_pedestrian_scenario_uses_executable_dummy_injection_gate(self) -> None:
        scenario = load_scenario("scenarios/l3/stress_occluded_pedestrian.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l3" / "stress_occluded_pedestrian.yaml")
        gate = load_kpi_gate("planning_control_l3_occluded_pedestrian", REPO_ROOT)
        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "planning_control_l3_occluded_pedestrian")
        self.assertIn("--kind l3_occluded_pedestrian", payload["metadata"]["validation_command"])
        self.assertIn("--perception-source dummy_injection", payload["metadata"]["validation_command"])
        self.assertEqual(payload["traffic_profile"]["vehicles"], 1)
        self.assertEqual(payload["traffic_profile"]["pedestrians"], 1)
        stable_runtime = payload["execution"]["stable_runtime"]
        self.assertEqual(stable_runtime["carla_vehicle_type"], "vehicle.pixmoving.robobus")
        self.assertEqual(stable_runtime["carla_actor_object_bridge_enabled"], "true")
        self.assertEqual(stable_runtime["carla_actor_object_bridge_include_walkers"], "true")
        self.assertIn("actor_count_observed", gate.metrics)

    def test_l3_expanded_occlusion_scenarios_use_executable_dummy_injection_gate(self) -> None:
        for path, probe_kind in (
            ("scenarios/l3/occluded_pedestrian_close_yield.yaml", "l3_occluded_pedestrian_close_yield"),
            ("scenarios/l3/occluded_pedestrian_double_occluder.yaml", "l3_occluded_pedestrian_double_occluder"),
        ):
            with self.subTest(path=path):
                scenario = load_scenario(path, REPO_ROOT)
                payload = load_yaml(REPO_ROOT / path)
                gate = load_kpi_gate("planning_control_l3_occluded_pedestrian", REPO_ROOT)

                self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
                self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
                self.assertEqual(scenario.kpi_gate, "planning_control_l3_occluded_pedestrian")
                self.assertIn(f"--kind {probe_kind}", payload["metadata"]["validation_command"])
                self.assertIn("--perception-source dummy_injection", payload["metadata"]["validation_command"])
                self.assertGreaterEqual(payload["traffic_profile"]["pedestrians"], 1)
                self.assertEqual(payload["execution"]["stable_runtime"]["carla_vehicle_type"], "vehicle.pixmoving.robobus")
                self.assertEqual(payload["execution"]["stable_runtime"]["carla_actor_object_bridge_enabled"], "true")
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

    def test_lsx_gsh0302_reconstruction_scenario_uses_local_0302_bundle(self) -> None:
        scenario = load_scenario("scenarios/l2/reconstruction_lsx_gsh0302_map_refresh.yaml", REPO_ROOT)
        self.assertEqual(scenario.asset_bundle, "site_gy_qyhx_gsh20260302")
        self.assertEqual(scenario.sensor_profile, "reconstruction_capture")
        self.assertEqual(scenario.algorithm_profile, "reconstruction_public_road_map_refresh")
        self.assertEqual(scenario.kpi_gate, "reconstruction_public_road_map_refresh_gate")

    def test_qiyu_loop_carla_import_smoke_scenario_targets_source_runtime(self) -> None:
        scenario = load_scenario("scenarios/l2/reconstruction_qiyu_loop_carla_import_smoke.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l2" / "reconstruction_qiyu_loop_carla_import_smoke.yaml")
        manifest = load_yaml(REPO_ROOT / "assets" / "manifests" / "carla_qiyu_loop_20260430_105120_dynobs.yaml")
        gate = load_kpi_gate("reconstruction_carla_import_smoke_gate", REPO_ROOT)

        self.assertEqual(scenario.asset_bundle, "carla_qiyu_loop_20260430_105120_dynobs")
        self.assertEqual(scenario.algorithm_profile, "reconstruction_carla_import_smoke")
        self.assertEqual(scenario.kpi_gate, "reconstruction_carla_import_smoke_gate")
        self.assertEqual(payload["execution"]["stable_runtime"]["carla_root"], manifest["metadata"]["runtime"]["selected_root"])
        self.assertEqual(payload["execution"]["stable_runtime"]["carla_map"], manifest["maps"]["carla_map"]["runtime_name"])
        self.assertIn("assets/manifests/carla_qiyu_loop_20260430_105120_dynobs.yaml", payload["metadata"]["source_assets"])
        self.assertTrue(
            any("runtime_previews/dynobs_visual_review_20260501_191939" in item for item in payload["metadata"]["source_assets"])
        )
        self.assertIn("carla_custom_map_load_probe.py", payload["metadata"]["validation_command"])
        self.assertIn("qiyu_loop_20260430_105120_dynobs", payload["metadata"]["validation_command"])
        self.assertIn("--min-alignment-iou 0.95", payload["metadata"]["validation_command"])
        self.assertIn("carla_custom_map_load_passed", gate.metrics)
        self.assertAlmostEqual(gate.metrics["carla_custom_map_alignment_iou"]["value"], 0.95)
        self.assertAlmostEqual(manifest["metadata"]["alignment"]["previous_bbox_iou_xy"], 0.9504276622995398)
        self.assertAlmostEqual(manifest["metadata"]["alignment"]["bbox_iou_xy"], 0.9787353959979124)

    def test_qiyu_loop_dynobs_manifest_records_dynamic_cleanup_handoff(self) -> None:
        manifest = load_yaml(REPO_ROOT / "assets" / "manifests" / "carla_qiyu_loop_20260430_105120_dynobs.yaml")

        self.assertEqual(manifest["bundle_id"], "carla_qiyu_loop_20260430_105120_dynobs")
        self.assertEqual(manifest["metadata"]["rollback"]["previous_bundle"], "carla_qiyu_loop_20260430_105120_alignv2")
        self.assertEqual(manifest["metadata"]["carla_import_status"], "runtime_load_smoke_passed_on_source_compiled_carla")
        self.assertEqual(
            manifest["maps"]["carla_map"]["runtime_name"],
            "/Game/qiyu_loop_20260430_105120_dynobs/Maps/qiyu_loop_20260430_105120_dynobs/qiyu_loop_20260430_105120_dynobs",
        )
        self.assertAlmostEqual(manifest["metadata"]["alignment"]["bbox_iou_xy"], 0.9787353959979124)
        cleanup = manifest["metadata"]["dynamic_obstacle_cleanup"]
        self.assertEqual(cleanup["road_faces_preserved"], 13158)
        self.assertEqual(cleanup["removed_static_faces"], 1964)
        self.assertAlmostEqual(cleanup["removed_static_face_ratio"], 0.06546666666666667)
        self.assertIsInstance(cleanup["planning_time_window_cst"]["start"], str)
        self.assertIsInstance(cleanup["planning_time_window_cst"]["end"], str)
        visual_review = manifest["metadata"]["runtime_visual_review"]
        self.assertEqual(visual_review["status"], "passed")
        self.assertEqual(visual_review["runtime_port"], 2400)
        self.assertIn("topdown_full.png", visual_review["captures"])
        self.assertIn("dynobs_visual_review_20260501_191939", visual_review["report_file"])
        self.assertIn("qiyu_loop_20260430_105120_dynobs", manifest["source"]["package_tar"])
        self.assertIn("dynamic_obstacle_cleanup", manifest["metadata"]["tags"])

    def test_qiyu_loop_dynobs_autoware_route_smoke_uses_carla_frame_lanelet_candidate(self) -> None:
        scenario = load_scenario("scenarios/l2/reconstruction_qiyu_loop_dynobs_autoware_route_smoke.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "l2" / "reconstruction_qiyu_loop_dynobs_autoware_route_smoke.yaml")
        manifest = load_yaml(REPO_ROOT / "assets" / "manifests" / "site_gy_qyhx_gsh20260310_carla_dynobs_frame.yaml")

        self.assertEqual(scenario.asset_bundle, "site_gy_qyhx_gsh20260310_carla_dynobs_frame")
        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "planning_control_baseline")
        self.assertEqual(scenario.kpi_gate, "planning_control_smoke")
        self.assertEqual(
            payload["execution"]["stable_runtime"]["autoware_map_path"],
            "/data/pix/assets/site_gy_qyhx_gsh20260310_carla_dynobs_frame",
        )
        self.assertIn("qiyu_loop_20260430_105120_dynobs", payload["execution"]["stable_runtime"]["carla_map"])
        self.assertIn("carla_closed_loop_route_probe.py", payload["metadata"]["validation_command"])
        self.assertEqual(manifest["metadata"]["frame_transform"]["dx_m"], -1313.72028)
        self.assertEqual(manifest["metadata"]["frame_transform"]["dy_m"], 457.810557)
        self.assertEqual(manifest["metadata"]["frame_transform"]["local_y_rule"], "-(y + dy)")
        self.assertIn("carla_frame_candidate", manifest["metadata"]["tags"])

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
