from __future__ import annotations

import importlib.util
import importlib.machinery
import os
import sys
import tempfile
import threading
import time
import unittest
from argparse import Namespace
from pathlib import Path


def _load_probe_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "ops" / "runtime_probes" / "sumo_cosim_probe.py"
    spec = importlib.util.spec_from_file_location("sumo_cosim_probe", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SumoCosimProbeTests(unittest.TestCase):
    def test_log_probe_retries_until_step_samples_appear(self) -> None:
        probe = _load_probe_module()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            (run_dir / "command_logs").mkdir(parents=True)
            log_path = run_dir / "command_logs" / "03_start-sumo-cosim.log"
            log_path.write_text(
                "\n".join(
                    [
                        "SUMO TraCI port ready: 127.0.0.1:9000",
                        "INFO: Connection to sumo server. Host: 127.0.0.1 Port: 9000",
                    ]
                ),
                encoding="utf-8",
            )

            def append_sample() -> None:
                time.sleep(0.05)
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(
                        "\rStep #5.00 (1ms ~= 50.00*RT, TraCI: 20ms, vehicles TOT 6 ACT 5 BUF 1)\n"
                    )

            thread = threading.Thread(target=append_sample, daemon=True)
            thread.start()
            payload = probe._sumo_log_probe(run_dir, max_wait_sec=0.3, poll_sec=0.02)
            thread.join(timeout=1.0)

        self.assertTrue(payload["connected"])
        self.assertEqual(payload["step_sample_count"], 1)
        self.assertEqual(payload["max_active_vehicles"], 5)

    def test_log_actor_source_produces_kpi_metrics_without_carla_rpc(self) -> None:
        probe = _load_probe_module()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            (run_dir / "command_logs").mkdir(parents=True)
            (run_dir / "pids").mkdir()
            (run_dir / "pids" / "sumo-server.pid").write_text(str(os.getpid()), encoding="utf-8")
            (run_dir / "command_logs" / "03_start-sumo-cosim.log").write_text(
                "\n".join(
                    [
                        "SUMO TraCI port ready: 127.0.0.1:9000",
                        "INFO: Connection to sumo server. Host: 127.0.0.1 Port: 9000",
                        "Step #0.00 (0ms ?*RT. ?UPS, TraCI: 10ms, vehicles TOT 1 ACT 1 BUF 0)",
                        "Step #5.00 (1ms ~= 50.00*RT, TraCI: 20ms, vehicles TOT 6 ACT 5 BUF 1)",
                    ]
                ),
                encoding="utf-8",
            )
            sumocfg = Path(tmp) / "Town01.sumocfg"
            sumocfg.write_text("<configuration />", encoding="utf-8")

            original_ros_probe = probe._ros_topic_probe
            probe._ros_topic_probe = lambda args: {
                "object_topic": {"seen": True},
                "control_topic": {"seen": True},
                "autoware_object_stream_seen": True,
                "ego_control_command_seen": True,
                "ego_control_command_sample_seen": True,
                "ego_control_command_presence_fallback": False,
            }
            try:
                payload = probe.run_probe(
                    Namespace(
                        wait_sec=0,
                        run_dir=str(run_dir),
                        profile="town01_sumo_smoke",
                        actor_source="log",
                        carla_root="",
                        carla_host="127.0.0.1",
                        carla_port=2000,
                        carla_timeout_sec=1.0,
                        ego_role_name="ego_vehicle",
                        sumo_role_prefix="sumo",
                        sumo_config_file=str(sumocfg),
                        min_actors=1,
                        max_actor_details=12,
                        object_topic="/perception/object_recognition/objects",
                        control_topic="/control/command/control_cmd",
                        ros_timeout_sec=1.0,
                        log_wait_timeout_sec=0.0,
                        log_poll_sec=0.1,
                    )
                )
            finally:
                probe._ros_topic_probe = original_ros_probe

        self.assertTrue(payload["overall_passed"])
        self.assertEqual(payload["metrics"]["sumo_actor_count"], 5.0)
        self.assertEqual(payload["metrics"]["sumo_step_samples"], 2.0)
        self.assertEqual(payload["metrics"]["sumo_cosim_alive"], 1.0)
        self.assertEqual(payload["carla"]["source"], "disabled")

    def test_carla_actor_probe_ticks_until_sumo_actors_are_visible(self) -> None:
        probe = _load_probe_module()

        class FakeActorList(list):
            def filter(self, pattern: str) -> "FakeActorList":
                return self if pattern == "vehicle.*" else FakeActorList()

        class FakeActor:
            def __init__(self, actor_id: int, role_name: str) -> None:
                self.id = actor_id
                self.type_id = "vehicle.test"
                self.attributes = {"role_name": role_name}

            def get_location(self) -> object:
                return type("Location", (), {"x": 1.0, "y": 2.0, "z": 0.0})()

        class FakeWorld:
            def __init__(self) -> None:
                self.ticks = 0

            def tick(self) -> None:
                self.ticks += 1

            def get_actors(self) -> FakeActorList:
                if self.ticks < 2:
                    return FakeActorList()
                return FakeActorList(
                    [
                        FakeActor(1, "ego_vehicle"),
                        FakeActor(2, "sumo_driver"),
                        FakeActor(3, "sumo_shadow"),
                    ]
                )

        fake_world = FakeWorld()

        class FakeClient:
            def __init__(self, host: str, port: int) -> None:
                self.host = host
                self.port = port

            def set_timeout(self, _timeout: float) -> None:
                return None

            def get_world(self) -> FakeWorld:
                return fake_world

        fake_carla = type(sys)("carla")
        fake_carla.__spec__ = importlib.machinery.ModuleSpec("carla", loader=None)
        fake_carla.Client = FakeClient
        previous = sys.modules.get("carla")
        sys.modules["carla"] = fake_carla
        try:
            payload = probe._carla_actor_probe(
                Namespace(
                    carla_root="",
                    carla_host="127.0.0.1",
                    carla_port=2000,
                    carla_timeout_sec=1.0,
                    ego_role_name="ego_vehicle",
                    sumo_role_prefix="sumo",
                    min_actors=2,
                    max_actor_details=12,
                    carla_actor_wait_sec=1.0,
                    carla_actor_poll_sec=0.0,
                )
            )
        finally:
            if previous is None:
                sys.modules.pop("carla", None)
            else:
                sys.modules["carla"] = previous

        self.assertTrue(payload["passed"])
        self.assertEqual(payload["actor_count"], 3)
        self.assertEqual(payload["sumo_actor_count"], 2)
        self.assertGreaterEqual(payload["actor_poll_attempts"], 2)


if __name__ == "__main__":
    unittest.main()
