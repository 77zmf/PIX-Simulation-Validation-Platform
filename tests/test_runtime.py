from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.runtime import execute_plan


class RuntimeExecutionTests(unittest.TestCase):
    def test_execute_plan_passes_env_to_foreground_steps(self) -> None:
        command = f'"{sys.executable}" -c "import os; print(os.environ[\'SIMCTL_TEST_VAR\'])"'
        plan = {
            "steps": [
                {
                    "name": "print-env",
                    "runner": "python",
                    "background": False,
                    "cwd": None,
                    "command": command,
                    "env": {"SIMCTL_TEST_VAR": "foreground-ok"},
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tempdir:
            logs = execute_plan(plan, Path(tempdir))
            self.assertEqual(logs[0]["status"], "completed")
            log_path = Path(logs[0]["log_path"])
            self.assertIn("foreground-ok", log_path.read_text(encoding="utf-8"))

    def test_execute_plan_streams_background_output_to_log_file(self) -> None:
        command = (
            f'"{sys.executable}" -c "import os,time; time.sleep(0.3); print(os.environ[\'SIMCTL_BG_VAR\'])"'
        )
        plan = {
            "steps": [
                {
                    "name": "background-env",
                    "runner": "python",
                    "background": True,
                    "cwd": None,
                    "command": command,
                    "env": {"SIMCTL_BG_VAR": "background-ok"},
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tempdir:
            logs = execute_plan(plan, Path(tempdir))
            self.assertEqual(logs[0]["status"], "started")
            time.sleep(0.6)
            log_path = Path(logs[0]["log_path"])
            self.assertIn("background-ok", log_path.read_text(encoding="utf-8"))

    def test_execute_plan_detects_fast_failing_background_steps(self) -> None:
        command = f'"{sys.executable}" -c "import sys; sys.exit(3)"'
        plan = {
            "steps": [
                {
                    "name": "fail-fast",
                    "runner": "python",
                    "background": True,
                    "cwd": None,
                    "command": command,
                    "env": {},
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tempdir:
            logs = execute_plan(plan, Path(tempdir))

        self.assertEqual(logs[0]["status"], "failed")
        self.assertEqual(logs[0]["returncode"], 3)


if __name__ == "__main__":
    unittest.main()
