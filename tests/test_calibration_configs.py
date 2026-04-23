from __future__ import annotations

import sys
import unittest
import importlib.util
from math import hypot
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.config import load_yaml
from simctl.evaluation import load_kpi_gate
from simctl.profiles import load_algorithm_profile
from simctl.scenarios import load_scenario


CALIBRATION_SCENARIOS = [
    "scenarios/calibration/lidar_sensor_kit_extrinsic.yaml",
    "scenarios/calibration/lidar_workshop_bv1qk411d7ta.yaml",
]

DRIVING_TEST_SCENARIOS = [
    "scenarios/l0/robobus117th_town01_closed_loop.yaml",
    "scenarios/l1/regression_follow_lane.yaml",
    "scenarios/l2/planning_control_merge_regression.yaml",
    "scenarios/l2/planning_control_multi_actor_cut_in_lead_brake.yaml",
    "scenarios/l2/planning_control_public_road_merge_regression.yaml",
    "scenarios/l2/robobus117th_town01_close_cut_in_actor_bridge.yaml",
]


def _stable_spawn_xy(payload: dict) -> tuple[float, float]:
    spawn_point = payload["execution"]["stable_runtime"]["carla_spawn_point"]
    parts = [float(part.strip()) for part in spawn_point.split(",")]
    if len(parts) != 6:
        raise AssertionError(f"Expected 6-part CARLA spawn point, got: {spawn_point}")
    return parts[0], parts[1]


def _load_scene_spawner():
    path = REPO_ROOT / "stack" / "stable" / "carla_calibration_scene_spawner.py"
    spec = importlib.util.spec_from_file_location("carla_calibration_scene_spawner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CalibrationConfigTests(unittest.TestCase):
    def test_lidar_calibration_scenario_loads_with_metric_probe_contract(self) -> None:
        scenario = load_scenario("scenarios/calibration/lidar_sensor_kit_extrinsic.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "calibration" / "lidar_sensor_kit_extrinsic.yaml")
        gate = load_kpi_gate("lidar_sensor_kit_extrinsic", REPO_ROOT)
        profile = load_algorithm_profile("lidar_sensor_kit_extrinsic_calibration", REPO_ROOT)

        self.assertEqual(scenario.sensor_profile, "robobus_pixrover14_application_topology")
        self.assertEqual(scenario.algorithm_profile, "lidar_sensor_kit_extrinsic_calibration")
        self.assertEqual(profile.profile_type, "calibration")
        self.assertEqual(scenario.kpi_gate, "lidar_sensor_kit_extrinsic")
        self.assertIn("lidar_extrinsic_translation_error_m", gate.metrics)
        self.assertIn("calibration_scene_spawned_count", gate.metrics)
        self.assertIn("camera_fiducial_detection_count", gate.metrics)
        self.assertIn("lidar_board_hit_count", gate.metrics)
        self.assertIn("sensor_sample_coverage", gate.metrics)
        self.assertIn(
            "ops/runtime_probes/lidar_calibration_metric_probe.py",
            payload["metadata"]["source_assets"],
        )
        self.assertIn("lidar_calibration_metric_probe.py", payload["metadata"]["validation_command"])

    def test_calibration_scenarios_do_not_overlap_driving_test_anchors(self) -> None:
        driving_anchors = {
            scenario_path: _stable_spawn_xy(load_yaml(REPO_ROOT / scenario_path))
            for scenario_path in DRIVING_TEST_SCENARIOS
        }

        for scenario_path in CALIBRATION_SCENARIOS:
            with self.subTest(scenario=scenario_path):
                payload = load_yaml(REPO_ROOT / scenario_path)
                isolation = payload["metadata"]["scene_isolation"]
                self.assertEqual(isolation["class"], "calibration_only")
                self.assertIn("calibration_only", payload["labels"])
                self.assertIn("not_driving_regression", payload["labels"])
                required_distance_m = float(isolation["min_distance_from_driving_test_spawn_m"])
                self.assertGreaterEqual(required_distance_m, 250.0)
                self.assertEqual(
                    set(isolation["must_not_overlap_with"]),
                    set(DRIVING_TEST_SCENARIOS),
                )
                calibration_x, calibration_y = _stable_spawn_xy(payload)
                for driving_path, (driving_x, driving_y) in driving_anchors.items():
                    distance_m = hypot(calibration_x - driving_x, calibration_y - driving_y)
                    self.assertGreaterEqual(
                        distance_m,
                        required_distance_m,
                        f"{scenario_path} overlaps driving-test anchor {driving_path}",
                    )

    def test_lidar_calibration_assets_define_five_truth_and_initial_frames(self) -> None:
        truth = load_yaml(REPO_ROOT / "assets" / "calibration" / "lidar_sensor_kit_truth.yaml")
        initial = load_yaml(REPO_ROOT / "assets" / "calibration" / "lidar_sensor_kit_initial_perturbed.yaml")

        self.assertEqual(truth["coordinate_contract"]["visibility"], "evaluator_only")
        self.assertEqual(initial["coordinate_contract"]["visibility"], "calibration_program_input")
        self.assertEqual(len(truth["lidars"]), 5)
        self.assertEqual(set(truth["lidars"]), set(initial["lidars"]))
        self.assertEqual(
            truth["lidars"]["lidar_ft_base_link"]["topic"],
            "/sensing/lidar/top/pointcloud_before_sync",
        )
        self.assertNotEqual(
            truth["lidars"]["lidar_ft_base_link"]["transform"]["x"],
            initial["lidars"]["lidar_ft_base_link"]["transform"]["x"],
        )

    def test_video_workshop_lidar_scenario_tracks_source_and_proxy_limits(self) -> None:
        scenario = load_scenario("scenarios/calibration/lidar_workshop_bv1qk411d7ta.yaml", REPO_ROOT)
        payload = load_yaml(REPO_ROOT / "scenarios" / "calibration" / "lidar_workshop_bv1qk411d7ta.yaml")
        scene = load_yaml(
            REPO_ROOT / "assets" / "calibration" / "calibration_workshop_bv1qk411d7ta_scene.yaml"
        )

        self.assertEqual(scenario.kpi_gate, "lidar_sensor_kit_extrinsic")
        self.assertEqual(scenario.algorithm_profile, "lidar_sensor_kit_extrinsic_calibration")
        self.assertEqual(payload["metadata"]["source_video"]["url"], "https://www.bilibili.com/video/BV1qK411D7TA/")
        self.assertEqual(
            payload["metadata"]["executable_scope"],
            "carla_spawnable_proxy_until_indoor_workshop_assets_exist",
        )
        self.assertIn(
            "assets/calibration/calibration_workshop_bv1qk411d7ta_scene.yaml",
            payload["metadata"]["source_assets"],
        )
        self.assertIn(
            "assets/calibration/boards/single_qr_fiducial_board.yaml",
            payload["metadata"]["source_assets"],
        )
        self.assertIn(
            "ops/runtime_probes/camera_fiducial_board_opencv_probe.py",
            payload["metadata"]["source_assets"],
        )
        self.assertIn(
            "ops/runtime_probes/lidar_fiducial_board_hit_probe.py",
            payload["metadata"]["source_assets"],
        )
        self.assertIn(
            "ops/runtime_probes/lidar_camera_projection_probe.py",
            payload["metadata"]["source_assets"],
        )
        self.assertIn("lidar_fiducial_board_hit_probe.py", payload["metadata"]["validation_command"])
        self.assertIn("camera_fiducial_board_opencv_probe.py", payload["metadata"]["validation_command"])
        self.assertIn("lidar_camera_projection_probe.py", payload["metadata"]["validation_command"])
        self.assertEqual(scene["source"]["evidence_level"], "video_reference_plus_dimensioned_proxy")
        self.assertEqual(scene["scene_intent"]["executable_status"], "carla_spawnable_proxy")
        self.assertEqual(scene["scene_intent"]["target_style"], "dimensioned_single_qr_panel_12_targets")
        self.assertEqual(scene["scene_intent"]["spawner"], "stack/stable/carla_calibration_scene_spawner.py")
        self.assertEqual(scene["capture_contract"]["required_static_targets"], 12)
        self.assertEqual(scene["capture_contract"]["marker_count_per_board"], 1)
        self.assertEqual(scene["capture_contract"]["required_panel_geometry"]["panel_count"], 12)
        self.assertEqual(scene["capture_contract"]["required_panel_geometry"]["expected_panel_size_m"], [1.6, 1.6])
        self.assertEqual(scene["layout_proxy"]["target_mounting_contract"]["qr_print_size_m"], 1.05)
        self.assertEqual(len(scene["capture_contract"]["required_lidar_topics"]), 5)
        self.assertEqual(len(scene["static_calibration_targets"]["fiducial_board_targets"]), 12)

        board = load_yaml(
            REPO_ROOT
            / "assets"
            / "calibration"
            / "boards"
            / "single_qr_fiducial_board.yaml"
        )
        self.assertEqual(board["opencv_contract"]["detector"], "QRCodeDetector")
        self.assertEqual(board["opencv_contract"]["marker_type"], "qr_code")
        self.assertEqual(board["opencv_contract"]["marker_num"], 1)
        self.assertEqual(board["physical_panel"]["panel_size_m"], [1.6, 1.6])
        self.assertEqual(board["physical_panel"]["marker_color"], "matte_black")
        self.assertTrue(board["physical_panel"]["measured_corner_required"])

    def test_video_workshop_scene_spawner_builds_target_plan(self) -> None:
        spawner = _load_scene_spawner()
        scene_path = REPO_ROOT / "assets" / "calibration" / "calibration_workshop_bv1qk411d7ta_scene.yaml"
        scene = spawner.load_scene(scene_path)

        plan = spawner.build_spawn_plan(scene, scene_path)

        self.assertEqual(plan["scene_asset_id"], "calibration_workshop_bv1qk411d7ta_scene")
        self.assertEqual(plan["target_count"], 12)
        target_ids = {target["target_id"] for target in plan["targets"]}
        self.assertIn("front_qr_board", target_ids)
        self.assertIn("front_upper_qr_board", target_ids)
        self.assertIn("rear_upper_qr_board", target_ids)
        self.assertIn("front_left_qr_corner_board", target_ids)
        self.assertTrue(all(target["kind"] == "fiducial_board" for target in plan["targets"]))
        self.assertTrue(all(target["size_m"] == [1.6, 1.6] for target in plan["targets"]))
        self.assertTrue(all(target["panel"]["panel_size_m"] == [1.6, 1.6] for target in plan["targets"]))
        self.assertTrue(all(target["panel"]["frame_width_m"] == 0.06 for target in plan["targets"]))
        self.assertTrue(all(target["panel"]["measured_corner_required"] for target in plan["targets"]))
        self.assertTrue(all(target["marker"]["type"] == "qr_code" for target in plan["targets"]))
        self.assertTrue(all(target["marker"]["marker_count_per_board"] == 1 for target in plan["targets"]))
        self.assertTrue(all(len(target["marker_set"]) == 1 for target in plan["targets"]))
        self.assertEqual(
            len({target["marker"]["qr_payload"] for target in plan["targets"]}),
            12,
        )
        self.assertTrue(all(target["marker"]["qr_payload"].startswith("PXC:") for target in plan["targets"]))
        self.assertTrue(all(len(target["marker"]["qr_payload"]) <= 32 for target in plan["targets"]))
        self.assertEqual(
            {marker["type"] for target in plan["targets"] for marker in target["marker_set"]},
            {"qr_code"},
        )
        self.assertEqual(
            {target["panel"]["mount_type"] for target in plan["targets"] if "upper" in target["target_id"]},
            {"front_wall_rail", "rear_wall_rail"},
        )
        self.assertEqual(plan["coordinate_contract"]["spawn_mode"], "relative_to_ego_vehicle")

    def test_scene_spawner_can_generate_single_qr_matrix(self) -> None:
        spawner = _load_scene_spawner()

        matrix = spawner.qr_code_matrix("PXC:front_qr_board", quiet_zone_modules=4)

        self.assertEqual(len(matrix), 33)
        self.assertEqual(len(matrix[0]), 33)
        self.assertTrue(matrix[4][4])
        self.assertTrue(matrix[8][8])
        self.assertTrue(matrix[28][4])


if __name__ == "__main__":
    unittest.main()
