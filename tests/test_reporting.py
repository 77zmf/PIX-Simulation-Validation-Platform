from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.reporting import aggregate_run_results, render_markdown


def _shadow_run_result(
    *,
    run_id: str,
    scenario_id: str,
    profile_id: str,
    gate_id: str,
    kpis: dict[str, float],
    profile_specific: list[str],
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "stack": "stable",
        "status": "passed",
        "gate": {"passed": True, "gate_id": gate_id, "violations": []},
        "kpis": kpis,
        "resolved_profiles": {
            "algorithm": {
                "profile_id": profile_id,
                "interface_contract": {
                    "comparison_metrics": {
                        "common": [
                            "route_completion",
                            "collision_count",
                            "trajectory_divergence_m",
                            "min_ttc_sec",
                            "planner_disengagement_triggers",
                        ],
                        "profile_specific": profile_specific,
                    }
                },
            }
        },
    }


class ReportingTests(unittest.TestCase):
    def test_aggregate_run_results_builds_shadow_comparison_summary(self) -> None:
        summary = aggregate_run_results(
            [
                _shadow_run_result(
                    run_id="run-uniad",
                    scenario_id="carla0915_public_road_bevfusion_uniad_unprotected_left",
                    profile_id="e2e_bevfusion_uniad_shadow",
                    gate_id="e2e_bevfusion_uniad_shadow_gate",
                    kpis={
                        "route_completion": 1.0,
                        "collision_count": 0.0,
                        "trajectory_divergence_m": 0.42,
                        "min_ttc_sec": 2.1,
                        "planner_disengagement_triggers": 0.0,
                        "comfort_cost": 0.21,
                    },
                    profile_specific=["comfort_cost"],
                ),
                _shadow_run_result(
                    run_id="run-vadv2",
                    scenario_id="carla0915_public_road_bevfusion_vadv2_occluded_pedestrian",
                    profile_id="e2e_bevfusion_vadv2_shadow",
                    gate_id="e2e_bevfusion_vadv2_shadow_gate",
                    kpis={
                        "route_completion": 0.98,
                        "collision_count": 0.0,
                        "trajectory_divergence_m": 0.51,
                        "min_ttc_sec": 2.0,
                        "planner_disengagement_triggers": 1.0,
                        "shadow_uncertainty_coverage": 0.88,
                    },
                    profile_specific=["shadow_uncertainty_coverage"],
                ),
            ]
        )

        shadow = summary["shadow_comparison"]
        self.assertIsNotNone(shadow)
        self.assertEqual(shadow["profile_count"], 2)
        self.assertEqual(
            shadow["shared_metric_order"],
            [
                "route_completion",
                "collision_count",
                "trajectory_divergence_m",
                "min_ttc_sec",
                "planner_disengagement_triggers",
            ],
        )

        profiles = {profile["profile_id"]: profile for profile in shadow["profiles"]}
        self.assertEqual(profiles["e2e_bevfusion_uniad_shadow"]["comparison_ready_runs"], 1)
        self.assertEqual(profiles["e2e_bevfusion_uniad_shadow"]["shared_metric_stats"]["trajectory_divergence_m"]["avg"], 0.42)
        self.assertEqual(profiles["e2e_bevfusion_vadv2_shadow"]["shared_metric_stats"]["planner_disengagement_triggers"]["avg"], 1.0)
        self.assertEqual(profiles["e2e_bevfusion_uniad_shadow"]["profile_specific_metric_stats"]["comfort_cost"]["avg"], 0.21)
        self.assertEqual(
            profiles["e2e_bevfusion_vadv2_shadow"]["profile_specific_metric_stats"]["shadow_uncertainty_coverage"]["avg"],
            0.88,
        )
        self.assertEqual(
            profiles["e2e_bevfusion_uniad_shadow"]["shared_metric_verdicts"]["route_completion"],
            {
                "threshold": ">=0.96",
                "passed_runs": 1,
                "failed_runs": 0,
                "missing_runs": 0,
                "run_count": 1,
            },
        )
        self.assertEqual(
            profiles["e2e_bevfusion_vadv2_shadow"]["shared_metric_coverage"]["trajectory_divergence_m"]["ratio"], 1.0
        )
        self.assertEqual(profiles["e2e_bevfusion_uniad_shadow"]["comparison_gaps"], [])

    def test_render_markdown_includes_shadow_comparison_section(self) -> None:
        summary = aggregate_run_results(
            [
                _shadow_run_result(
                    run_id="run-uniad",
                    scenario_id="carla0915_public_road_bevfusion_uniad_unprotected_left",
                    profile_id="e2e_bevfusion_uniad_shadow",
                    gate_id="e2e_bevfusion_uniad_shadow_gate",
                    kpis={
                        "route_completion": 1.0,
                        "collision_count": 0.0,
                        "trajectory_divergence_m": 0.42,
                        "min_ttc_sec": 2.1,
                        "planner_disengagement_triggers": 0.0,
                        "comfort_cost": 0.21,
                    },
                    profile_specific=["comfort_cost"],
                )
            ]
        )

        markdown = render_markdown(summary)
        self.assertIn("## Shadow Comparison", markdown)
        self.assertIn("`e2e_bevfusion_uniad_shadow`", markdown)
        self.assertIn("trajectory_divergence_m avg", markdown)
        self.assertIn("### Profile-Specific Signals", markdown)
        self.assertIn("### Gate Verdicts", markdown)
        self.assertIn("`route_completion` | `>=0.96` | 1 | 0 | 0", markdown)
        self.assertIn("### Comparison Gaps", markdown)
        self.assertIn("- None", markdown)

    def test_shadow_comparison_reports_missing_metrics_as_gaps(self) -> None:
        summary = aggregate_run_results(
            [
                _shadow_run_result(
                    run_id="run-vadv2-gap",
                    scenario_id="carla0915_public_road_bevfusion_vadv2_gap_case",
                    profile_id="e2e_bevfusion_vadv2_shadow",
                    gate_id="e2e_bevfusion_vadv2_shadow_gate",
                    kpis={
                        "route_completion": 0.97,
                        "collision_count": 0.0,
                        "trajectory_divergence_m": 0.61,
                        "planner_disengagement_triggers": 1.0,
                    },
                    profile_specific=["shadow_uncertainty_coverage"],
                )
            ]
        )

        shadow = summary["shadow_comparison"]
        profile = shadow["profiles"][0]
        self.assertEqual(profile["comparison_ready_runs"], 0)
        self.assertEqual(
            profile["shared_metric_verdicts"]["min_ttc_sec"],
            {
                "threshold": ">=1.9",
                "passed_runs": 0,
                "failed_runs": 0,
                "missing_runs": 1,
                "run_count": 1,
            },
        )
        self.assertEqual(
            profile["comparison_gaps"],
            [
                {
                    "run_id": "run-vadv2-gap",
                    "scenario_id": "carla0915_public_road_bevfusion_vadv2_gap_case",
                    "missing_shared_metrics": ["min_ttc_sec"],
                    "missing_profile_specific_metrics": ["shadow_uncertainty_coverage"],
                }
            ],
        )
        markdown = render_markdown(summary)
        self.assertIn("missing shared: `min_ttc_sec`", markdown)
        self.assertIn("missing profile-specific: `shadow_uncertainty_coverage`", markdown)


if __name__ == "__main__":
    unittest.main()
