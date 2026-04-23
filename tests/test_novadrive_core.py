from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novadrive.control import PurePursuitPidController
from novadrive.foundation import DetectedObject, EgoState, Vector3, to_jsonable
from novadrive.perception.bevfusion_provider import BEVFusionProvider
from novadrive.planning import BehaviorPlanner, ReferenceLinePlanner
from novadrive.reasoning import ConstantVelocityPredictor, NearestNeighborTracker, RiskAssessor
from novadrive.runtime.scenario_loader import load_novadrive_scenario
from simctl.runtime_evidence import collect_runtime_evidence


class NovaDriveCoreTests(unittest.TestCase):
    def test_scenario_loader_reads_novadrive_coordinates(self) -> None:
        scenario = load_novadrive_scenario(REPO_ROOT / "scenarios" / "l2" / "novadrive_merge.yaml")
        self.assertEqual(scenario.scenario_id, "novadrive_l2_merge")
        self.assertEqual(scenario.start.y, 2.0201120376586914)
        self.assertEqual(len(scenario.actors), 1)
        self.assertEqual(scenario.actors[0].name, "merging_audi_tt")

    def test_bevfusion_provider_accepts_standard_json(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "detections.json"
            path.write_text(
                json.dumps(
                    {
                        "timestamp": 10.0,
                        "frame_id": "lidar",
                        "detections": [
                            {
                                "object_id": "car-1",
                                "class_name": "car",
                                "score": 0.91,
                                "center_xyz": [12.0, 1.5, 0.0],
                                "size_lwh": [4.5, 1.9, 1.7],
                                "yaw": 0.1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            snapshot = BEVFusionProvider(str(path), max_age_sec=60.0).detect(10.1)

        self.assertTrue(snapshot.healthy)
        self.assertEqual(len(snapshot.detections), 1)
        self.assertEqual(snapshot.detections[0].center.x, 12.0)

    def test_reasoning_planning_control_pipeline(self) -> None:
        ego = EgoState(1.0, "carla_world", Vector3(0.0, 0.0, 0.0), yaw_rad=0.0, velocity_mps=4.0)
        detection = DetectedObject(
            timestamp=1.0,
            frame_id="carla_world",
            source="test",
            class_name="car",
            score=1.0,
            center=Vector3(12.0, 0.5, 0.0),
            size_lwh=Vector3(4.0, 2.0, 1.5),
            yaw_rad=0.0,
            velocity=Vector3(0.0, 0.0, 0.0),
        )
        tracker = NearestNeighborTracker()
        tracks = tracker.update([detection])
        predictions = ConstantVelocityPredictor().predict(tracks)
        risk = RiskAssessor(safe_ttc_sec=3.5).assess(ego, predictions)
        behavior = BehaviorPlanner(cruise_speed_mps=4.0).decide(risk, route_completion=0.1)
        trajectory = ReferenceLinePlanner().plan(ego, Vector3(40.0, 0.0, 0.0), behavior)
        command = PurePursuitPidController().control(ego, trajectory)

        self.assertEqual(len(tracks), 1)
        self.assertTrue(risk.collision_risk)
        self.assertIn(behavior.mode, {"YIELD", "BRAKE"})
        self.assertGreaterEqual(command.brake, 0.0)
        self.assertLessEqual(abs(command.steer), 1.0)
        self.assertIn("throttle", to_jsonable(command))

    def test_runtime_evidence_collects_novadrive_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run"
            runtime_dir = run_dir / "runtime_verification"
            runtime_dir.mkdir(parents=True)
            (runtime_dir / "novadrive_novadrive_l0_smoke_20260421T000000.json").write_text(
                json.dumps(
                    {
                        "kind": "novadrive_run",
                        "scenario_id": "novadrive_l0_smoke",
                        "perception_source": "mock",
                        "overall_passed": True,
                        "summary": {"runtime_status": "COMPLETED", "sample_count": 20},
                        "metrics": {
                            "route_completion": 1.0,
                            "collision_count": 0.0,
                            "min_ttc_sec": 999.0,
                            "min_distance_m": 999.0,
                            "control_rate_hz": 20.0,
                            "perception_frame_rate_hz": 20.0,
                            "trajectory_valid_ratio": 1.0,
                            "novadrive_runtime_passed": 1.0,
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = collect_runtime_evidence(run_dir, {"scenario_params": {"traffic_profile": {"mode": "empty"}}})

        self.assertEqual(summary["novadrive_attempt_count"], 1)
        self.assertEqual(summary["successful_novadrive_count"], 1)
        self.assertEqual(summary["metrics"]["route_completion"], 1.0)
        self.assertEqual(summary["metric_sources"]["route_completion"], "novadrive_runtime")


if __name__ == "__main__":
    unittest.main()

