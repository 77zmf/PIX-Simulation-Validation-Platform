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
from simctl.subagents import (
    list_onboarding_profiles,
    list_subagent_specs,
    load_onboarding_profile,
    load_subagent_spec,
)


class SubagentSpecTests(unittest.TestCase):
    def test_list_subagent_specs_loads_catalog(self) -> None:
        specs = list_subagent_specs(REPO_ROOT)
        self.assertEqual(
            [spec.spec_id for spec in specs],
            [
                "algorithm_research_explorer",
                "execution_runtime_explorer",
                "gaussian_reconstruction_explorer",
                "project_automation_explorer",
                "public_road_e2e_shadow_explorer",
                "stable_stack_host_readiness_explorer",
            ],
        )

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
        self.assertEqual(len(payload["specs"]), 6)

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
        self.assertTrue(payload["spawn_agent_parameters"]["fork_context"])

    def test_load_gaussian_reconstruction_spec_mentions_reconstruction(self) -> None:
        spec = load_subagent_spec("gaussian_reconstruction_explorer", REPO_ROOT)
        self.assertIn("Gaussian reconstruction", spec.description)
        self.assertIn("reconstruction", spec.render_message(REPO_ROOT).lower())

    def test_load_public_road_e2e_shadow_spec_mentions_bevfusion(self) -> None:
        spec = load_subagent_spec("public_road_e2e_shadow_explorer", REPO_ROOT)
        self.assertIn("BEVFusion", spec.description)
        self.assertIn("uniad", spec.render_message(REPO_ROOT).lower())

    def test_load_stable_stack_host_readiness_spec_mentions_ubuntu(self) -> None:
        spec = load_subagent_spec("stable_stack_host_readiness_explorer", REPO_ROOT)
        self.assertIn("readiness", spec.description.lower())
        self.assertIn("ubuntu host", spec.render_message(REPO_ROOT).lower())

    def test_cli_renders_spawn_json(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "subagent-spec",
                    "--name",
                    "project_automation_explorer",
                    "--format",
                    "spawn_json",
                ]
            )
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["agent_type"], "explorer")
        self.assertTrue(payload["fork_context"])
        self.assertEqual(payload["model"], "gpt-5.4-mini")
        self.assertEqual(payload["reasoning_effort"], "medium")
        self.assertIn(str(REPO_ROOT), payload["message"])

    def test_list_onboarding_profiles_loads_catalog(self) -> None:
        profiles = list_onboarding_profiles(REPO_ROOT)
        self.assertEqual(
            [profile.profile_id for profile in profiles],
            ["codex_pmo", "lsxala", "yzp333666", "zhu_minfeng"],
        )

    def test_load_onboarding_profile_for_yang_includes_expected_routes(self) -> None:
        profile = load_onboarding_profile("yzp333666", REPO_ROOT)
        payload = profile.as_payload(REPO_ROOT)
        self.assertEqual(payload["display_name"], "Yang Zhipeng / 杨志朋")
        self.assertEqual(
            [spec["spec_id"] for spec in payload["recommended_subagents"]],
            ["public_road_e2e_shadow_explorer", "algorithm_research_explorer"],
        )
        self.assertEqual(
            [skill["skill_id"] for skill in payload["related_skills"]],
            ["simctl-run-analysis", "carla-case-builder"],
        )
        self.assertIn("python -m simctl subagent-spec --onboarding yzp333666", payload["starter_commands"])

    def test_cli_lists_onboarding_profiles(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(["--repo-root", str(REPO_ROOT), "subagent-spec", "--list-onboarding"])
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(len(payload["profiles"]), 4)
        self.assertEqual(payload["profiles"][0]["profile_id"], "codex_pmo")

    def test_cli_renders_one_onboarding_profile(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(["--repo-root", str(REPO_ROOT), "subagent-spec", "--onboarding", "zhu_minfeng"])
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["profile_id"], "zhu_minfeng")
        self.assertEqual(payload["recommended_subagents"][0]["spec_id"], "stable_stack_host_readiness_explorer")
        self.assertEqual(payload["related_skills"][0]["skill_id"], "simctl-run-analysis")


if __name__ == "__main__":
    unittest.main()
