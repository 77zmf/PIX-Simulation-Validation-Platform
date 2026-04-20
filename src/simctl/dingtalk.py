from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def build_dingtalk_signed_url(webhook: str, secret: str, timestamp_ms: int | None = None) -> str:
    timestamp = int(timestamp_ms if timestamp_ms is not None else time.time() * 1000)
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest).decode("utf-8"))
    separator = "&" if "?" in webhook else "?"
    return f"{webhook}{separator}timestamp={timestamp}&sign={sign}"


def build_markdown_payload(title: str, markdown: str, at_mobiles: list[str] | None = None) -> dict[str, Any]:
    at_mobiles = at_mobiles or []
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": markdown,
        },
        "at": {
            "atMobiles": at_mobiles,
            "isAtAll": False,
        },
    }


def build_validation_markdown(run_result: dict[str, Any]) -> str:
    artifacts = run_result.get("artifacts") or {}
    gate = run_result.get("gate") or {}
    runtime_health = run_result.get("runtime_health") or {}
    evidence = run_result.get("runtime_evidence") or {}
    observable = evidence.get("observable") if isinstance(evidence, dict) else {}
    observable = observable if isinstance(observable, dict) else {}

    lines = [
        "## PIX 仿真验证结果",
        "",
        f"- run_id: `{run_result.get('run_id', 'unknown')}`",
        f"- scenario: `{run_result.get('scenario_id', 'unknown')}`",
        f"- status: `{run_result.get('status', 'unknown')}`",
        f"- gate: `{gate.get('gate_id', 'unknown')}` / passed=`{gate.get('passed', 'unknown')}`",
    ]
    if runtime_health:
        lines.append(f"- runtime_health: passed=`{runtime_health.get('passed', 'unknown')}`")
    if run_result.get("slot_id"):
        lines.append(f"- slot: `{run_result.get('slot_id')}`")
    if run_result.get("commit"):
        lines.append(f"- commit: `{run_result.get('commit')}`")
    if observable:
        lines.extend(
            [
                "",
                "### Observable",
                f"- route_completion: `{observable.get('route_completion', 'n/a')}`",
                f"- control_count: `{observable.get('control_count', 'n/a')}`",
                f"- trajectory_count: `{observable.get('trajectory_count', 'n/a')}`",
                f"- max_velocity_mps: `{observable.get('max_velocity_mps', 'n/a')}`",
            ]
        )
    lines.extend(
        [
            "",
            "### Artifacts",
            f"- run_result: `{artifacts.get('run_result', 'n/a')}`",
            f"- health_report: `{artifacts.get('health_report', 'n/a')}`",
            f"- report_dir: `{artifacts.get('report_dir', 'n/a')}`",
        ]
    )
    return "\n".join(lines)


def load_markdown(markdown: str | None, markdown_file: str | None, run_result: str | None) -> str:
    selected = [value is not None for value in (markdown, markdown_file, run_result)]
    if sum(selected) != 1:
        raise ValueError("provide exactly one of --markdown, --markdown-file, or --run-result")
    if markdown is not None:
        return markdown
    if markdown_file is not None:
        return Path(markdown_file).read_text(encoding="utf-8")
    payload = json.loads(Path(str(run_result)).read_text(encoding="utf-8"))
    return build_validation_markdown(payload)


def resolve_webhook(webhook: str | None, webhook_env: str) -> str:
    value = webhook or os.environ.get(webhook_env)
    if not value:
        raise ValueError(f"DingTalk webhook is required; pass --webhook or set {webhook_env}")
    return value


def resolve_secret(secret: str | None, secret_env: str) -> str | None:
    return secret or os.environ.get(secret_env)


def redact_webhook(webhook: str) -> str:
    parsed = urllib.parse.urlsplit(webhook)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted_query = []
    for key, value in query:
        if key.lower() == "access_token" and value:
            value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
        redacted_query.append((key, value))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted_query), parsed.fragment)
    )


def send_dingtalk_markdown(webhook: str, secret: str | None, payload: dict[str, Any], timeout: int = 10) -> dict[str, Any]:
    url = build_dingtalk_signed_url(webhook, secret) if secret else webhook
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DingTalk webhook HTTP {exc.code}: {body}") from exc
    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"DingTalk webhook returned non-JSON response: {body}") from exc
    if result.get("errcode") != 0:
        raise RuntimeError(f"DingTalk webhook failed: {result}")
    return result
