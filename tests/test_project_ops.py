from __future__ import annotations

import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.project_ops import (
    extract_notion_id,
    item_from_payload,
    load_project_items,
    notion_connection_status,
    notion_page_to_payload,
    send_digest_email,
    summarize_items,
)


class ProjectOpsTests(unittest.TestCase):
    def test_extract_notion_id_from_url(self) -> None:
        notion_id = extract_notion_id("https://www.notion.so/dc730999bb7140338b871dd33dfbfeec?v=32cef7e6aaa9819b9826000c4b519313")
        self.assertEqual(notion_id, "dc730999-bb71-4033-8b87-1dd33dfbfeec")

    def test_notion_page_to_payload_maps_common_property_types(self) -> None:
        payload = notion_page_to_payload(
            {
                "url": "https://www.notion.so/example-page",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Confirm remote GPU host access"}]},
                    "Status": {"type": "status", "status": {"name": "Todo"}},
                    "Priority": {"type": "select", "select": {"name": "P1"}},
                    "Due Date": {"type": "date", "date": {"start": "2026-03-25"}},
                    "Owner": {"type": "people", "people": [{"name": "Yang Zhipeng"}]},
                    "Blocked": {"type": "checkbox", "checkbox": True},
                    "Summary": {"type": "rich_text", "rich_text": [{"plain_text": "Waiting for remote machine credentials."}]},
                },
            },
            {
                "title": "Name",
                "status": "Status",
                "priority": "Priority",
                "due_date": "Due Date",
                "owner": "Owner",
                "blocked": "Blocked",
                "body": "Summary",
            },
        )
        item = item_from_payload(payload)
        self.assertEqual(item.title, "Confirm remote GPU host access")
        self.assertEqual(item.owner, "Yang Zhipeng")
        self.assertEqual(item.blocked, "Yes")
        self.assertEqual(item.body, "Waiting for remote machine credentials.")
        self.assertEqual(item.notion_url, "https://www.notion.so/example-page")

    def test_load_project_items_auto_falls_back_to_github_when_notion_token_missing(self) -> None:
        with patch("simctl.project_ops.fetch_project_items", return_value=["github"]) as github_fetch:
            items = load_project_items(
                owner="pixmoving-moveit",
                number=2,
                provider="auto",
                notion_cfg={
                    "token_env": "NOTION_TOKEN",
                    "tasks": {"database_url": "https://www.notion.so/dc730999bb7140338b871dd33dfbfeec"},
                },
                source_name="tasks",
            )
        self.assertEqual(items, ["github"])
        github_fetch.assert_called_once_with("pixmoving-moveit", 2)

    def test_notion_connection_status_reports_missing_token(self) -> None:
        status = notion_connection_status(
            {
                "projects": {},
                "notion": {
                    "token_env": "NOTION_TOKEN",
                    "tasks": {"database_url": "https://www.notion.so/dc730999bb7140338b871dd33dfbfeec"},
                },
            }
        )
        self.assertTrue(status["configured"])
        self.assertFalse(status["token_present"])
        self.assertFalse(status["sources"]["tasks"]["reachable"])
        self.assertIn("Missing Notion token", status["sources"]["tasks"]["reason"])

    def test_summarize_items_treats_chinese_done_status_as_done(self) -> None:
        items = [
            item_from_payload(
                {
                    "title": "闭环验收",
                    "status": "完成",
                    "priority": "P0",
                    "track": "Stable Stack",
                    "due Date": "2026-03-20",
                    "owner": "朱民峰",
                    "blocked": "No",
                }
            ),
            item_from_payload(
                {
                    "title": "远端 GPU 准备",
                    "status": "In Progress",
                    "priority": "P1",
                    "track": "UE5 Lab",
                    "due Date": "2026-03-21",
                    "owner": "杨志朋",
                    "blocked": "No",
                }
            ),
        ]

        summary = summarize_items(items, today=date(2026, 3, 22), due_soon_days=3)
        self.assertEqual(summary["active"], 1)
        self.assertEqual([item.title for item in summary["overdue"]], ["远端 GPU 准备"])

    def test_send_digest_email_fails_soft_on_smtp_error(self) -> None:
        config = {"email": {}}
        previous_env = {key: os.environ.get(key) for key in ("TEAM_REMINDER_TO", "SMTP_HOST", "SMTP_FROM")}
        os.environ["TEAM_REMINDER_TO"] = "minfengzhu8@gmail.com"
        os.environ["SMTP_HOST"] = "smtp.example.com"
        os.environ["SMTP_FROM"] = "minfengzhu8@gmail.com"

        try:
            with patch("simctl.project_ops.smtplib.SMTP", side_effect=OSError("network down")):
                result = send_digest_email(
                    config=config,
                    subject="digest",
                    markdown_text="digest",
                    html_text="<p>digest</p>",
                )
        finally:
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertFalse(result["sent"])
        self.assertEqual(result["reason"], "smtp_error")
        self.assertIn("network down", result["error"])


if __name__ == "__main__":
    unittest.main()
