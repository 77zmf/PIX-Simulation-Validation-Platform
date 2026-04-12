from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.cli import main
from simctl.slots import load_slot_catalog, read_slot_lock


class CliTests(unittest.TestCase):
    def test_bootstrap_renders_stable_plan(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(["--repo-root", str(REPO_ROOT), "bootstrap", "--stack", "stable"])
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["stack_id"], "stable")
        self.assertEqual(payload["action"], "bootstrap")
        self.assertEqual(payload["steps"][0]["runner"], "bash")
        self.assertIn("infra/ubuntu/bootstrap_host.sh", payload["steps"][0]["command"])
        self.assertNotIn("wsl.exe", payload["steps"][0]["command"].lower())

    def test_run_creates_passed_stub_result(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "run",
                        "--scenario",
                        "scenarios/l0/smoke_stub.yaml",
                        "--run-root",
                        tempdir,
                        "--slot",
                        "stable-slot-02",
                    ]
                )
            self.assertEqual(rc, 0)
            run_dirs = list(Path(tempdir).iterdir())
            self.assertEqual(len(run_dirs), 1)
            result = json.loads((run_dirs[0] / "run_result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["gate"]["passed"])
            self.assertEqual(result["slot_id"], "stable-slot-02")
            self.assertEqual(result["carla_rpc_port"], 2010)
            self.assertEqual(result["ros_domain_id"], 22)
            self.assertEqual(result["resolved_profiles"]["sensor"]["profile_id"], "ground_truth_control_baseline")
            self.assertEqual(result["resolved_profiles"]["algorithm"]["profile_id"], "planning_control_baseline")
            self.assertTrue(Path(result["artifacts"]["sensor_profile_snapshot"]).exists())
            self.assertTrue(Path(result["artifacts"]["algorithm_profile_snapshot"]).exists())

    def test_run_fails_fast_for_missing_algorithm_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            scenario_path = Path(tempdir) / "invalid_profile.yaml"
            scenario_path.write_text(
                dedent(
                    """\
                    scenario_id: invalid_algorithm_profile
                    stack: stable
                    map_id: Town01
                    asset_bundle: carla_town01
                    ego_init:
                      spawn_point: Town01/1
                    goal:
                      route_id: Town01/simple_loop
                    traffic_profile:
                      mode: background_light
                      vehicles: 1
                      pedestrians: 0
                    weather_profile:
                      preset: ClearNoon
                    sensor_profile: ground_truth_control_baseline
                    algorithm_profile: missing_algorithm_profile
                    seed: 1
                    recording:
                      rosbag2:
                        enabled: false
                      carla_recorder:
                        enabled: false
                    kpi_gate: planning_control_smoke
                    execution:
                      mode: stub
                      stub_outcome: passed
                    """
                ),
                encoding="utf-8",
            )
            with self.assertRaises(FileNotFoundError):
                main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "run",
                        "--scenario",
                        str(scenario_path),
                        "--run-root",
                        tempdir,
                    ]
                )

    def test_run_static_reconstruction_outputs_algorithm_execution_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "run",
                        "--scenario",
                        "scenarios/l2/reconstruction_static_public_road_gaussian_base.yaml",
                        "--run-root",
                        tempdir,
                        "--mock-result",
                        "passed",
                    ]
                )
            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["algorithm_execution"]["family"], "static_gaussians")
            self.assertEqual(result["algorithm_execution"]["stage"], "geometry_base")
            self.assertIn("static_gaussians", result["algorithm_execution"]["artifacts"])

    def test_run_dynamic_reconstruction_outputs_algorithm_execution_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "run",
                        "--scenario",
                        "scenarios/l3/reconstruction_dynamic_public_road_gaussian_replay.yaml",
                        "--run-root",
                        tempdir,
                        "--mock-result",
                        "passed",
                    ]
                )
            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["algorithm_execution"]["family"], "dynamic_gaussians")
            self.assertEqual(result["algorithm_execution"]["stage"], "actor_aware_replay")
            self.assertIn("dynamic_tracks", result["algorithm_execution"]["artifacts"])

    def test_run_execute_marks_launch_failed_when_execution_step_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            slot_id = "stable-slot-03"
            lock_path = REPO_ROOT / "artifacts" / "slot_locks" / "stable" / f"{slot_id}.json"
            previous_lock = lock_path.read_text(encoding="utf-8") if lock_path.exists() else None
            try:
                lock_path.unlink(missing_ok=True)
                with patch(
                    "simctl.cli.execute_plan",
                    return_value=[
                        {
                            "step": "start-carla-server",
                            "status": "failed",
                            "returncode": 2,
                            "log_path": str(Path(tempdir) / "start-carla-server.log"),
                        }
                    ],
                ):
                    with redirect_stdout(stream):
                        rc = main(
                            [
                                "--repo-root",
                                str(REPO_ROOT),
                                "run",
                                "--scenario",
                                "scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml",
                                "--run-root",
                                tempdir,
                                "--slot",
                                slot_id,
                                "--execute",
                            ]
                        )
            finally:
                if previous_lock is None:
                    lock_path.unlink(missing_ok=True)
                else:
                    lock_path.write_text(previous_lock, encoding="utf-8")
            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"], "launch_failed")
            self.assertEqual(result["gate"]["violations"][0]["reason"], "launch_step_failed")
            self.assertEqual(result["gate"]["violations"][0]["returncode"], 2)
            self.assertIsNone(result["runtime_health"])

    def test_run_execute_marks_launch_failed_when_health_probe_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            slot_id = "stable-slot-04"
            lock_path = REPO_ROOT / "artifacts" / "slot_locks" / "stable" / f"{slot_id}.json"
            previous_lock = lock_path.read_text(encoding="utf-8") if lock_path.exists() else None
            try:
                lock_path.unlink(missing_ok=True)
                with (
                    patch(
                        "simctl.cli.execute_plan",
                        return_value=[
                            {
                                "step": "start-carla-server",
                                "status": "started",
                                "pid": 1001,
                                "pid_file": str(Path(tempdir) / "carla.pid"),
                                "log_path": str(Path(tempdir) / "start-carla-server.log"),
                            },
                            {
                                "step": "start-autoware-bridge",
                                "status": "started",
                                "pid": 1002,
                                "pid_file": str(Path(tempdir) / "bridge.pid"),
                                "log_path": str(Path(tempdir) / "start-autoware-bridge.log"),
                            },
                            {
                                "step": "start-autoware-stack",
                                "status": "started",
                                "pid": 1003,
                                "pid_file": str(Path(tempdir) / "autoware.pid"),
                                "log_path": str(Path(tempdir) / "start-autoware-stack.log"),
                            },
                        ],
                    ),
                    patch(
                        "simctl.cli.probe_runtime_health",
                        return_value={
                            "passed": False,
                            "failed_checks": ["carla_rpc_port"],
                            "report_path": str(Path(tempdir) / "health.json"),
                        },
                    ),
                ):
                    with redirect_stdout(stream):
                        rc = main(
                            [
                                "--repo-root",
                                str(REPO_ROOT),
                                "run",
                                "--scenario",
                                "scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml",
                                "--run-root",
                                tempdir,
                                "--slot",
                                slot_id,
                                "--execute",
                            ]
                        )
            finally:
                if previous_lock is None:
                    lock_path.unlink(missing_ok=True)
                else:
                    lock_path.write_text(previous_lock, encoding="utf-8")
            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"], "launch_failed")
            self.assertEqual(result["gate"]["violations"][0]["reason"], "runtime_health_check_failed")
            self.assertEqual(result["gate"]["violations"][0]["failed_checks"], ["carla_rpc_port"])
            self.assertFalse(result["runtime_health"]["passed"])

    def test_run_execute_marks_launch_submitted_when_health_probe_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            slot_id = "stable-slot-01"
            lock_path = REPO_ROOT / "artifacts" / "slot_locks" / "stable" / f"{slot_id}.json"
            previous_lock = lock_path.read_text(encoding="utf-8") if lock_path.exists() else None
            try:
                lock_path.unlink(missing_ok=True)
                with (
                    patch(
                        "simctl.cli.execute_plan",
                        return_value=[
                            {
                                "step": "start-carla-server",
                                "status": "started",
                                "pid": 1001,
                                "pid_file": str(Path(tempdir) / "carla.pid"),
                                "log_path": str(Path(tempdir) / "start-carla-server.log"),
                            },
                            {
                                "step": "start-autoware-bridge",
                                "status": "started",
                                "pid": 1002,
                                "pid_file": str(Path(tempdir) / "bridge.pid"),
                                "log_path": str(Path(tempdir) / "start-autoware-bridge.log"),
                            },
                            {
                                "step": "start-autoware-stack",
                                "status": "started",
                                "pid": 1003,
                                "pid_file": str(Path(tempdir) / "autoware.pid"),
                                "log_path": str(Path(tempdir) / "start-autoware-stack.log"),
                            },
                        ],
                    ),
                    patch(
                        "simctl.cli.probe_runtime_health",
                        return_value={
                            "passed": True,
                            "failed_checks": [],
                            "report_path": str(Path(tempdir) / "health.json"),
                        },
                    ),
                ):
                    with redirect_stdout(stream):
                        rc = main(
                            [
                                "--repo-root",
                                str(REPO_ROOT),
                                "run",
                                "--scenario",
                                "scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml",
                                "--run-root",
                                tempdir,
                                "--slot",
                                slot_id,
                                "--execute",
                            ]
                        )
            finally:
                if previous_lock is None:
                    lock_path.unlink(missing_ok=True)
                else:
                    lock_path.write_text(previous_lock, encoding="utf-8")
            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"], "launch_submitted")
            self.assertEqual(result["gate"]["violations"][0]["reason"], "awaiting_runtime_results")
            self.assertTrue(result["runtime_health"]["passed"])

    def test_batch_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "batch",
                    "--glob",
                    "scenarios/l1/*.yaml",
                    "--run-root",
                    tempdir,
                    "--mock-result",
                    "passed",
                ]
            )
            report_dir = Path(tempdir) / "report"
            rc = main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "report",
                    "--run-root",
                    tempdir,
                    "--output-dir",
                    str(report_dir),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertTrue((report_dir / "report.md").exists())
            self.assertTrue((report_dir / "report.html").exists())
            self.assertTrue((report_dir / "issue_update.md").exists())

    def test_batch_parallel_uses_two_slots_and_reuses_one_for_third_run(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "batch",
                        "scenarios/l0/smoke_stub.yaml",
                        "scenarios/l1/regression_follow_lane.yaml",
                        "scenarios/l2/planning_control_merge_regression.yaml",
                        "--run-root",
                        tempdir,
                        "--parallel",
                        "2",
                        "--mock-result",
                        "passed",
                    ]
                )
            self.assertEqual(rc, 0)
            batch_index_path = Path(stream.getvalue().strip())
            batch_index = json.loads(batch_index_path.read_text(encoding="utf-8"))
            self.assertEqual(batch_index["parallel"], 2)
            self.assertEqual(len(batch_index["records"]), 3)
            slot_ids = [record["slot_id"] for record in batch_index["records"]]
            self.assertEqual(len(set(slot_ids)), 2)
            for record in batch_index["records"]:
                result = json.loads(Path(record["run_result"]).read_text(encoding="utf-8"))
                self.assertEqual(result["slot_id"], record["slot_id"])
                self.assertEqual(result["status"], "passed")

    def test_batch_ignores_existing_report_directory_when_indexing_results(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            (Path(tempdir) / "report").mkdir()
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "batch",
                        "--glob",
                        "scenarios/l1/*.yaml",
                        "--run-root",
                        tempdir,
                        "--mock-result",
                        "passed",
                    ]
                )
            self.assertEqual(rc, 0)
            batch_dirs = sorted(path for path in Path(tempdir).iterdir() if path.is_dir() and "__batch" in path.name)
            self.assertEqual(len(batch_dirs), 1)
            batch_index = json.loads((batch_dirs[0] / "batch_index.json").read_text(encoding="utf-8"))
            for record in batch_index["records"]:
                self.assertTrue(Path(record["run_result"]).exists())
                self.assertEqual(Path(record["run_result"]).name, "run_result.json")

    def test_down_releases_slot_lock_for_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "20260330T000000000000Z__stable_l1_follow_lane"
            run_dir.mkdir(parents=True)
            slot = load_slot_catalog("stable", REPO_ROOT)[0]
            lock_path = REPO_ROOT / "artifacts" / "slot_locks" / "stable" / f"{slot.slot_id}.json"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            previous_lock = lock_path.read_text(encoding="utf-8") if lock_path.exists() else None
            (run_dir / "run_result.json").write_text(
                json.dumps(
                    {
                        "stack": "stable",
                        "slot_id": slot.slot_id,
                    }
                ),
                encoding="utf-8",
            )
            try:
                lock_path.write_text(
                    json.dumps(
                        {
                            "stack_id": "stable",
                            "slot_id": slot.slot_id,
                            "scenario_id": "stable_l1_follow_lane",
                            "run_dir": str(run_dir),
                        }
                    ),
                    encoding="utf-8",
                )
                with patch("simctl.cli.execute_plan", return_value=[]):
                    rc = main(
                        [
                            "--repo-root",
                            str(REPO_ROOT),
                            "down",
                            "--stack",
                            "stable",
                            "--run-dir",
                            str(run_dir),
                            "--execute",
                        ]
                    )
                self.assertEqual(rc, 0)
                self.assertIsNone(read_slot_lock(REPO_ROOT, "stable", slot.slot_id))
            finally:
                if previous_lock is None:
                    lock_path.unlink(missing_ok=True)
                else:
                    lock_path.write_text(previous_lock, encoding="utf-8")

    def test_digest_from_fixture_json(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "digest",
                        "--config",
                        str(REPO_ROOT / "ops" / "project_automation.yaml"),
                        "--tasks-json",
                        str(REPO_ROOT / "tests" / "fixtures" / "project_tasks.json"),
                        "--scenarios-json",
                        str(REPO_ROOT / "tests" / "fixtures" / "project_scenarios.json"),
                        "--output-dir",
                        tempdir,
                    ]
                )
            self.assertEqual(rc, 0)
            outputs = json.loads(stream.getvalue())
            summary = json.loads(Path(outputs["summary"]).read_text(encoding="utf-8"))
            self.assertIn("Confirm E2E shadow evaluation plan", summary["task_summary"]["blocked_titles"])
            scenario_watch_titles = summary["scenario_summary"]["due_soon_titles"] + summary["scenario_summary"]["overdue_titles"]
            self.assertIn("Unprotected left at signalized intersection", scenario_watch_titles)
            self.assertTrue(Path(outputs["markdown"]).exists())
            self.assertTrue(Path(outputs["html"]).exists())

if __name__ == "__main__":
    unittest.main()
