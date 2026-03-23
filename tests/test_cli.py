from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
