from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.runtime_evidence import collect_runtime_evidence


class RuntimeEvidenceTests(unittest.TestCase):
    def test_closed_loop_route_quality_metrics_are_collected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_l1_follow_lane"
            runtime_dir = run_dir / "runtime_verification"
            runtime_dir.mkdir(parents=True)
            (runtime_dir / "closed_loop_route_sync_20260420T120204.json").write_text(
                json.dumps(
                    {
                        "goal": {"x": 314.0, "y": -2.0},
                        "service_calls": [{"step": "set_route_points", "returncode": 0}],
                        "summary": {
                            "moved": True,
                            "reached_near_goal": False,
                            "total_delta_m": 81.7,
                            "max_speed_mps": 3.9,
                            "sample_count": 400,
                            "last_location": {"x": 311.5, "y": 1.64},
                            "final_map_location": {"x": 311.5, "y": -1.64},
                            "effective_goal": {"x": 314.0, "y": -1.69},
                            "final_carla_waypoint": {
                                "lane_id": -1,
                                "center_map": {"x": 311.5, "y": -1.62},
                                "carla_lateral_error_m": 0.02,
                            },
                            "lateral_error_m": 0.34,
                            "route_goal_lateral_error_m": 0.05,
                            "longitudinal_error_m": 2.73,
                            "jerk_mps3": 1.7,
                            "stopped_before_goal": True,
                            "ros_telemetry": {
                                "enabled": True,
                                "topic_counts": {"control_cmd": 10},
                                "tail_stats": {
                                    "tail_control_velocity_mps": {
                                        "min": 0.0,
                                        "max": 1.0,
                                        "mean": 0.5,
                                        "sample_count": 10.0,
                                    }
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (runtime_dir / "closed_loop_route_sync_summary.json").write_text(
                json.dumps(
                    {
                        "overall_passed": False,
                        "route_passed": False,
                        "movement_passed": True,
                        "summary": {
                            "moved": True,
                            "reached_near_goal": False,
                            "total_delta_m": 71.0,
                            "sample_count": 400,
                        },
                    }
                ),
                encoding="utf-8",
            )
            run_result = {
                "scenario_params": {
                    "traffic_profile": {
                        "mode": "empty_route_follow",
                        "vehicles": 0,
                        "pedestrians": 0,
                    }
                }
            }

            summary = collect_runtime_evidence(run_dir, run_result)

            self.assertEqual(summary["attempt_count"], 1)
            self.assertEqual(summary["successful_attempt_count"], 0)
            self.assertEqual(summary["metrics"]["route_completion"], 0.0)
            self.assertEqual(summary["metrics"]["collision_count"], 0.0)
            self.assertEqual(summary["metrics"]["min_ttc_sec"], 999.0)
            self.assertEqual(summary["metrics"]["lateral_error_m"], 0.34)
            self.assertEqual(summary["metrics"]["route_goal_lateral_error_m"], 0.05)
            self.assertEqual(summary["metrics"]["longitudinal_error_m"], 2.73)
            self.assertEqual(summary["metrics"]["jerk_mps3"], 1.7)
            self.assertTrue(summary["attempts"][0]["stopped_before_goal"])
            self.assertEqual(summary["attempts"][0]["effective_goal"]["y"], -1.69)
            self.assertEqual(summary["attempts"][0]["final_carla_waypoint"]["lane_id"], -1)
            self.assertEqual(
                summary["attempts"][0]["ros_telemetry"]["tail_stats"]["tail_control_velocity_mps"]["mean"],
                0.5,
            )

    def test_public_road_multi_actor_merge_accepts_multi_actor_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_l2_public_road"
            probe_dir = (
                run_dir
                / "runtime_verification"
                / "l2_multi_actor_cut_in_lead_brake_actor_bridge_20260420T184644"
            )
            probe_dir.mkdir(parents=True)
            (probe_dir / "l2_multi_actor_cut_in_lead_brake_actor_bridge_20260420T184644.json").write_text(
                json.dumps(
                    {
                        "classification": "l2_multi_actor_cut_in_lead_brake_with_perception_pipeline",
                        "service_calls": [{"step": "set_route_points", "returncode": 0}],
                        "summary": {
                            "sample_count": 121,
                            "moved": True,
                            "collision_count": 0,
                            "min_distance_m": 18.6,
                            "min_ttc_sec": 6.9,
                            "autoware_reacted": True,
                            "total_delta_m": 26.7,
                            "actor_count_spawned": 3,
                            "actor_count_observed": 3,
                            "object_pipeline_nonempty_duration_ratio": 1.0,
                        },
                        "object_pipeline": {
                            "perception_source": "actor_bridge",
                            "dummy_object_injected": False,
                            "objects_topic_nonempty_after_injection": True,
                        },
                        "verdict": {
                            "overall_passed": True,
                            "safety_passed": True,
                            "autoware_dynamic_actor_response_passed": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            run_result = {
                "scenario_params": {
                    "traffic_profile": {
                        "mode": "public_road_merge_actor_bridge_surrogate",
                        "vehicles": 3,
                        "pedestrians": 0,
                    }
                }
            }

            summary = collect_runtime_evidence(run_dir, run_result)

            self.assertEqual(summary["dynamic_probe_attempt_count"], 1)
            self.assertEqual(summary["successful_dynamic_probe_count"], 1)
            self.assertEqual(summary["ignored_dynamic_probe_attempts"], [])
            self.assertEqual(summary["metrics"]["route_completion"], 1.0)
            self.assertEqual(summary["metrics"]["actor_count_observed"], 3.0)
            self.assertEqual(summary["metric_sources"]["dynamic_actor_response"], "runtime_dynamic_probe")

    def test_sumo_cosim_probe_metrics_are_collected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_sumo_town01"
            probe_dir = run_dir / "runtime_verification" / "sumo_cosim_20260423T120000"
            probe_dir.mkdir(parents=True)
            (probe_dir / "sumo_cosim_20260423T120000.json").write_text(
                json.dumps(
                    {
                        "kind": "sumo_cosim_probe",
                        "profile": "town01_sumo_smoke",
                        "overall_passed": True,
                        "summary": {
                            "sumo_cosim_alive": True,
                            "sumo_actor_count": 4,
                            "sumo_route_loaded": True,
                            "sumo_step_samples": 1,
                            "autoware_object_stream_seen": True,
                            "ego_control_command_seen": True,
                        },
                        "metrics": {
                            "sumo_cosim_alive": 1.0,
                            "sumo_actor_count": 4.0,
                            "sumo_route_loaded": 1.0,
                            "sumo_step_samples": 1.0,
                            "autoware_object_stream_seen": 1.0,
                            "ego_control_command_seen": 1.0,
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = collect_runtime_evidence(run_dir, {"scenario_params": {"traffic_profile": {}}})

            self.assertEqual(summary["sumo_cosim_attempt_count"], 1)
            self.assertEqual(summary["successful_sumo_cosim_count"], 1)
            self.assertEqual(summary["metrics"]["sumo_actor_count"], 4.0)
            self.assertEqual(summary["metrics"]["autoware_object_stream_seen"], 1.0)
            self.assertEqual(
                summary["metric_sources"]["sumo_actor_count"],
                "runtime_sumo_cosim_probe",
            )

    def test_l3_occluded_pedestrian_probe_is_collected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_l3_occluded_pedestrian"
            probe_dir = (
                run_dir
                / "runtime_verification"
                / "l3_occluded_pedestrian_dummy_injection_20260422T184644"
            )
            probe_dir.mkdir(parents=True)
            (probe_dir / "l3_occluded_pedestrian_dummy_injection_20260422T184644.json").write_text(
                json.dumps(
                    {
                        "classification": "l3_occluded_pedestrian_visual_actor_with_pedestrian_dummy_injection",
                        "service_calls": [{"step": "set_route_points", "returncode": 0}],
                        "summary": {
                            "sample_count": 150,
                            "moved": True,
                            "collision_count": 0,
                            "min_distance_m": 7.2,
                            "min_ttc_sec": 3.4,
                            "autoware_reacted": True,
                            "total_delta_m": 24.8,
                            "actor_count_spawned": 2,
                            "actor_count_observed": 1,
                            "object_pipeline_nonempty_duration_ratio": 1.0,
                        },
                        "object_pipeline": {
                            "perception_source": "dummy_injection",
                            "dummy_object_injected": True,
                            "objects_topic_nonempty_after_injection": True,
                        },
                        "verdict": {
                            "overall_passed": True,
                            "safety_passed": True,
                            "autoware_dynamic_actor_response_passed": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            run_result = {
                "scenario_params": {
                    "traffic_profile": {
                        "mode": "l3_occluded_pedestrian_dummy_injection",
                        "vehicles": 1,
                        "pedestrians": 1,
                    }
                }
            }

            summary = collect_runtime_evidence(run_dir, run_result)

            self.assertEqual(summary["dynamic_probe_attempt_count"], 1)
            self.assertEqual(summary["successful_dynamic_probe_count"], 1)
            self.assertEqual(summary["ignored_dynamic_probe_attempts"], [])
            self.assertEqual(summary["metrics"]["route_completion"], 1.0)
            self.assertEqual(summary["metrics"]["actor_count_observed"], 1.0)
            self.assertEqual(summary["metrics"]["yield_response_count"], 1.0)

    def test_l3_expanded_occluded_pedestrian_probe_is_collected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_l3_occluded_pedestrian_close_yield"
            probe_dir = (
                run_dir
                / "runtime_verification"
                / "l3_occluded_pedestrian_close_yield_dummy_injection_20260423T020000"
            )
            probe_dir.mkdir(parents=True)
            (probe_dir / "l3_occluded_pedestrian_close_yield_dummy_injection_20260423T020000.json").write_text(
                json.dumps(
                    {
                        "classification": "l3_occluded_pedestrian_close_yield_visual_actor_with_pedestrian_dummy_injection",
                        "service_calls": [{"step": "set_route_points", "returncode": 0}],
                        "summary": {
                            "sample_count": 160,
                            "moved": True,
                            "collision_count": 0,
                            "min_distance_m": 6.1,
                            "min_ttc_sec": 2.8,
                            "autoware_reacted": True,
                            "total_delta_m": 21.5,
                            "actor_count_spawned": 2,
                            "actor_count_observed": 1,
                            "object_pipeline_nonempty_duration_ratio": 0.5,
                        },
                        "object_pipeline": {
                            "perception_source": "dummy_injection",
                            "dummy_object_injected": True,
                            "objects_topic_nonempty_after_injection": True,
                        },
                        "verdict": {
                            "overall_passed": True,
                            "safety_passed": True,
                            "autoware_dynamic_actor_response_passed": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            run_result = {
                "scenario_params": {
                    "traffic_profile": {
                        "mode": "l3_occluded_pedestrian_close_yield_dummy_injection",
                        "vehicles": 1,
                        "pedestrians": 1,
                    }
                }
            }

            summary = collect_runtime_evidence(run_dir, run_result)

            self.assertEqual(summary["dynamic_probe_attempt_count"], 1)
            self.assertEqual(summary["successful_dynamic_probe_count"], 1)
            self.assertEqual(summary["ignored_dynamic_probe_attempts"], [])
            self.assertEqual(summary["metrics"]["dynamic_actor_response"], 1.0)
            self.assertEqual(summary["metrics"]["actor_count_observed"], 1.0)

    def test_lidar_calibration_metric_probe_is_collected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_lidar_calibration"
            probe_dir = run_dir / "runtime_verification" / "metric_probe_lidar_sensor_kit_extrinsic_20260420T120000"
            probe_dir.mkdir(parents=True)
            (probe_dir / "metric_probe_lidar_sensor_kit_extrinsic_20260420T120000.json").write_text(
                json.dumps(
                    {
                        "profile": "lidar_sensor_kit_extrinsic",
                        "overall_passed": True,
                        "missing_metrics": [],
                        "missing_topics": [],
                        "sample_missing_topics": [],
                        "metrics_file": str(
                            run_dir
                            / "runtime_verification"
                            / "calibration"
                            / "lidar_sensor_kit_extrinsic"
                            / "calibration_result.json"
                        ),
                        "metrics": {
                            "calibration_converged": 1.0,
                            "calibrated_lidar_count": 5.0,
                            "lidar_extrinsic_translation_error_m": 0.018,
                            "lidar_extrinsic_rotation_error_deg": 0.22,
                            "lidar_pairwise_registration_rmse_m": 0.032,
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = collect_runtime_evidence(run_dir, {"scenario_params": {"traffic_profile": {}}})

            self.assertEqual(summary["metric_probe_attempt_count"], 1)
            self.assertEqual(summary["successful_metric_probe_count"], 1)
            self.assertEqual(summary["metrics"]["calibrated_lidar_count"], 5.0)
            self.assertEqual(
                summary["metric_sources"]["lidar_extrinsic_translation_error_m"],
                "runtime_metric_probe",
            )

    def test_calibration_scene_and_camera_fiducial_evidence_are_collected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_lidar_workshop"
            runtime_dir = run_dir / "runtime_verification"
            scene_dir = runtime_dir / "calibration_scene"
            camera_dir = runtime_dir / "calibration" / "camera_fiducial_board_detection"
            scene_dir.mkdir(parents=True)
            camera_dir.mkdir(parents=True)

            spawned = [
                {
                    "target_id": f"qr_board_{index:02d}",
                    "marker": {"qr_payload": f"PXC:qr_board_{index:02d}"},
                    "panel": {"panel_size_m": [1.6, 1.6]},
                    "marker_overlay": {"marker_count": 1},
                    "panel_overlay": {"line_count": 16},
                }
                for index in range(12)
            ]
            (scene_dir / "calibration_workshop_bv1qk411d7ta_scene_spawn.json").write_text(
                json.dumps(
                    {
                        "scene_asset_id": "calibration_workshop_bv1qk411d7ta_scene",
                        "target_count": 12,
                        "spawned_count": 12,
                        "failed_count": 0,
                        "skipped_count": 0,
                        "spawned": spawned,
                    }
                ),
                encoding="utf-8",
            )
            (camera_dir / "detection_result.json").write_text(
                json.dumps(
                    {
                        "passed": True,
                        "capture_from_carla": True,
                        "expected_board_count": 12,
                        "captured_images": [
                            {"camera": "front_camera", "path": "front.png"},
                            {"camera": "left_camera", "path": "left.png"},
                            {"camera": "right_camera", "path": "right.png"},
                            {"camera": "rear_camera", "path": "rear.png"},
                        ],
                        "detection_count": 25,
                        "qr_count": 1,
                        "aruco_count": 0,
                        "binary_fiducial_candidate_count": 24,
                    }
                ),
                encoding="utf-8",
            )

            summary = collect_runtime_evidence(run_dir, {"scenario_params": {"traffic_profile": {}}})

            self.assertEqual(summary["calibration_scene_attempt_count"], 1)
            self.assertEqual(summary["successful_calibration_scene_count"], 1)
            self.assertEqual(summary["camera_fiducial_attempt_count"], 1)
            self.assertEqual(summary["successful_camera_fiducial_count"], 1)
            self.assertEqual(summary["metrics"]["calibration_scene_target_count"], 12.0)
            self.assertEqual(summary["metrics"]["calibration_scene_spawned_count"], 12.0)
            self.assertEqual(summary["metrics"]["calibration_scene_panel_count"], 12.0)
            self.assertEqual(summary["metrics"]["calibration_scene_marker_overlay_count"], 12.0)
            self.assertEqual(summary["metrics"]["calibration_scene_panel_overlay_line_count"], 192.0)
            self.assertEqual(summary["metrics"]["calibration_scene_marker_payload_count"], 12.0)
            self.assertEqual(summary["metrics"]["camera_fiducial_expected_board_count"], 12.0)
            self.assertEqual(summary["metrics"]["camera_fiducial_captured_image_count"], 4.0)
            self.assertEqual(summary["metrics"]["camera_fiducial_detection_count"], 25.0)
            self.assertEqual(summary["metrics"]["camera_fiducial_qr_count"], 1.0)
            self.assertEqual(
                summary["metric_sources"]["calibration_scene_spawned_count"],
                "runtime_calibration_scene_spawn",
            )
            self.assertEqual(
                summary["metric_sources"]["camera_fiducial_detection_count"],
                "runtime_camera_fiducial_probe",
            )


if __name__ == "__main__":
    unittest.main()
