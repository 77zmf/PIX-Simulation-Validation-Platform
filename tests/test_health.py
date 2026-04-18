from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.health import probe_runtime_health
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
