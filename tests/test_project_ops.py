from __future__ import annotations

import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.project_ops import item_from_payload, send_digest_email, summarize_items


class ProjectOpsTests(unittest.TestCase):
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
