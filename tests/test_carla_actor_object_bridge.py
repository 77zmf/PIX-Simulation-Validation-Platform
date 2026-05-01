from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = REPO_ROOT / "stack" / "stable" / "carla_actor_object_bridge.py"

spec = importlib.util.spec_from_file_location("carla_actor_object_bridge", BRIDGE_PATH)
carla_actor_object_bridge = importlib.util.module_from_spec(spec)
sys.modules["carla_actor_object_bridge"] = carla_actor_object_bridge
assert spec.loader is not None
spec.loader.exec_module(carla_actor_object_bridge)


class _FakeActor:
    def __init__(self, type_id: str, role_name: str) -> None:
        self.type_id = type_id
        self.attributes = {"role_name": role_name}


class _FakeActorList(list):
    def filter(self, pattern: str) -> "_FakeActorList":
        if pattern == "vehicle.*":
            return _FakeActorList(actor for actor in self if actor.type_id.startswith("vehicle."))
        if pattern == "walker.pedestrian.*":
            return _FakeActorList(actor for actor in self if actor.type_id.startswith("walker.pedestrian."))
        return _FakeActorList()


class _FakeWorld:
    def __init__(self) -> None:
        self.actor_calls = 0

    def get_actors(self) -> _FakeActorList:
        self.actor_calls += 1
        if self.actor_calls == 1:
            raise RuntimeError("time-out of 10000ms while waiting for the simulator")
        return _FakeActorList(
            [
                _FakeActor("vehicle.pixmoving.robobus", "ego_vehicle"),
                _FakeActor("vehicle.audi.tt", "target"),
                _FakeActor("walker.pedestrian.0001", "pedestrian"),
            ]
        )


class _FakeClient:
    def __init__(self) -> None:
        self.world = _FakeWorld()

    def get_world(self) -> _FakeWorld:
        return self.world


class CarlaActorObjectBridgeTests(unittest.TestCase):
    def test_actor_query_retries_transient_carla_timeout(self) -> None:
        original_sleep = carla_actor_object_bridge.time.sleep
        try:
            carla_actor_object_bridge.time.sleep = lambda _seconds: None
            actors = carla_actor_object_bridge.iter_target_actors_with_retry(
                _FakeClient(),
                SimpleNamespace(carla_wait_sec=1.0, poll_sec=0.0),
                ego_role_name="ego_vehicle",
                include_walkers=True,
            )
        finally:
            carla_actor_object_bridge.time.sleep = original_sleep

        self.assertEqual([actor.type_id for actor in actors], ["vehicle.audi.tt", "walker.pedestrian.0001"])


if __name__ == "__main__":
    unittest.main()
