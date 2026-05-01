from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = REPO_ROOT / "ops" / "runtime_probes" / "carla_actor_visual_capture.py"

spec = importlib.util.spec_from_file_location("carla_actor_visual_capture", PROBE_PATH)
carla_actor_visual_capture = importlib.util.module_from_spec(spec)
sys.modules["carla_actor_visual_capture"] = carla_actor_visual_capture
assert spec.loader is not None
spec.loader.exec_module(carla_actor_visual_capture)


class _FakeActor:
    def __init__(self, actor_id: int, type_id: str, role_name: str) -> None:
        self.id = actor_id
        self.type_id = type_id
        self.attributes = {"role_name": role_name}


class CarlaActorVisualCaptureTests(unittest.TestCase):
    def test_select_npc_actors_prefers_sumo_driver_role(self) -> None:
        actors = [
            _FakeActor(1, "vehicle.pixmoving.robobus", "ego_vehicle"),
            _FakeActor(2, "vehicle.ford.mustang", "sumo_driver"),
            _FakeActor(3, "vehicle.audi.tt", "background"),
            _FakeActor(4, "vehicle.mini.cooper_s", "sumo_shadow"),
        ]

        selected = carla_actor_visual_capture.select_npc_actors(
            actors,
            ego_role_name="ego_vehicle",
            npc_role_name="sumo_driver",
            npc_role_prefix="sumo",
            include_non_ego_fallback=True,
        )

        self.assertEqual([actor.id for actor in selected], [2, 4])

    def test_select_npc_actors_can_fallback_to_non_ego(self) -> None:
        actors = [
            _FakeActor(1, "vehicle.pixmoving.robobus", "ego_vehicle"),
            _FakeActor(2, "vehicle.ford.mustang", "background"),
            _FakeActor(3, "vehicle.audi.tt", "npc"),
        ]

        selected = carla_actor_visual_capture.select_npc_actors(
            actors,
            ego_role_name="ego_vehicle",
            npc_role_name="sumo_driver",
            npc_role_prefix="sumo",
            include_non_ego_fallback=True,
        )

        self.assertEqual([actor.id for actor in selected], [2, 3])

    def test_build_metrics_uses_numeric_runtime_evidence_fields(self) -> None:
        metrics = carla_actor_visual_capture._build_metrics(
            vehicle_count=6,
            ego_seen=True,
            npc_count=5,
            capture_count=11,
        )

        self.assertEqual(metrics["carla_actor_visual_vehicle_count"], 6.0)
        self.assertEqual(metrics["carla_actor_visual_ego_seen"], 1.0)
        self.assertEqual(metrics["carla_actor_visual_npc_count"], 5.0)
        self.assertEqual(metrics["carla_actor_visual_capture_count"], 11.0)

    def test_poll_vehicle_actors_waits_until_ego_and_sumo_npc_exist(self) -> None:
        ego = _FakeActor(1, "vehicle.pixmoving.robobus", "ego_vehicle")
        npc = _FakeActor(2, "vehicle.ford.mustang", "sumo_driver")
        snapshots = [[], [ego, npc]]

        def actor_fetcher() -> list[_FakeActor]:
            if snapshots:
                return snapshots.pop(0)
            return [ego, npc]

        with mock.patch.object(
            carla_actor_visual_capture.time,
            "monotonic",
            side_effect=[0.0, 0.0],
        ), mock.patch.object(carla_actor_visual_capture.time, "sleep") as sleep_mock:
            actors, ego_actor, npc_actors, attempts = carla_actor_visual_capture.poll_vehicle_actors(
                actor_fetcher,
                ego_role_name="ego_vehicle",
                npc_role_name="sumo_driver",
                npc_role_prefix="sumo",
                include_non_ego_fallback=True,
                max_npcs=3,
                min_npcs=1,
                timeout_sec=8.0,
                poll_interval_sec=0.5,
            )

        self.assertEqual([actor.id for actor in actors], [1, 2])
        self.assertEqual(ego_actor.id, 1)
        self.assertEqual([actor.id for actor in npc_actors], [2])
        self.assertEqual(
            attempts,
            [
                {"vehicle_count": 0, "ego_seen": False, "npc_count": 0},
                {"vehicle_count": 2, "ego_seen": True, "npc_count": 1},
            ],
        )
        sleep_mock.assert_called_once_with(0.5)

    def test_poll_vehicle_actors_returns_last_snapshot_after_timeout(self) -> None:
        actor = _FakeActor(9, "vehicle.pixmoving.robobus", "ego_vehicle")

        with mock.patch.object(
            carla_actor_visual_capture.time,
            "monotonic",
            side_effect=[0.0, 0.0],
        ), mock.patch.object(carla_actor_visual_capture.time, "sleep") as sleep_mock:
            actors, ego_actor, npc_actors, attempts = carla_actor_visual_capture.poll_vehicle_actors(
                lambda: [actor],
                ego_role_name="ego_vehicle",
                npc_role_name="sumo_driver",
                npc_role_prefix="sumo",
                include_non_ego_fallback=False,
                max_npcs=3,
                min_npcs=1,
                timeout_sec=0.0,
                poll_interval_sec=0.5,
            )

        self.assertEqual([item.id for item in actors], [9])
        self.assertEqual(ego_actor.id, 9)
        self.assertEqual(npc_actors, [])
        self.assertEqual(
            attempts,
            [{"vehicle_count": 1, "ego_seen": True, "npc_count": 0}],
        )
        sleep_mock.assert_not_called()

    def test_write_artifacts_uses_metric_probe_directory(self) -> None:
        payload = {
            "overall_passed": True,
            "blocked_reason": None,
            "metrics": {
                "carla_actor_visual_vehicle_count": 6.0,
                "carla_actor_visual_ego_seen": 1.0,
                "carla_actor_visual_npc_count": 5.0,
                "carla_actor_visual_capture_count": 11.0,
            },
            "summary": {
                "vehicle_count": 6,
                "ego_seen": True,
                "ego_id": 202,
                "npc_count": 5,
                "capture_count": 11,
                "image_dir": "/tmp/images",
            },
            "captures": [
                {
                    "actor_id": 200,
                    "type_id": "vehicle.ford.mustang",
                    "role_name": "sumo_driver",
                    "close_path": "/tmp/images/npc_01_close.png",
                    "side_path": "/tmp/images/npc_01_side.png",
                }
            ],
            "group_capture": {"path": "/tmp/images/npc_group_topdown_all_sumo_driver.png"},
        }
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run"
            run_dir.mkdir()

            outputs = carla_actor_visual_capture.write_artifacts(run_dir, payload)

            artifact = Path(outputs["artifact"])
            summary = Path(outputs["summary_path"])
            self.assertIn("metric_probe_carla_actor_visual_", str(artifact.parent))
            self.assertTrue(artifact.exists())
            self.assertTrue(summary.exists())
            saved = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(saved["metrics"]["carla_actor_visual_npc_count"], 5.0)
            saved_summary = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(saved_summary["summary"]["capture_count"], 11)


if __name__ == "__main__":
    unittest.main()
