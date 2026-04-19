from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.cli import main
from simctl.dingtalk import build_dingtalk_signed_url, build_validation_markdown, redact_webhook


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class DingTalkTests(unittest.TestCase):
    def test_build_signed_url_matches_dingtalk_hmac_shape(self) -> None:
        url = build_dingtalk_signed_url(
            "https://oapi.dingtalk.com/robot/send?access_token=abc",
            "SEC123",
            timestamp_ms=1700000000000,
        )
        self.assertEqual(
            url,
            "https://oapi.dingtalk.com/robot/send?access_token=abc&timestamp=1700000000000"
            "&sign=lkcPI1uoxBY1gUnCnnPH1Kkru0Hqjo7rFpA3haIVhEQ%3D",
        )

    def test_redact_webhook_hides_access_token(self) -> None:
        redacted = redact_webhook("https://oapi.dingtalk.com/robot/send?access_token=abcdef123456")
        self.assertEqual(redacted, "https://oapi.dingtalk.com/robot/send?access_token=abcd...3456")

    def test_build_validation_markdown_uses_run_result_fields(self) -> None:
        markdown = build_validation_markdown(
            {
                "run_id": "run_001",
                "scenario_id": "l0_smoke",
                "status": "passed",
                "slot_id": "stable-slot-01",
                "gate": {"gate_id": "stable_smoke", "passed": True},
                "artifacts": {"run_result": "runs/run_001/run_result.json", "report_dir": "runs/report"},
            }
        )
        self.assertIn("PIX 仿真验证结果", markdown)
        self.assertIn("run_001", markdown)
        self.assertIn("stable_smoke", markdown)
        self.assertIn("runs/run_001/run_result.json", markdown)

    def test_ding_notify_dry_run_does_not_require_webhook(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(["ding-notify", "--markdown", "## PIX 仿真验证结果\n\n- status: passed"])
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["mode"], "dry-run")
        self.assertFalse(payload["execute"])
        self.assertEqual(payload["payload"]["msgtype"], "markdown")

    def test_ding_notify_execute_posts_payload(self) -> None:
        stream = io.StringIO()
        with (
            patch.dict(
                "os.environ",
                {
                    "DINGTALK_WEBHOOK": "https://oapi.dingtalk.com/robot/send?access_token=abcdef123456",
                    "DINGTALK_SECRET": "SEC123",
                },
            ),
            patch("urllib.request.urlopen", return_value=_FakeResponse('{"errcode":0,"errmsg":"ok"}')) as urlopen,
            redirect_stdout(stream),
        ):
            rc = main(["ding-notify", "--markdown", "## PIX 仿真验证结果\n\n- status: passed", "--execute"])
        self.assertEqual(rc, 0)
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args.args[0]
        self.assertIn("timestamp=", request.full_url)
        self.assertIn("sign=", request.full_url)
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["msgtype"], "markdown")


if __name__ == "__main__":
    unittest.main()
