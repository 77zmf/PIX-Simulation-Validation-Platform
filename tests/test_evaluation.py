from __future__ import annotations

import unittest
from pathlib import Path

from src.simctl.evaluation import evaluate_metrics
from src.simctl.models import KpiGate


class EvaluationTests(unittest.TestCase):
    def test_failure_labels_are_filtered_to_violated_metrics(self) -> None:
        gate = KpiGate(
            gate_id="planning_control_l3_occluded_pedestrian",
            description="test gate",
            metrics={
                "route_completion": {"op": ">=", "value": 0.95},
                "collision_count": {"op": "<=", "value": 0},
                "min_ttc_sec": {"op": ">=", "value": 1.8},
                "dynamic_actor_response": {"op": ">=", "value": 1.0},
                "sensor_topic_coverage": {"op": ">=", "value": 1.0},
            },
            failure_labels=[
                "route_completion_failure",
                "collision_failure",
                "pedestrian_perception_failure",
                "pedestrian_yield_failure",
                "robobus_sensor_bridge_failure",
            ],
            gate_path=Path("evaluation/kpi_gates/planning_control_l3_occluded_pedestrian.yaml"),
        )

        result = evaluate_metrics(
            {
                "route_completion": 1.0,
                "collision_count": 0.0,
                "min_ttc_sec": 0.93,
                "dynamic_actor_response": 1.0,
                "sensor_topic_coverage": 1.0,
            },
            gate,
        )

        self.assertFalse(result["passed"])
        self.assertEqual([item["metric"] for item in result["violations"]], ["min_ttc_sec"])
        self.assertEqual(result["failure_labels"], ["pedestrian_yield_failure"])

    def test_missing_sensor_metrics_map_to_sensor_failure_label(self) -> None:
        gate = KpiGate(
            gate_id="robobus117th_sensor_actor_bridge",
            description="test gate",
            metrics={
                "route_completion": {"op": ">=", "value": 0.95},
                "sensor_topic_coverage": {"op": ">=", "value": 1.0},
                "sensor_sample_coverage": {"op": ">=", "value": 1.0},
            },
            failure_labels=[
                "robobus_sensor_bridge_failure",
                "actor_bridge_perception_failure",
                "planning_control_gate_failure",
            ],
            gate_path=Path("evaluation/kpi_gates/robobus117th_sensor_actor_bridge.yaml"),
        )

        result = evaluate_metrics({"route_completion": 1.0}, gate)

        self.assertFalse(result["passed"])
        self.assertEqual(
            [item["metric"] for item in result["violations"]],
            ["sensor_topic_coverage", "sensor_sample_coverage"],
        )
        self.assertEqual(result["failure_labels"], ["robobus_sensor_bridge_failure"])

    def test_dynamic_response_failure_prefers_planning_control_label(self) -> None:
        gate = KpiGate(
            gate_id="robobus117th_sensor_actor_bridge",
            description="test gate",
            metrics={
                "route_completion": {"op": ">=", "value": 0.95},
                "dynamic_actor_response": {"op": ">=", "value": 1.0},
            },
            failure_labels=[
                "robobus_sensor_bridge_failure",
                "actor_bridge_perception_failure",
                "planning_control_gate_failure",
            ],
            gate_path=Path("evaluation/kpi_gates/robobus117th_sensor_actor_bridge.yaml"),
        )

        result = evaluate_metrics({"route_completion": 1.0, "dynamic_actor_response": 0.0}, gate)

        self.assertFalse(result["passed"])
        self.assertEqual(result["failure_labels"], ["planning_control_gate_failure"])

    def test_robobus_bbox_failure_maps_to_collision_label(self) -> None:
        gate = KpiGate(
            gate_id="robobus117th_vehicle_blueprint_acceptance",
            description="test gate",
            metrics={
                "robobus_blueprint_found": {"op": ">=", "value": 1.0},
                "robobus_bbox_plausible": {"op": ">=", "value": 1.0},
                "robobus_attached_sensor_count": {"op": ">=", "value": 13.0},
            },
            failure_labels=[
                "robobus_blueprint_failure",
                "robobus_bbox_collision_failure",
                "robobus_sensor_attachment_failure",
            ],
            gate_path=Path("evaluation/kpi_gates/robobus117th_vehicle_blueprint_acceptance.yaml"),
        )

        result = evaluate_metrics(
            {
                "robobus_blueprint_found": 1.0,
                "robobus_bbox_plausible": 0.0,
                "robobus_attached_sensor_count": 13.0,
            },
            gate,
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["failure_labels"], ["robobus_bbox_collision_failure"])

    def test_kinematic_sanity_metrics_map_to_kinematic_label(self) -> None:
        gate = KpiGate(
            gate_id="planning_control_smoke_kinematic_sanity",
            description="test gate",
            metrics={
                "route_completion": {"op": ">=", "value": 0.95},
                "kinematic_sanity_passed": {"op": ">=", "value": 1.0},
                "max_abs_roll_deg": {"op": "<=", "value": 30.0},
            },
            failure_labels=[
                "route_completion_failure",
                "planning_control_gate_failure",
                "kinematic_sanity_failure",
            ],
            gate_path=Path("evaluation/kpi_gates/planning_control_smoke_kinematic_sanity.yaml"),
        )

        result = evaluate_metrics(
            {"route_completion": 1.0, "kinematic_sanity_passed": 0.0, "max_abs_roll_deg": 178.0},
            gate,
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["failure_labels"], ["kinematic_sanity_failure"])

    def test_robobus_qiyu_spawn_metrics_map_to_physics_asset_label(self) -> None:
        gate = KpiGate(
            gate_id="robobus117th_qiyu_spawn_stability",
            description="test gate",
            metrics={
                "robobus_qiyu_spawn_stability_passed": {"op": ">=", "value": 1.0},
                "robobus_qiyu_spawn_stable_count": {"op": ">=", "value": 1.0},
            },
            failure_labels=[
                "robobus_qiyu_spawn_instability",
                "robobus_physics_asset_failure",
                "carla_vehicle_asset_failure",
            ],
            gate_path=Path("evaluation/kpi_gates/robobus117th_qiyu_spawn_stability.yaml"),
        )

        result = evaluate_metrics(
            {"robobus_qiyu_spawn_stability_passed": 0.0, "robobus_qiyu_spawn_stable_count": 0.0},
            gate,
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["failure_labels"], ["robobus_qiyu_spawn_instability"])


if __name__ == "__main__":
    unittest.main()
