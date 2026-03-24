from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from textwrap import dedent


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.cli import main


class CliTests(unittest.TestCase):
    def test_bootstrap_renders_stable_plan(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(["--repo-root", str(REPO_ROOT), "bootstrap", "--stack", "stable"])
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["stack_id"], "stable")
        self.assertEqual(payload["action"], "bootstrap")

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
                    ]
                )
            self.assertEqual(rc, 0)
            run_dirs = list(Path(tempdir).iterdir())
            self.assertEqual(len(run_dirs), 1)
            result = json.loads((run_dirs[0] / "run_result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["gate"]["passed"])
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
            self.assertIn("Confirm remote GPU host access", summary["task_summary"]["blocked_titles"])
            self.assertIn("Unprotected left at signalized intersection", summary["scenario_summary"]["due_soon_titles"])
            self.assertTrue(Path(outputs["markdown"]).exists())
            self.assertTrue(Path(outputs["html"]).exists())

    def test_notion_check_reports_missing_token_without_failing(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "notion-check",
                    "--config",
                    str(REPO_ROOT / "ops" / "project_automation.yaml"),
                ]
            )
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertTrue(payload["configured"])
        self.assertIn("tasks", payload["sources"])
        self.assertFalse(payload["token_present"])


if __name__ == "__main__":
    unittest.main()
