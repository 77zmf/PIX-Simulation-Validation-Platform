from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.health import probe_runtime_health
from simctl.health import _probe_carla_actor
from simctl.health import _probe_ros_graph
from simctl.models import RuntimeSlot


def _write_health_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class RuntimeHealthTests(unittest.TestCase):
    def _slot(self, port: int) -> RuntimeSlot:
        return RuntimeSlot(
            slot_id="stable-slot-01",
            carla_rpc_port=port,
            traffic_manager_port=8000,
            ros_domain_id=21,
            runtime_namespace="/stable/slot01",
            gpu_id="0",
        )

    def test_probe_runtime_health_passes_when_port_and_processes_are_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            logs = [
                {"step": "start-carla-server", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-bridge", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-stack", "status": "started", "pid": os.getpid()},
                {"step": "start-carla-localization-bridge", "status": "started", "pid": os.getpid()},
            ]
            with (
                patch("simctl.health._probe_ros_graph", return_value={"available": False, "passed": None}),
                patch("simctl.health.dump_json", side_effect=_write_health_report),
            ):
                report = probe_runtime_health(
                    run_dir=Path(tempdir),
                    slot=self._slot(port),
                    logs=logs,
                    runtime_namespace="/stable/slot01",
                )

            self.assertTrue(report["passed"])
            self.assertEqual(report["failed_checks"], [])
            self.assertTrue((Path(tempdir) / "health.json").exists())

    def test_probe_runtime_health_fails_when_port_is_unreachable(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            logs = [
                {"step": "start-carla-server", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-bridge", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-stack", "status": "started", "pid": os.getpid()},
                {"step": "start-carla-localization-bridge", "status": "started", "pid": os.getpid()},
            ]
            with (
                patch("simctl.health._probe_ros_graph", return_value={"available": False, "passed": None}),
                patch(
                    "simctl.health._probe_tcp_port",
                    return_value={"passed": False, "host": "127.0.0.1", "port": 2000, "error": "connection_refused"},
                ),
                patch("simctl.health.dump_json", side_effect=_write_health_report),
            ):
                report = probe_runtime_health(
                    run_dir=Path(tempdir),
                    slot=self._slot(2000),
                    logs=logs,
                    runtime_namespace="/stable/slot01",
                )

            self.assertFalse(report["passed"])
            self.assertIn("carla_rpc_port", report["failed_checks"])

    def test_probe_runtime_health_checks_extra_started_background_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            logs = [
                {"step": "start-carla-server", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-bridge", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-stack", "status": "started", "pid": os.getpid()},
                {"step": "start-carla-localization-bridge", "status": "started", "pid": os.getpid()},
                {"step": "start-carla-actor-object-bridge", "status": "started", "pid": 0},
            ]
            with (
                patch("simctl.health._probe_ros_graph", return_value={"available": False, "passed": None}),
                patch("simctl.health.dump_json", side_effect=_write_health_report),
            ):
                report = probe_runtime_health(
                    run_dir=Path(tempdir),
                    slot=self._slot(port),
                    logs=logs,
                    runtime_namespace="/stable/slot01",
                )

            self.assertFalse(report["passed"])
            self.assertIn("processes", report["failed_checks"])
            self.assertIn("start-carla-actor-object-bridge", report["checks"]["processes"]["failed_steps"])

    def test_probe_runtime_health_fails_when_started_process_log_has_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            carla_log = Path(tempdir) / "start-carla-server.log"
            carla_log.write_text("Signal 11 caught.\nSegmentation fault (core dumped)\n", encoding="utf-8")
            logs = [
                {
                    "step": "start-carla-server",
                    "status": "started",
                    "pid": os.getpid(),
                    "log_path": str(carla_log),
                },
                {"step": "start-autoware-bridge", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-stack", "status": "started", "pid": os.getpid()},
                {"step": "start-carla-localization-bridge", "status": "started", "pid": os.getpid()},
            ]
            with (
                patch("simctl.health._probe_ros_graph", return_value={"available": False, "passed": None}),
                patch("simctl.health.dump_json", side_effect=_write_health_report),
            ):
                report = probe_runtime_health(
                    run_dir=Path(tempdir),
                    slot=self._slot(port),
                    logs=logs,
                    runtime_namespace="/stable/slot01",
                )

            self.assertFalse(report["passed"])
            self.assertIn("processes", report["failed_checks"])
            carla_check = report["checks"]["processes"]["process_checks"][0]
            self.assertFalse(carla_check["passed"])
            self.assertEqual(carla_check["reason"], "crash_log:Signal 11 caught")

    def test_probe_runtime_health_can_require_carla_ego_actor(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            logs = [
                {"step": "start-carla-server", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-bridge", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-stack", "status": "started", "pid": os.getpid()},
                {"step": "start-carla-localization-bridge", "status": "started", "pid": os.getpid()},
            ]
            actor_check = {
                "required": True,
                "passed": True,
                "vehicle_count": 1,
                "matched_actor": {
                    "id": 197,
                    "type_id": "vehicle.pixmoving.robobus",
                    "role_name": "ego_vehicle",
                },
            }
            with (
                patch("simctl.health._probe_ros_graph", return_value={"available": False, "passed": None}),
                patch("simctl.health._probe_carla_actor", return_value=actor_check),
                patch("simctl.health.dump_json", side_effect=_write_health_report),
            ):
                report = probe_runtime_health(
                    run_dir=Path(tempdir),
                    slot=self._slot(port),
                    logs=logs,
                    runtime_namespace="/stable/slot01",
                    carla_actor_check=True,
                    carla_actor_type="vehicle.pixmoving.robobus",
                    carla_ego_role_name="ego_vehicle",
                    carla_root="/opt/carla",
                )

            self.assertTrue(report["passed"])
            self.assertEqual(report["checks"]["carla_actor"]["matched_actor"]["type_id"], "vehicle.pixmoving.robobus")

    def test_probe_runtime_health_fails_when_required_carla_ego_actor_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            logs = [
                {"step": "start-carla-server", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-bridge", "status": "started", "pid": os.getpid()},
                {"step": "start-autoware-stack", "status": "started", "pid": os.getpid()},
                {"step": "start-carla-localization-bridge", "status": "started", "pid": os.getpid()},
            ]
            with (
                patch("simctl.health._probe_ros_graph", return_value={"available": False, "passed": None}),
                patch(
                    "simctl.health._probe_carla_actor",
                    return_value={
                        "required": True,
                        "passed": False,
                        "vehicle_count": 0,
                        "error": "carla_actor_not_found",
                    },
                ),
                patch("simctl.health.dump_json", side_effect=_write_health_report),
            ):
                report = probe_runtime_health(
                    run_dir=Path(tempdir),
                    slot=self._slot(port),
                    logs=logs,
                    runtime_namespace="/stable/slot01",
                    carla_actor_check=True,
                    carla_actor_type="vehicle.pixmoving.robobus",
                    carla_ego_role_name="ego_vehicle",
                    carla_root="/opt/carla",
                )

            self.assertFalse(report["passed"])
            self.assertIn("carla_actor", report["failed_checks"])
            self.assertEqual(report["checks"]["carla_actor"]["vehicle_count"], 0)

    def test_carla_actor_probe_process_failure_does_not_kill_health_check(self) -> None:
        completed = SimpleNamespace(returncode=139, stdout="", stderr="Segmentation fault")
        with (
            patch("simctl.health.subprocess.run", return_value=completed),
            patch("simctl.health.shutil.which", return_value="/usr/bin/python3"),
        ):
            report = _probe_carla_actor(
                port=2000,
                carla_root="/home/pixmoving/CARLA_0.9.15",
                actor_type="vehicle.pixmoving.robobus",
                ego_role_name="ego_vehicle",
                attempts=1,
                wait_sec=0,
            )

        self.assertFalse(report["passed"])
        self.assertEqual(report["error"], "carla_actor_probe_process_failed:139")
        self.assertIn("Segmentation fault", report["stderr_tail"])

    def test_probe_ros_graph_accepts_scenario_expected_topics(self) -> None:
        completed = SimpleNamespace(
            returncode=0,
            stdout="/clock\n/tf\n/sensing/lidar/top/pointcloud_before_sync\n",
            stderr="",
        )
        with (
            patch("simctl.health._ros2_available", return_value=True),
            patch("simctl.health._ros_topic_command", return_value=["ros2", "topic", "list"]),
            patch("simctl.health.subprocess.run", return_value=completed),
        ):
            report = _probe_ros_graph(
                21,
                expected_topics=[
                    "/clock",
                    "/sensing/lidar/top/pointcloud_before_sync",
                ],
            )

        self.assertTrue(report["passed"])
        self.assertEqual(
            report["expected_topics"],
            ["/clock", "/sensing/lidar/top/pointcloud_before_sync"],
        )

    def test_probe_ros_graph_times_out_ros_cli_calls(self) -> None:
        with (
            patch("simctl.health._ros2_available", return_value=True),
            patch("simctl.health._ros_topic_command", return_value=["ros2", "topic", "list"]),
            patch("simctl.health.ROS_GRAPH_ATTEMPTS", 1),
            patch("simctl.health.ROS_GRAPH_WAIT_SEC", 0),
            patch("simctl.health.ROS_GRAPH_COMMAND_TIMEOUT_SEC", 0.1),
            patch(
                "simctl.health.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["ros2", "topic", "list"], timeout=0.1),
            ) as run_mock,
        ):
            report = _probe_ros_graph(21, expected_topics=["/clock"])

        self.assertFalse(report["passed"])
        self.assertTrue(report["timed_out"])
        self.assertEqual(report["command_timeout_sec"], 0.1)
        run_mock.assert_called_once()
        self.assertEqual(run_mock.call_args.kwargs["timeout"], 0.1)

    def test_ros_topic_command_disables_ros2cli_daemon(self) -> None:
        from simctl.health import _ros_topic_command

        with tempfile.TemporaryDirectory() as tempdir:
            setup_script = Path(tempdir) / "setup.bash"
            setup_script.write_text("", encoding="utf-8")
            with patch("simctl.health.ROS_SETUP_SCRIPT", setup_script):
                command = _ros_topic_command(21, rmw_implementation="rmw_cyclonedds_cpp")

        self.assertIsNotNone(command)
        assert command is not None
        self.assertIn("export ROS2CLI_DISABLE_DAEMON=1", command[-1])
        self.assertIn("export ROS_DOMAIN_ID=21", command[-1])
