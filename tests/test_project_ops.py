from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.project_ops import item_from_payload, load_project_items, render_digest_markdown, summarize_items


class ProjectOpsTests(unittest.TestCase):
    def test_codex_import_manifest_references_existing_overlay_files(self) -> None:
        manifest = json.loads((REPO_ROOT / "codex_import_manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["entrypoint"], "AGENTS.override.md")
        for doc in manifest["docs"]:
            self.assertTrue((REPO_ROOT / doc["path"]).exists(), doc["path"])
        self.assertTrue((REPO_ROOT / manifest["project_config"]).exists())
        for agent_path in manifest["custom_agents"]:
            self.assertTrue((REPO_ROOT / agent_path).exists(), agent_path)

        backlog = json.loads((REPO_ROOT / "tasks" / "codex_backlog.json").read_text(encoding="utf-8"))
        self.assertEqual(backlog["version"], "2026-04-18")
        self.assertIn("STABLE-001", {task["id"] for task in backlog["tasks"]})

    def test_item_from_payload_maps_generic_project_fields(self) -> None:
        item = item_from_payload(
            {
                "title": "Confirm E2E shadow evaluation plan",
                "status": "Todo",
                "priority": "P1",
                "due Date": "2026-03-25",
                "owner": "Yang Zhipeng",
                "blocked": "Yes",
                "item URL": "https://github.com/users/77zmf/projects/1/views/1",
                "content": {"body": "Waiting for the UE4.26 shadow validation plan and scenario shortlist."},
            }
        )
        self.assertEqual(item.title, "Confirm E2E shadow evaluation plan")
        self.assertEqual(item.owner, "Yang Zhipeng")
        self.assertEqual(item.blocked, "Yes")
        self.assertEqual(item.body, "Waiting for the UE4.26 shadow validation plan and scenario shortlist.")
        self.assertEqual(item.item_url, "https://github.com/users/77zmf/projects/1/views/1")

    def test_load_project_items_auto_uses_github_project(self) -> None:
        with patch("simctl.project_ops.fetch_project_items", return_value=["github"]) as github_fetch:
            items = load_project_items(
                owner="pixmoving-moveit",
                number=2,
                provider="auto",
                source_name="tasks",
            )
        self.assertEqual(items, ["github"])
        github_fetch.assert_called_once_with("pixmoving-moveit", 2)

    def test_summarize_items_treats_completed_status_as_done(self) -> None:
        items = [
            item_from_payload(
                {
                    "title": "closed_loop_acceptance",
                    "status": "completed",
                    "priority": "P0",
                    "track": "Stable Stack",
                    "due Date": "2026-03-20",
                    "owner": "Zhu Minfeng",
                    "blocked": "No",
                }
            ),
            item_from_payload(
                {
                    "title": "e2e_shadow_plan_review",
                    "status": "In Progress",
                    "priority": "P1",
                    "track": "E2E Shadow",
                    "due Date": "2026-03-21",
                    "owner": "Yang Zhipeng",
                    "blocked": "No",
                }
            ),
        ]

        summary = summarize_items(items, today=date(2026, 3, 22), due_soon_days=3)
        self.assertEqual(summary["active"], 1)
        self.assertEqual([item.title for item in summary["overdue"]], ["e2e_shadow_plan_review"])

    def test_render_digest_markdown_lists_overdue_scenarios(self) -> None:
        scenario_summary = summarize_items(
            [
                item_from_payload(
                    {
                        "title": "Unprotected left at signalized intersection",
                        "status": "Todo",
                        "severity": "P0",
                        "stack": "Stable",
                        "target Track": "Public Road",
                        "scenario Type": "Unprotected Left",
                        "due Date": "2026-03-20",
                    }
                )
            ],
            today=date(2026, 3, 22),
            due_soon_days=3,
        )
        markdown = render_digest_markdown(
            config={
                "projects": {
                    "tasks": {"number": 2, "url": "https://github.com/users/77zmf/projects/1"},
                    "scenarios": {"number": 3, "url": "https://github.com/users/77zmf/projects/2"},
                },
                "reporting": {"due_soon_days": 3},
            },
            today=date(2026, 3, 22),
            task_summary=summarize_items([], today=date(2026, 3, 22), due_soon_days=3),
            scenario_summary=scenario_summary,
            run_summary=None,
        )
        self.assertIn("### Overdue", markdown)
        self.assertIn("Unprotected left at signalized intersection", markdown)


if __name__ == "__main__":
    unittest.main()
