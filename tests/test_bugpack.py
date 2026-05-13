from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.bugpack import classify_run_result, write_bugpack


def _base_result(run_dir: Path, *, status: str = "failed") -> dict[str, object]:
    return {
        "run_id": run_dir.name,
        "scenario_id": "stable_l2_planning_control_merge_regression",
        "stack": "stable",
        "status": status,
        "scenario_path": "scenarios/l2/planning_control_merge_regression.yaml",
        "scenario_params": {
            "map_id": "Town01",
            "goal": {"route_id": "Town01/merge"},
            "labels": ["stable", "planning_control", "merge"],
        },
        "software_versions": {
            "autoware_universe": "main",
            "ros2": "humble",
            "carla": "0.9.15",
            "unreal_engine": "4.26",
        },
        "resolved_profiles": {
            "sensor": {"profile_id": "robobus_pixrover14_application_topology"},
            "algorithm": {"profile_id": "planning_control_baseline"},
        },
        "runtime_health": {"passed": True},
        "gate": {
            "gate_id": "planning_control_multi_actor_regression",
            "passed": False,
            "violations": [
                {
                    "metric": "min_ttc_sec",
                    "reason": "threshold_violation",
                    "actual": 0.6,
                    "op": ">=",
                    "threshold": 1.8,
                }
            ],
            "failure_labels": ["collision_failure"],
        },
        "kpis": {"min_ttc_sec": 0.6, "collision_count": 0.0},
        "artifacts": {
            "run_dir": str(run_dir),
            "run_result": str(run_dir / "run_result.json"),
            "runtime_evidence_summary": str(run_dir / "runtime_evidence_summary.json"),
            "health_report": str(run_dir / "health.json"),
        },
        "slot_id": "stable-slot-01",
    }


def _roadtest_replay_result(run_dir: Path) -> dict[str, object]:
    result = _base_result(run_dir)
    result["scenario_id"] = "stable_l2_planning_control_roadtest_trajectory_dropout_replay_draft"
    result["scenario_path"] = "scenarios/l2/planning_control_roadtest_trajectory_dropout_replay_draft.yaml"
    result["runtime_health"] = None
    result["scenario_params"] = {
        "map_id": "roadtest_gy_qyhx_202604",
        "goal": {"route_id": "roadtest_replay/trajectory_dropout_source_goal"},
        "labels": ["stable", "planning_control", "road_test_replay", "trajectory_dropout", "draft"],
    }
    result["gate"] = {
        "gate_id": "planning_control_trajectory_stability_replay",
        "passed": False,
        "violations": [
            {
                "metric": "trajectory_silence_sec",
                "reason": "threshold_violation",
                "actual": 130.749133911,
                "op": "<=",
                "threshold": 1.0,
            },
            {
                "metric": "route_empty_count",
                "reason": "threshold_violation",
                "actual": 1.0,
                "op": "<=",
                "threshold": 0.0,
            },
        ],
    }
    result["kpis"] = {
        "trajectory_silence_sec": 130.749133911,
        "route_empty_count": 1.0,
        "roadtest_replay_case_count": 3.0,
    }
    return result


def _route_recovery_kinematic_result(run_dir: Path) -> dict[str, object]:
    result = _base_result(run_dir)
    result["scenario_id"] = "stable_l2_planning_route_update_dropout_recovery"
    result["scenario_path"] = "scenarios/l2/planning_route_update_dropout_recovery.yaml"
    result["gate"] = {
        "gate_id": "planning_route_update_dropout_recovery",
        "passed": False,
        "violations": [
            {
                "metric": "route_completion",
                "reason": "threshold_violation",
                "actual": 0.0,
                "op": ">=",
                "threshold": 0.98,
            },
            {
                "metric": "lateral_error_m",
                "reason": "threshold_violation",
                "actual": 1.614568,
                "op": "<=",
                "threshold": 1.0,
            },
        ],
    }
    result["kpis"] = {
        "route_completion": 0.0,
        "lateral_error_m": 1.614568,
        "route_goal_lateral_error_m": 1.6155948,
        "longitudinal_error_m": 1.932556,
        "jerk_mps3": 6.7516858,
        "kinematic_sanity_passed": 0.0,
        "max_abs_roll_deg": 46.50156,
        "max_abs_pitch_deg": 12.270803,
        "max_ego_z_m": 2.063667,
    }
    return result


def _route_goal_geometry_result(run_dir: Path) -> dict[str, object]:
    result = _base_result(run_dir)
    result["scenario_id"] = "stable_l1_robobus117th_town01_speed40_probe"
    result["scenario_path"] = "scenarios/l1/robobus117th_town01_speed40_probe.yaml"
    result["gate"] = {
        "gate_id": "planning_control_speed40_probe",
        "passed": False,
        "violations": [
            {
                "metric": "route_completion",
                "reason": "threshold_violation",
                "actual": 0.0,
                "op": ">=",
                "threshold": 0.98,
            },
            {
                "metric": "route_goal_lateral_error_m",
                "reason": "threshold_violation",
                "actual": 4.227222,
                "op": "<=",
                "threshold": 0.8,
            },
        ],
    }
    result["kpis"] = {
        "route_completion": 0.0,
        "max_speed_kph": 40.012,
        "lateral_error_m": 0.245,
        "route_goal_lateral_error_m": 4.227222,
        "longitudinal_error_m": 60.854,
        "jerk_mps3": 2.42,
        "max_abs_roll_deg": 2.67,
        "kinematic_sanity_passed": 1.0,
    }
    return result


def _speed40_simulation_fidelity_result(run_dir: Path) -> dict[str, object]:
    result = _base_result(run_dir)
    result["scenario_id"] = "stable_l1_robobus117th_town01_speed40_probe"
    result["scenario_path"] = "scenarios/l1/robobus117th_town01_speed40_probe.yaml"
    result["scenario_params"] = {
        "map_id": "Town01",
        "labels": ["stable", "planning_control", "simulation_fidelity", "robobus117th"],
    }
    result["gate"] = {
        "gate_id": "planning_control_speed40_probe",
        "passed": False,
        "violations": [
            {
                "metric": "route_completion",
                "reason": "threshold_violation",
                "actual": 0.0,
                "op": ">=",
                "threshold": 0.98,
            },
            {
                "metric": "lateral_error_m",
                "reason": "threshold_violation",
                "actual": 1.05,
                "op": "<=",
                "threshold": 0.75,
            },
        ],
    }
    result["kpis"] = {
        "route_completion": 0.0,
        "max_speed_kph": 39.95,
        "lateral_error_m": 1.05,
        "route_goal_lateral_error_m": 1.03,
        "longitudinal_error_m": 49.37,
        "max_abs_roll_deg": 2.02,
        "kinematic_sanity_passed": 1.0,
    }
    return result


class BugpackTests(unittest.TestCase):
    def test_classifies_planning_control_kpi_failure_as_bug_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_failed"
            run_dir.mkdir()
            result = _base_result(run_dir)

            triage = classify_run_result(result, run_dir / "run_result.json")

            self.assertEqual(triage["classification"], "planning_control_bug_candidate")
            self.assertEqual(triage["severity"], "P1")
            self.assertIn("planning", triage["suspected_modules"])

    def test_classifies_roadtest_replay_kpi_failure_as_planning_bug_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_roadtest_replay_failed"
            run_dir.mkdir()
            result = _roadtest_replay_result(run_dir)

            triage = classify_run_result(result, run_dir / "run_result.json")

            self.assertEqual(triage["classification"], "planning_control_bug_candidate")
            self.assertEqual(triage["runtime_health_passed"], None)
            self.assertIn("planning", triage["suspected_modules"])

    def test_kinematic_instability_is_owned_as_closed_loop_vehicle_dynamics(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_route_recovery_failed"
            run_dir.mkdir()
            result = _route_recovery_kinematic_result(run_dir)

            triage = classify_run_result(result, run_dir / "run_result.json")

            self.assertEqual(triage["classification"], "planning_control_bug_candidate")
            self.assertEqual(triage["severity"], "P1")
            self.assertIn("closed_loop_vehicle_dynamics", triage["suspected_modules"])
            self.assertIn("control", triage["suspected_modules"])
            self.assertIn("planning", triage["suspected_modules"])

    def test_route_goal_mismatch_with_good_lane_error_is_owned_as_simulation_fidelity(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_speed40_route_geometry_failed"
            run_dir.mkdir()
            result = _route_goal_geometry_result(run_dir)

            triage = classify_run_result(result, run_dir / "run_result.json")

            self.assertEqual(triage["classification"], "planning_control_bug_candidate")
            self.assertIn("simulation_fidelity", triage["suspected_modules"])
            self.assertIn("scenario_route_geometry", triage["suspected_modules"])
            self.assertIn("autoware_carla_bridge", triage["suspected_modules"])
            self.assertIn("planning", triage["suspected_modules"])

    def test_speed40_fidelity_scope_keeps_bridge_dynamics_in_suspected_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_speed40_fidelity_failed"
            run_dir.mkdir()
            result = _speed40_simulation_fidelity_result(run_dir)

            triage = classify_run_result(result, run_dir / "run_result.json")

            self.assertEqual(triage["classification"], "planning_control_bug_candidate")
            self.assertIn("simulation_fidelity", triage["suspected_modules"])
            self.assertIn("closed_loop_vehicle_dynamics", triage["suspected_modules"])
            self.assertIn("autoware_carla_bridge", triage["suspected_modules"])

    def test_write_bugpack_creates_issue_for_roadtest_replay_without_include_infra(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "run_roadtest_replay_failed"
            run_dir.mkdir(parents=True)
            result_path = run_dir / "run_result.json"
            result_path.write_text(json.dumps(_roadtest_replay_result(run_dir)), encoding="utf-8")

            summary = write_bugpack(
                run_result_paths=[result_path],
                output_dir=root / "bugpack",
                owner="planning-control",
            )

            self.assertEqual(summary["issue_count"], 1)
            self.assertEqual(summary["blocked_count"], 0)
            issue = Path(summary["issues"][0]["issue_path"]).read_text(encoding="utf-8")
            self.assertIn("trajectory_silence_sec", issue)
            self.assertIn("route_empty_count", issue)

    def test_write_bugpack_creates_issue_markdown_for_failed_planning_run(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "run_failed"
            run_dir.mkdir(parents=True)
            runtime_dir = run_dir / "runtime_verification"
            runtime_dir.mkdir()
            (runtime_dir / "closed_loop_route_sync_summary.json").write_text(
                json.dumps(
                    {
                        "camera_video": {
                            "path": str(runtime_dir / "speed40_route_sync.mp4"),
                            "mode": "ego_chase",
                        }
                    }
                ),
                encoding="utf-8",
            )
            result_path = run_dir / "run_result.json"
            result_path.write_text(json.dumps(_base_result(run_dir)), encoding="utf-8")

            summary = write_bugpack(
                run_result_paths=[result_path],
                output_dir=root / "bugpack",
                owner="planning-control",
            )

            self.assertEqual(summary["issue_count"], 1)
            self.assertEqual(summary["blocked_count"], 0)
            issue_path = Path(summary["issues"][0]["issue_path"])
            self.assertTrue(issue_path.exists())
            issue = issue_path.read_text(encoding="utf-8")
            self.assertIn("## Reproduction conditions", issue)
            self.assertIn("min_ttc_sec", issue)
            self.assertIn("closed_loop_route_summary", issue)
            self.assertIn("speed40_route_sync.mp4", issue)
            self.assertIn("planning-control", issue)
            self.assertTrue((root / "bugpack" / "index.md").exists())
            self.assertTrue((root / "bugpack" / "summary.json").exists())

    def test_issue_markdown_includes_kinematic_probe_diagnosis(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "run_route_recovery_failed"
            run_dir.mkdir(parents=True)
            runtime_dir = run_dir / "runtime_verification"
            runtime_dir.mkdir()
            (runtime_dir / "closed_loop_route_sync_20260511T055747.json").write_text(
                json.dumps(
                    {
                        "verdict": {"overall_passed": False, "movement_passed": True},
                        "summary": {
                            "route_service_calls_successful": True,
                            "all_service_calls_successful": True,
                            "max_speed_mps": 3.204,
                            "total_delta_m": 21.4,
                            "stopped_before_goal": False,
                            "kinematic_sanity_passed": False,
                            "max_abs_roll_deg": 46.50156,
                            "max_abs_pitch_deg": 12.270803,
                            "min_ego_z_m": 0.0999,
                            "max_ego_z_m": 2.063667,
                            "reached_near_goal": False,
                            "min_goal_distance_m": 1.003,
                            "lateral_error_m": 1.614568,
                            "route_goal_lateral_error_m": 1.6155948,
                            "longitudinal_error_m": 1.932556,
                            "jerk_mps3": 6.7516858,
                            "final_pose": {
                                "x": 78.4,
                                "y": 56.2,
                                "z": 2.06,
                                "yaw_deg": 91.2,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            result_path = run_dir / "run_result.json"
            result_path.write_text(
                json.dumps(_route_recovery_kinematic_result(run_dir)),
                encoding="utf-8",
            )

            summary = write_bugpack(
                run_result_paths=[result_path],
                output_dir=root / "bugpack",
                owner="planning-control",
            )

            issue = Path(summary["issues"][0]["issue_path"]).read_text(encoding="utf-8")
            self.assertIn("closed-loop kinematic sanity", issue)
            self.assertIn("kinematic_sanity_passed", issue)
            self.assertIn("max_abs_roll_deg", issue)
            self.assertIn("closed_loop_vehicle_dynamics", issue)
            self.assertIn("closed-loop final pose", issue)

    def test_issue_markdown_labels_sim_failure_as_validation_finding_not_vehicle_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "run_route_recovery_failed"
            run_dir.mkdir(parents=True)
            result_path = run_dir / "run_result.json"
            result_path.write_text(
                json.dumps(_route_recovery_kinematic_result(run_dir)),
                encoding="utf-8",
            )

            summary = write_bugpack(
                run_result_paths=[result_path],
                output_dir=root / "bugpack",
                owner="planning-control",
            )

            issue = Path(summary["issues"][0]["issue_path"]).read_text(encoding="utf-8")
            self.assertIn("## Simulation validation interpretation", issue)
            self.assertIn(
                "not proof of a real-vehicle Autoware planning/control defect",
                issue,
            )
            self.assertIn("simulation_fidelity", issue)
            self.assertIn("Compare against real-vehicle or bag evidence", issue)

    def test_issue_markdown_labels_route_goal_mismatch_as_simulation_fidelity(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "run_speed40_route_geometry_failed"
            run_dir.mkdir(parents=True)
            runtime_dir = run_dir / "runtime_verification"
            runtime_dir.mkdir()
            (runtime_dir / "closed_loop_route_sync_20260511T162733.json").write_text(
                json.dumps(
                    {
                        "verdict": {"overall_passed": False, "movement_passed": True},
                        "summary": {
                            "route_service_calls_successful": True,
                            "all_service_calls_successful": True,
                            "max_speed_mps": 11.11,
                            "total_delta_m": 134.1,
                            "stopped_before_goal": True,
                            "kinematic_sanity_passed": True,
                            "max_abs_roll_deg": 2.67,
                            "max_abs_pitch_deg": 7.86,
                            "min_ego_z_m": 0.14,
                            "max_ego_z_m": 0.27,
                            "reached_near_goal": False,
                            "min_goal_distance_m": 60.99,
                            "lateral_error_m": 0.245,
                            "route_goal_lateral_error_m": 4.227222,
                            "longitudinal_error_m": 60.854,
                            "jerk_mps3": 2.42,
                            "final_map_location": {
                                "x": 254.145,
                                "y": -129.238,
                                "z": 0.168,
                                "yaw": -0.948,
                            },
                            "final_carla_waypoint": {
                                "road_id": 4,
                                "lane_id": 1,
                                "s": 152.724,
                                "center_map": {"x": 254.145, "y": -129.483},
                                "carla_lateral_error_m": 0.245,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            result_path = run_dir / "run_result.json"
            result_path.write_text(
                json.dumps(_route_goal_geometry_result(run_dir)),
                encoding="utf-8",
            )

            summary = write_bugpack(
                run_result_paths=[result_path],
                output_dir=root / "bugpack",
                owner="planning-control",
            )

            issue = Path(summary["issues"][0]["issue_path"]).read_text(encoding="utf-8")
            self.assertIn("[Simulation][SimulationFidelity][P1]", issue)
            self.assertIn("scenario_route_geometry", issue)
            self.assertIn("closed-loop final map location", issue)
            self.assertIn("closed-loop final CARLA waypoint", issue)
            self.assertIn("lane selection", issue)

    def test_runtime_failure_is_blocked_by_default_not_planning_bug(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "run_launch_failed"
            run_dir.mkdir(parents=True)
            result = _base_result(run_dir, status="launch_failed")
            result["runtime_health"] = {"passed": False}
            result["gate"] = {"gate_id": "planning_control_regression", "passed": False, "violations": []}
            result_path = run_dir / "run_result.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")

            summary = write_bugpack(
                run_result_paths=[result_path],
                output_dir=root / "bugpack",
                owner="planning-control",
            )

            self.assertEqual(summary["issue_count"], 0)
            self.assertEqual(summary["blocked_count"], 1)
            self.assertEqual(summary["blocked"][0]["classification"], "runtime_blocker")

    def test_dynamic_service_failure_is_blocked_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "run_dynamic_setup_failed"
            run_dir.mkdir(parents=True)
            result = _base_result(run_dir)
            result["runtime_evidence"] = {
                "ignored_dynamic_probe_attempts": [
                    {
                        "path": str(run_dir / "runtime_verification" / "l2_merge.json"),
                        "reason": "service_call_failed",
                        "invalid_steps": ["change_to_autonomous"],
                    }
                ],
                "dynamic_probe_attempts": [],
            }
            result_path = run_dir / "run_result.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")

            summary = write_bugpack(
                run_result_paths=[result_path],
                output_dir=root / "bugpack",
                owner="planning-control",
            )

            self.assertEqual(summary["issue_count"], 0)
            self.assertEqual(summary["blocked_count"], 1)
            self.assertEqual(summary["blocked"][0]["classification"], "integration_blocker")

    def test_write_bugpack_removes_stale_issue_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "run_failed"
            run_dir.mkdir(parents=True)
            result_path = run_dir / "run_result.json"
            result_path.write_text(json.dumps(_base_result(run_dir)), encoding="utf-8")
            output_dir = root / "bugpack"

            first = write_bugpack(
                run_result_paths=[result_path],
                output_dir=output_dir,
                owner="planning-control",
            )
            stale_issue = Path(first["issues"][0]["issue_path"])
            self.assertTrue(stale_issue.exists())

            result = _base_result(run_dir)
            result["runtime_evidence"] = {
                "ignored_dynamic_probe_attempts": [
                    {"reason": "service_call_failed", "invalid_steps": ["change_to_autonomous"]}
                ]
            }
            result_path.write_text(json.dumps(result), encoding="utf-8")
            second = write_bugpack(
                run_result_paths=[result_path],
                output_dir=output_dir,
                owner="planning-control",
            )

            self.assertEqual(second["issue_count"], 0)
            self.assertFalse(stale_issue.exists())
            self.assertEqual(list((output_dir / "issues").glob("*.md")), [])

    def test_issue_markdown_includes_dynamic_probe_diagnosis(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "run_failed"
            run_dir.mkdir(parents=True)
            result = _base_result(run_dir)
            result["runtime_evidence"] = {
                "dynamic_probe_attempts": [
                    {
                        "kind": "l2_close_cut_in",
                        "overall_passed": False,
                        "safety_passed": True,
                        "autoware_dynamic_actor_response_passed": False,
                        "moved": True,
                        "reaction_reason": None,
                        "actor_count_observed": 1.0,
                        "actor_count_spawned": 1.0,
                        "max_speed_mps": 2.03,
                        "min_speed_after_target_in_lane_mps": 1.04,
                        "total_delta_m": 60.1,
                        "failure_reasons": ["autoware_no_dynamic_response"],
                    }
                ]
            }
            result_path = run_dir / "run_result.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")

            summary = write_bugpack(
                run_result_paths=[result_path],
                output_dir=root / "bugpack",
                owner="planning-control",
            )

            issue_path = Path(summary["issues"][0]["issue_path"])
            issue = issue_path.read_text(encoding="utf-8")
            self.assertIn("## Runtime probe diagnosis", issue)
            self.assertIn("l2_close_cut_in", issue)
            self.assertIn("autoware_no_dynamic_response", issue)

    def test_issue_markdown_includes_closed_loop_service_failure_details(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "run_route_failed"
            run_dir.mkdir(parents=True)
            runtime_dir = run_dir / "runtime_verification"
            runtime_dir.mkdir()
            command_logs = run_dir / "command_logs"
            command_logs.mkdir()
            (command_logs / "06_start-autoware-stack.log").write_text(
                "\n".join(
                    [
                        "[control.autonomous_emergency_braking]: [AEB] waiting for imu message",
                        "[control.autonomous_emergency_braking]: [AEB] At least one path (IMU or predicted trajectory) is required for operation",
                        "[system.topic_state_monitor_vehicle_status_velocity_status]: /vehicle/status/velocity_status topic rate has dropped to the warning level.",
                    ]
                ),
                encoding="utf-8",
            )
            (runtime_dir / "closed_loop_route_sync_20260501T082306.json").write_text(
                json.dumps(
                    {
                        "verdict": {"overall_passed": False, "movement_passed": False},
                        "summary": {
                            "route_service_calls_successful": True,
                            "all_service_calls_successful": False,
                            "max_speed_mps": 0.39,
                            "total_delta_m": 1.4,
                            "stopped_before_goal": True,
                            "ros_telemetry": {
                                "tail_stats": {
                                    "tail_actuation_brake_cmd": {"mean": 0.8},
                                    "tail_control_acceleration_mps2": {"mean": -2.5},
                                    "tail_vehicle_velocity_mps": {"mean": 0.0},
                                }
                            },
                        },
                        "setup_checks": [
                            {
                                "step": "wait_operation_mode_autonomous_available",
                                "topic": "/api/operation_mode/state",
                                "passed": False,
                                "attempt_count": 11,
                                "blocker_snapshot": {
                                    "topics": {
                                        "operation_mode_state": {
                                            "sample_received": True,
                                            "returncode": 0,
                                            "output_tail": "is_autonomous_mode_available: false",
                                        },
                                        "fail_safe_mrm_state": {
                                            "sample_received": True,
                                            "returncode": 0,
                                            "output_tail": "state: 1 behavior: 1",
                                        },
                                    }
                                },
                            }
                        ],
                        "service_calls": [
                            {
                                "step": "change_to_autonomous",
                                "attempt": 5,
                                "service_failure_reason": "service_status_false",
                                "service_failure_message": "The target mode is not available.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = _base_result(run_dir)
            result["gate"] = {
                "gate_id": "sumo_dense_route_follow_bughunt",
                "passed": False,
                "violations": [
                    {
                        "metric": "route_completion",
                        "reason": "threshold_violation",
                        "actual": 0.0,
                        "op": ">=",
                        "threshold": 0.98,
                    }
                ],
            }
            result["kpis"] = {"route_completion": 0.0}
            result["runtime_evidence"] = {
                "ignored_attempts": [
                    {
                        "path": str(run_dir / "runtime_verification" / "closed_loop_route_sync.json"),
                        "reason": "service_call_failed",
                        "invalid_steps": ["set_route_points", "change_to_autonomous"],
                        "service_calls": [
                            {
                                "step": "set_route_points",
                                "returncode": 0,
                                "output_summary": "status=ResponseStatus(success=False, message='The planned route is empty.')",
                            },
                            {
                                "step": "change_to_autonomous",
                                "returncode": 0,
                                "output_summary": "status=ResponseStatus(success=False, message='The target mode is not available.')",
                            },
                        ],
                    }
                ],
            }
            result_path = run_dir / "run_result.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")

            summary = write_bugpack(
                run_result_paths=[result_path],
                output_dir=root / "bugpack",
                owner="planning-control",
            )

            issue = Path(summary["issues"][0]["issue_path"]).read_text(encoding="utf-8")
            self.assertIn("ignored closed-loop route probe", issue)
            self.assertIn("set_route_points", issue)
            self.assertIn("The planned route is empty", issue)
            self.assertIn("change_to_autonomous", issue)
            self.assertIn("closed-loop setup blocker", issue)
            self.assertIn("is_autonomous_mode_available: false", issue)
            self.assertIn("fail_safe_mrm_state", issue)
            self.assertIn("aeb_waiting_for_imu", issue)


if __name__ == "__main__":
    unittest.main()
