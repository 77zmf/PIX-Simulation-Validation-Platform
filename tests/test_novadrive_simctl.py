from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novadrive.runtime.runner import main as novadrive_main
from simctl.cli import main as simctl_main


class NovaDriveSimctlTests(unittest.TestCase):
    def test_simctl_renders_novadrive_up_without_autoware_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = simctl_main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "up",
                        "--stack",
                        "novadrive",
                        "--scenario",
                        "scenarios/l0/novadrive_smoke.yaml",
                        "--run-dir",
                        tempdir,
                        "--slot",
                        "novadrive-slot-01",
                    ]
                )
            self.assertEqual(rc, 0)
            plan_path = Path(stream.getvalue().strip())
            plan = json.loads(plan_path.read_text(encoding="utf-8"))

        step_names = [step["name"] for step in plan["steps"]]
        self.assertIn("run-novadrive-direct-carla", step_names)
        self.assertNotIn("start-autoware-stack", step_names)
        self.assertNotIn("start-autoware-bridge", step_names)

    def test_mock_runner_and_finalize_close_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "novadrive_mock"
            rc = novadrive_main(
                [
                    "--scenario",
                    str(REPO_ROOT / "scenarios" / "l0" / "novadrive_smoke.yaml"),
                    "--run-dir",
                    str(run_dir),
                    "--mode",
                    "mock",
                ]
            )
            self.assertEqual(rc, 0)
            run_result = run_dir / "run_result.json"
            run_result.write_text(
                json.dumps(
                    {
                        "run_id": run_dir.name,
                        "scenario_id": "novadrive_l0_smoke",
                        "stack": "novadrive",
                        "status": "launch_submitted",
                        "scenario_path": str(REPO_ROOT / "scenarios" / "l0" / "novadrive_smoke.yaml"),
                        "scenario_params": {"traffic_profile": {"mode": "empty"}},
                        "gate": {"gate_id": "novadrive_smoke", "passed": False},
                        "artifacts": {"run_dir": str(run_dir), "run_result": str(run_result)},
                    }
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = simctl_main(["--repo-root", str(REPO_ROOT), "finalize", "--run-dir", str(run_dir)])
            self.assertEqual(rc, 0)
            finalized = json.loads(stream.getvalue())

        self.assertEqual(finalized["status"], "passed")
        self.assertEqual(finalized["goal_status"], "novadrive_passed")
        shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

