from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_probe():
    path = REPO_ROOT / "ops" / "runtime_probes" / "planning_roadtest_replay_probe.py"
    spec = importlib.util.spec_from_file_location("planning_roadtest_replay_probe", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_manifest(path: Path, cases: list[dict[str, object]]) -> None:
    lines = [
        "asset_id: planning_road_test_failcases_202604",
        "bundle_id: planning_road_test_failcases_202604",
        "cases:",
    ]
    for case in cases:
        lines.extend(
            [
                f"  - case_id: {case['case_id']}",
                f"    local_evidence_root: {case['local_evidence_root']}",
                f"    simulation_target: {case['simulation_target']}",
                f"    symptom: {case['symptom']}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class PlanningRoadtestReplayProbeTests(unittest.TestCase):
    def test_trajectory_jump_profile_extracts_max_jump_and_validator_invalid_count(self) -> None:
        probe = _load_probe()
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            jump_case = root / "jump_case"
            jump_case.mkdir()
            (jump_case / "analysis_summary.json").write_text(
                json.dumps(
                    {
                        "state": {"emergency_true_count": 0},
                        "trajectory_jumps_top": [
                            {"topic": "/planning/scenario_planning/trajectory", "jump_m": 4.5},
                            {"topic": "/planning/path_candidate/static_obstacle_avoidance", "jump_m": 57.39},
                        ],
                        "validator": {
                            "invalid_messages": 101,
                            "peaks": {"lateral_shift": {"value": 0.4}},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (jump_case / "analysis_report.md").write_text(
                "The planning report observed path and trajectory first-point jumps around 1761.972 m.\n",
                encoding="utf-8",
            )
            manifest = root / "manifest.yaml"
            _write_manifest(
                manifest,
                [
                    {
                        "case_id": "planning_20260421145245_trajectory_jump",
                        "local_evidence_root": jump_case,
                        "simulation_target": "route_churn_lane_change_trajectory_jump",
                        "symptom": "trajectory_jump",
                    }
                ],
            )

            payload = probe.run_probe(
                Namespace(
                    run_dir=str(root / "run"),
                    manifest=str(manifest),
                    profile="trajectory_jump",
                    case_id=[],
                )
            )

        self.assertEqual(payload["profile"], "trajectory_jump")
        self.assertFalse(payload["overall_passed"])
        self.assertEqual(payload["metrics"]["planning_validator_invalid_count"], 101.0)
        self.assertEqual(payload["metrics"]["trajectory_jump_max_m"], 1761.972)
        self.assertEqual(payload["metrics"]["trajectory_silence_sec"], 0.0)
        self.assertIn("trajectory_jump_max_m", payload["blocked_reason"])
        self.assertEqual(payload["summary"]["case_count"], 1)

    def test_dropout_and_out_of_lane_profiles_extract_replay_metrics(self) -> None:
        probe = _load_probe()
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            dropout_case = root / "dropout_case"
            dropout_case.mkdir()
            (dropout_case / "no_trajectory_diagnostics.json").write_text(
                json.dumps(
                    {
                        "topics": {
                            "/planning/scenario_planning/trajectory": {
                                "silence_after_last_to_event_end_s": 48.9,
                            }
                        },
                        "validator": {"invalid_messages": 231},
                    }
                ),
                encoding="utf-8",
            )
            route_empty_case = root / "route_empty_case"
            route_empty_case.mkdir()
            (route_empty_case / "analysis_report.md").write_text(
                "ADAPI planned route is empty and behavior_path_planning_container crashed with exit code -11.\n",
                encoding="utf-8",
            )
            brake_case = root / "brake_case"
            brake_case.mkdir()
            (brake_case / "analysis_report.md").write_text(
                "Planning validator detects trajectory shift around 0.856m. "
                "Max lateral jerk is 115.611 m/s^3. MRM emergency stop and brake takeover were observed.\n",
                encoding="utf-8",
            )
            manifest = root / "manifest.yaml"
            _write_manifest(
                manifest,
                [
                    {
                        "case_id": "planning_20260421145630_no_trajectory",
                        "local_evidence_root": dropout_case,
                        "simulation_target": "trajectory_publication_dropout",
                        "symptom": "no_trajectory_planning",
                    },
                    {
                        "case_id": "planning_202604221647_route_empty_no_trajectory",
                        "local_evidence_root": route_empty_case,
                        "simulation_target": "route_handler_lateral_neighbor_loop",
                        "symptom": "route_empty_no_trajectory_behavior_path_planner_crash",
                    },
                    {
                        "case_id": "planning_20260417135420_brake_takeover",
                        "local_evidence_root": brake_case,
                        "simulation_target": "out_of_lane_slowdown_failure_lateral_jerk_brake_takeover",
                        "symptom": "out_of_lane_lateral_shift_emergency_brake_takeover",
                    },
                ],
            )

            dropout_payload = probe.run_probe(
                Namespace(
                    run_dir=str(root / "dropout_run"),
                    manifest=str(manifest),
                    profile="trajectory_dropout",
                    case_id=[],
                )
            )
            brake_payload = probe.run_probe(
                Namespace(
                    run_dir=str(root / "brake_run"),
                    manifest=str(manifest),
                    profile="out_of_lane_brake_takeover",
                    case_id=[],
                )
            )

        self.assertEqual(dropout_payload["metrics"]["trajectory_silence_sec"], 48.9)
        self.assertEqual(dropout_payload["metrics"]["route_empty_count"], 1.0)
        self.assertEqual(dropout_payload["metrics"]["planner_container_crash_count"], 1.0)
        self.assertEqual(dropout_payload["metrics"]["planning_validator_invalid_count"], 231.0)
        self.assertFalse(dropout_payload["overall_passed"])
        self.assertEqual(brake_payload["metrics"]["lateral_shift_m"], 0.856)
        self.assertEqual(brake_payload["metrics"]["max_lateral_jerk_mps3"], 115.611)
        self.assertEqual(brake_payload["metrics"]["control_emergency_true_count"], 1.0)
        self.assertEqual(brake_payload["metrics"]["brake_takeover_count"], 1.0)
        self.assertFalse(brake_payload["overall_passed"])

    def test_lateral_shift_prefers_validator_peak_over_overlay_invalid_event_outliers(self) -> None:
        probe = _load_probe()
        evidence = probe.CaseEvidence(case_id="case", root=Path("/tmp/case"))
        evidence.json_payloads.append(
            (
                Path("/tmp/case/planning_viz_overlay_stats.json"),
                {
                    "validator_invalid_events": [
                        {"invalid_count": 96, "lateral_shift_m": 499.0014022121195}
                    ]
                },
            )
        )
        evidence.json_payloads.append(
            (
                Path("/tmp/case/analysis_summary.json"),
                {"validator": {"peaks": {"lateral_shift": {"value": 0.856}}}},
            )
        )

        self.assertEqual(probe._case_lateral_shift(evidence), 0.856)

    def test_lateral_shift_text_parser_does_not_capture_timestamps(self) -> None:
        probe = _load_probe()
        evidence = probe.CaseEvidence(case_id="case", root=Path("/tmp/case"))
        evidence.text_payloads.append(
            (
                Path("/tmp/case/analysis_report.md"),
                "Repeated warnings do not directly explain the lateral trajectory shift:\n"
                "- `13:54:46.045`: invalid field `is_valid_trajectory_shift`, "
                "`distance_deviation=0.871 m`, `lateral_shift=0.856 m`.\n",
            )
        )

        self.assertEqual(probe._case_lateral_shift(evidence), 0.856)

    def test_out_of_lane_profile_does_not_match_generic_brake_takeover_case(self) -> None:
        probe = _load_probe()
        generic_brake_case = {
            "case_id": "planning_20260427100413_trajectory_issue",
            "symptom": "trajectory_issue_with_brake_takeover",
            "simulation_target": "right_lane_change_static_obstacle_trajectory_jump",
        }
        out_of_lane_case = {
            "case_id": "planning_20260417135420_brake_takeover",
            "symptom": "out_of_lane_lateral_shift_emergency_brake_takeover",
            "simulation_target": "out_of_lane_slowdown_failure_lateral_jerk_brake_takeover",
        }

        self.assertFalse(probe._case_matches_profile(generic_brake_case, "out_of_lane_brake_takeover"))
        self.assertTrue(probe._case_matches_profile(out_of_lane_case, "out_of_lane_brake_takeover"))

    def test_invalid_count_deduplicates_multiple_summaries_for_same_case(self) -> None:
        probe = _load_probe()
        evidence = probe.CaseEvidence(case_id="case", root=Path("/tmp/case"))
        evidence.json_payloads.extend(
            [
                (Path("/tmp/case/analysis_summary.json"), {"validator": {"invalid_messages": 231}}),
                (Path("/tmp/case/no_trajectory_diagnostics.json"), {"validator": {"invalid_messages": 231}}),
            ]
        )

        self.assertEqual(probe._case_invalid_count(evidence), 231.0)

    def test_write_artifacts_uses_metric_probe_contract(self) -> None:
        probe = _load_probe()
        payload = {
            "profile": "trajectory_jump",
            "overall_passed": False,
            "blocked_reason": "thresholds_failed:trajectory_jump_max_m",
            "missing_metrics": [],
            "missing_topics": [],
            "sample_missing_topics": [],
            "metrics": {"trajectory_jump_max_m": 57.39},
            "summary": {"case_count": 1},
        }
        with tempfile.TemporaryDirectory() as tempdir:
            outputs = probe.write_artifacts(Path(tempdir), payload)
            artifact = Path(outputs["artifact"])
            summary = Path(outputs["summary_path"])

            self.assertIn("metric_probe_planning_roadtest_replay_", str(artifact.parent))
            self.assertTrue(artifact.exists())
            self.assertTrue(summary.exists())
            saved = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(saved["metrics"]["trajectory_jump_max_m"], 57.39)


if __name__ == "__main__":
    unittest.main()
