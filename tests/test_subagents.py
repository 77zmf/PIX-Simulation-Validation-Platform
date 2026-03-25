from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.cli import main
from simctl.subagents import list_subagent_specs, load_subagent_spec


class SubagentSpecTests(unittest.TestCase):
    def test_list_subagent_specs_loads_catalog(self) -> None:
        specs = list_subagent_specs(REPO_ROOT)
        self.assertEqual([spec.spec_id for spec in specs], ["algorithm_research_explorer", "execution_runtime_explorer"])

    def test_load_subagent_spec_renders_repo_root(self) -> None:
        spec = load_subagent_spec("execution_runtime_explorer", REPO_ROOT)
        message = spec.render_message(REPO_ROOT)
        self.assertIn(str(REPO_ROOT), message)
        self.assertIn("execution/runtime/automation", message)

    def test_cli_lists_subagent_specs(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(["--repo-root", str(REPO_ROOT), "subagent-spec", "--list"])
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(len(payload["specs"]), 2)

    def test_cli_renders_subagent_spec_json(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "subagent-spec",
                    "--name",
                    "algorithm_research_explorer",
                ]
            )
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["agent_type"], "explorer")
        self.assertEqual(payload["model"], "gpt-5.4-mini")
        self.assertIn(str(REPO_ROOT), payload["message"])


if __name__ == "__main__":
    unittest.main()
