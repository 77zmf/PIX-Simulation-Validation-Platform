from __future__ import annotations

import json
import os
import re
import shutil
import smtplib
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .config import dump_json, ensure_dir, load_yaml
from .reporting import aggregate_run_results, discover_run_results, load_run_result


STATUS_DONE = {"done", "completed", "完成", "已完成"}
NOTION_API_ROOT = "https://api.notion.com/v1"
DEFAULT_NOTION_VERSION = "2025-09-03"
NOTION_ID_PATTERN = re.compile(
    r"([0-9a-fA-F]{32})|([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
DEFAULT_NOTION_PROPERTY_MAPS = {
    "tasks": {
        "title": "Name",
        "status": "Status",
        "priority": "Priority",
        "phase": "Phase",
        "track": "Track",
        "due_date": "Due Date",
        "owner": "Owner",
        "blocked": "Blocked",
        "body": "Summary",
    },
    "scenarios": {
        "title": "Name",
        "status": "Status",
        "severity": "Severity",
        "stack": "Stack",
        "source": "Source",
        "target_track": "Target Track",
        "scenario_type": "Scenario Type",
        "due_date": "Due Date",
        "success_signal": "Success Signal",
        "body": "Summary",
    },
}


@dataclass(slots=True)
class ProjectItem:
    title: str
    status: str
    due_date: date | None
    owner: str
    priority: str
    phase: str
    track: str
    blocked: str
    notion_url: str
    severity: str
    stack: str
    source: str
    target_track: str
    scenario_type: str
    success_signal: str
    body: str
    raw: dict[str, Any]

    @property
    def is_done(self) -> bool:
        return self.status.strip().lower() in STATUS_DONE

    @property
    def is_blocked(self) -> bool:
        return self.blocked.strip().lower() in {"yes", "true", "__yes__", "blocked"}


def _normalize_key(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _parse_date(value: Any) -> date | None:
    raw = _clean_text(value)
    if not raw:
        return None
    return date.fromisoformat(raw[:10])


def _sort_key(item: ProjectItem) -> tuple[date, str, str]:
    return (item.due_date or date.max, item.priority or item.severity or "ZZZ", item.title)


def item_from_payload(payload: dict[str, Any]) -> ProjectItem:
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        normalized[_normalize_key(key)] = value
    content = payload.get("content", {})
    body = _clean_text(normalized.get("body") or content.get("body", ""))
    title = _clean_text(normalized.get("title") or content.get("title") or payload.get("title"))
    return ProjectItem(
        title=title,
        status=_clean_text(normalized.get("status")),
        due_date=_parse_date(normalized.get("due_date")),
        owner=_clean_text(normalized.get("owner")),
        priority=_clean_text(normalized.get("priority")),
        phase=_clean_text(normalized.get("phase")),
        track=_clean_text(normalized.get("track")),
        blocked=_clean_text(normalized.get("blocked")),
        notion_url=_clean_text(normalized.get("notion_url")),
        severity=_clean_text(normalized.get("severity")),
        stack=_clean_text(normalized.get("stack")),
        source=_clean_text(normalized.get("source")),
        target_track=_clean_text(normalized.get("target_track")),
        scenario_type=_clean_text(normalized.get("scenario_type")),
        success_signal=_clean_text(normalized.get("success_signal")),
        body=body,
        raw=payload,
    )


def _gh_path() -> str:
    gh = shutil.which("gh")
    if gh:
        return gh
    windows_default = Path("C:/Program Files/GitHub CLI/gh.exe")
    if windows_default.exists():
        return str(windows_default)
    raise FileNotFoundError("GitHub CLI is required unless --tasks-json/--scenarios-json are provided")


def fetch_project_items(owner: str, number: int) -> list[ProjectItem]:
    gh = _gh_path()
    result = subprocess.run(
        [gh, "project", "item-list", str(number), "--owner", owner, "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
    )
    payload = json.loads(result.stdout)
    return [item_from_payload(item) for item in payload.get("items", [])]


def extract_notion_id(value: str) -> str:
    raw = _clean_text(value)
    match = NOTION_ID_PATTERN.search(raw)
    if not match:
        raise ValueError(f"Unable to extract a Notion identifier from '{value}'")
    token = match.group(0).replace("-", "")
    return f"{token[0:8]}-{token[8:12]}-{token[12:16]}-{token[16:20]}-{token[20:32]}"


def _notion_token(notion_cfg: dict[str, Any] | None) -> str:
    if not notion_cfg:
        return ""
    direct = _clean_text(notion_cfg.get("token"))
    if direct:
        return direct
    token_env = _clean_text(notion_cfg.get("token_env") or "NOTION_TOKEN")
    return _clean_text(os.environ.get(token_env))


def _notion_version(notion_cfg: dict[str, Any] | None) -> str:
    if not notion_cfg:
        return DEFAULT_NOTION_VERSION
    return _clean_text(notion_cfg.get("version") or DEFAULT_NOTION_VERSION)


def _notion_source_cfg(notion_cfg: dict[str, Any] | None, source_name: str) -> dict[str, Any]:
    if not notion_cfg:
        return {}
    source_cfg = notion_cfg.get(source_name, {})
    return source_cfg if isinstance(source_cfg, dict) else {}


def _notion_has_source_config(notion_cfg: dict[str, Any] | None, source_name: str) -> bool:
    source_cfg = _notion_source_cfg(notion_cfg, source_name)
    return bool(
        source_cfg.get("database_url")
        or source_cfg.get("database_id")
        or source_cfg.get("data_source_id")
        or source_cfg.get("database_id_env")
        or source_cfg.get("data_source_id_env")
    )


def _notion_cfg_value(source_cfg: dict[str, Any], key: str) -> str:
    direct = _clean_text(source_cfg.get(key))
    if direct:
        return direct
    env_name = _clean_text(source_cfg.get(f"{key}_env"))
    if env_name:
        return _clean_text(os.environ.get(env_name))
    return ""


def _notion_error_message(exc: HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:
        payload = {}
    detail = _clean_text(payload.get("message") or payload.get("code") or "")
    if detail:
        return f"HTTP {exc.code}: {detail}"
    return f"HTTP {exc.code}"


def _notion_request_json(
    method: str,
    path: str,
    *,
    token: str,
    version: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(f"{NOTION_API_ROOT}{path}", method=method, data=data)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Notion-Version", version)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"Notion API {method} {path} failed: {_notion_error_message(exc)}") from exc
    return json.loads(raw) if raw else {}


def _notion_plain_text(items: list[dict[str, Any]]) -> str:
    return "".join(_clean_text(item.get("plain_text")) for item in items)


def _notion_person_text(items: list[dict[str, Any]]) -> str:
    labels = []
    for item in items:
        name = _clean_text(item.get("name"))
        if name:
            labels.append(name)
            continue
        person = item.get("person", {})
        email = _clean_text(person.get("email"))
        if email:
            labels.append(email)
            continue
        labels.append(_clean_text(item.get("id")))
    return ", ".join(label for label in labels if label)


def _notion_formula_text(value: dict[str, Any]) -> str:
    formula_type = value.get("type")
    if formula_type == "string":
        return _clean_text(value.get("string"))
    if formula_type == "number":
        number = value.get("number")
        return "" if number is None else str(number)
    if formula_type == "boolean":
        return "Yes" if value.get("boolean") else "No"
    if formula_type == "date":
        date_payload = value.get("date") or {}
        return _clean_text(date_payload.get("start"))
    return ""


def _notion_property_value(prop: dict[str, Any]) -> str:
    prop_type = prop.get("type")
    if prop_type == "title":
        return _notion_plain_text(prop.get("title", []))
    if prop_type == "rich_text":
        return _notion_plain_text(prop.get("rich_text", []))
    if prop_type == "status":
        return _clean_text((prop.get("status") or {}).get("name"))
    if prop_type == "select":
        return _clean_text((prop.get("select") or {}).get("name"))
    if prop_type == "multi_select":
        return ", ".join(_clean_text(item.get("name")) for item in prop.get("multi_select", []) if item.get("name"))
    if prop_type == "date":
        return _clean_text((prop.get("date") or {}).get("start"))
    if prop_type == "checkbox":
        return "Yes" if prop.get("checkbox") else "No"
    if prop_type == "people":
        return _notion_person_text(prop.get("people", []))
    if prop_type == "url":
        return _clean_text(prop.get("url"))
    if prop_type == "email":
        return _clean_text(prop.get("email"))
    if prop_type == "phone_number":
        return _clean_text(prop.get("phone_number"))
    if prop_type == "number":
        number = prop.get("number")
        return "" if number is None else str(number)
    if prop_type == "formula":
        return _notion_formula_text(prop.get("formula") or {})
    if prop_type == "relation":
        return ", ".join(_clean_text(item.get("id")) for item in prop.get("relation", []) if item.get("id"))
    if prop_type == "created_time":
        return _clean_text(prop.get("created_time"))
    if prop_type == "last_edited_time":
        return _clean_text(prop.get("last_edited_time"))
    if prop_type == "created_by":
        return _clean_text((prop.get("created_by") or {}).get("name"))
    if prop_type == "last_edited_by":
        return _clean_text((prop.get("last_edited_by") or {}).get("name"))
    return ""


def _notion_default_title(properties: dict[str, Any]) -> str:
    for prop in properties.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return _notion_property_value(prop)
    return ""


def notion_page_to_payload(page: dict[str, Any], property_map: dict[str, str]) -> dict[str, Any]:
    properties = page.get("properties", {})
    payload: dict[str, Any] = {}
    for target_key, notion_name in property_map.items():
        if not notion_name:
            continue
        prop = properties.get(notion_name)
        payload[target_key] = _notion_property_value(prop) if isinstance(prop, dict) else ""

    payload.setdefault("title", _notion_default_title(properties))
    payload.setdefault("notion_url", _clean_text(page.get("url")))
    body = _clean_text(payload.get("body"))
    if body:
        payload["content"] = {"body": body}
    return payload


def _notion_resolve_data_source_id(source_cfg: dict[str, Any], *, token: str, version: str) -> str:
    direct_data_source = _notion_cfg_value(source_cfg, "data_source_id")
    if direct_data_source:
        return extract_notion_id(direct_data_source)

    database_ref = _notion_cfg_value(source_cfg, "database_id") or _notion_cfg_value(source_cfg, "database_url")
    if not database_ref:
        raise ValueError("Notion source config requires database_url, database_id, or data_source_id")

    database_id = extract_notion_id(database_ref)
    database = _notion_request_json("GET", f"/databases/{database_id}", token=token, version=version)
    data_sources = database.get("data_sources", [])
    if not data_sources:
        raise RuntimeError(f"Database {database_id} has no accessible data sources")

    preferred_name = _clean_text(source_cfg.get("data_source_name"))
    if preferred_name:
        for entry in data_sources:
            if _clean_text(entry.get("name")) == preferred_name:
                return extract_notion_id(entry["id"])
        raise RuntimeError(f"Unable to find Notion data source named '{preferred_name}' in database {database_id}")
    return extract_notion_id(data_sources[0]["id"])


def fetch_notion_items(*, notion_cfg: dict[str, Any], source_name: str) -> list[ProjectItem]:
    token = _notion_token(notion_cfg)
    if not token:
        token_env = _clean_text((notion_cfg or {}).get("token_env") or "NOTION_TOKEN")
        raise RuntimeError(f"Missing Notion token in env '{token_env}'")

    source_cfg = _notion_source_cfg(notion_cfg, source_name)
    if not source_cfg:
        raise ValueError(f"Missing notion.{source_name} configuration")

    version = _notion_version(notion_cfg)
    data_source_id = _notion_resolve_data_source_id(source_cfg, token=token, version=version)
    property_map = dict(DEFAULT_NOTION_PROPERTY_MAPS.get(source_name, {}))
    property_map.update(source_cfg.get("property_map", {}))
    query_payload: dict[str, Any] = {
        "page_size": int(source_cfg.get("page_size", 100)),
    }
    if "filter" in source_cfg:
        query_payload["filter"] = source_cfg["filter"]
    if "sorts" in source_cfg:
        query_payload["sorts"] = source_cfg["sorts"]

    pages: list[dict[str, Any]] = []
    next_cursor: str | None = None
    while True:
        payload = dict(query_payload)
        if next_cursor:
            payload["start_cursor"] = next_cursor
        response = _notion_request_json(
            "POST",
            f"/data_sources/{data_source_id}/query",
            token=token,
            version=version,
            payload=payload,
        )
        pages.extend(result for result in response.get("results", []) if result.get("object") == "page")
        if not response.get("has_more"):
            break
        next_cursor = _clean_text(response.get("next_cursor"))
        if not next_cursor:
            break

    return [item_from_payload(notion_page_to_payload(page, property_map)) for page in pages]


def notion_connection_status(config: dict[str, Any]) -> dict[str, Any]:
    notion_cfg = config.get("notion") if isinstance(config.get("notion"), dict) else {}
    token_env = _clean_text((notion_cfg or {}).get("token_env") or "NOTION_TOKEN")
    token = _notion_token(notion_cfg)
    version = _notion_version(notion_cfg)
    status: dict[str, Any] = {
        "configured": bool(notion_cfg),
        "token_env": token_env,
        "token_present": bool(token),
        "version": version,
        "sources": {},
    }
    if not notion_cfg:
        return status

    for source_name in ("tasks", "scenarios"):
        source_cfg = _notion_source_cfg(notion_cfg, source_name)
        if not source_cfg:
            continue
        source_status: dict[str, Any] = {"configured": True}
        try:
            if not token:
                raise RuntimeError(f"Missing Notion token in env '{token_env}'")
            data_source_id = _notion_resolve_data_source_id(source_cfg, token=token, version=version)
            data_source = _notion_request_json(
                "GET",
                f"/data_sources/{data_source_id}",
                token=token,
                version=version,
            )
            source_status.update(
                {
                    "reachable": True,
                    "data_source_id": data_source_id,
                    "title": _clean_text(data_source.get("name")),
                    "properties": sorted(str(name) for name in (data_source.get("properties") or {}).keys()),
                }
            )
        except Exception as exc:
            source_status.update({"reachable": False, "reason": str(exc)})
        status["sources"][source_name] = source_status
    return status


def load_project_items(
    *,
    owner: str,
    number: int,
    json_override: str | None = None,
    provider: str = "github_project",
    notion_cfg: dict[str, Any] | None = None,
    source_name: str = "tasks",
) -> list[ProjectItem]:
    if json_override:
        payload = json.loads(Path(json_override).read_text(encoding="utf-8"))
        return [item_from_payload(item) for item in payload.get("items", [])]
    provider_name = _clean_text(provider) or "github_project"
    if provider_name == "notion":
        return fetch_notion_items(notion_cfg=notion_cfg or {}, source_name=source_name)
    if provider_name == "auto" and _notion_has_source_config(notion_cfg, source_name) and _notion_token(notion_cfg):
        return fetch_notion_items(notion_cfg=notion_cfg or {}, source_name=source_name)
    return fetch_project_items(owner, number)


def load_run_summary(run_root: Path) -> dict[str, Any] | None:
    report_summary = run_root / "report" / "summary.json"
    if report_summary.exists():
        return json.loads(report_summary.read_text(encoding="utf-8"))
    run_result_paths = discover_run_results(run_root)
    if not run_result_paths:
        return None
    results = [load_run_result(path) for path in run_result_paths]
    return aggregate_run_results(results)


def summarize_items(items: list[ProjectItem], *, today: date, due_soon_days: int) -> dict[str, Any]:
    statuses = Counter()
    tracks = Counter()
    priorities = Counter()
    overdue: list[ProjectItem] = []
    due_soon: list[ProjectItem] = []
    blocked: list[ProjectItem] = []

    horizon = today + timedelta(days=due_soon_days)
    for item in items:
        statuses[item.status or "Unknown"] += 1
        track_name = item.track or item.target_track or item.stack or "Unknown"
        tracks[track_name] += 1
        priority_name = item.priority or item.severity or "Unspecified"
        priorities[priority_name] += 1
        if item.is_blocked:
            blocked.append(item)
        if item.is_done or item.due_date is None:
            continue
        if item.due_date < today:
            overdue.append(item)
        elif item.due_date <= horizon:
            due_soon.append(item)

    active = [item for item in items if not item.is_done]
    return {
        "total": len(items),
        "active": len(active),
        "statuses": dict(statuses),
        "tracks": dict(tracks),
        "priorities": dict(priorities),
        "overdue": sorted(overdue, key=_sort_key),
        "due_soon": sorted(due_soon, key=_sort_key),
        "blocked": sorted(blocked, key=_sort_key),
        "active_items": sorted(active, key=_sort_key),
    }


def _owner_buckets(task_summary: dict[str, Any]) -> dict[str, list[ProjectItem]]:
    buckets: dict[str, list[ProjectItem]] = defaultdict(list)
    for item in task_summary["overdue"] + task_summary["due_soon"]:
        owner = item.owner or "Unassigned"
        buckets[owner].append(item)
    return {owner: sorted(items, key=_sort_key) for owner, items in sorted(buckets.items())}


def _format_item_line(item: ProjectItem, *, label: str) -> str:
    due = item.due_date.isoformat() if item.due_date else "n/a"
    return f"- `{due}` | `{label}` | **{item.title}** | owner: `{item.owner or 'Unassigned'}`"


def _render_run_section(run_summary: dict[str, Any] | None) -> list[str]:
    if run_summary is None:
        return [
            "## Validation Snapshot",
            "",
            "- No `run_result.json` data is currently available in the repo workspace.",
            "",
        ]

    lines = [
        "## Validation Snapshot",
        "",
        f"- Total runs: `{run_summary['total_runs']}`",
        "",
        "### Status Counts",
        "",
    ]
    for status, count in sorted(run_summary.get("statuses", {}).items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "### Failure Clusters", ""])
    clusters = run_summary.get("failure_clusters", [])
    if not clusters:
        lines.append("- None")
    else:
        for cluster in clusters[:5]:
            labels = ", ".join(cluster.get("labels", []))
            lines.append(f"- `{labels}`: {cluster.get('count', 0)} run(s)")
    lines.append("")
    return lines


def render_digest_markdown(
    *,
    config: dict[str, Any],
    today: date,
    task_summary: dict[str, Any],
    scenario_summary: dict[str, Any],
    run_summary: dict[str, Any] | None,
) -> str:
    due_window = int(config.get("reporting", {}).get("due_soon_days", 3))
    task_project = config["projects"]["tasks"]
    scenario_project = config["projects"]["scenarios"]
    lines = [
        "# Project Digest",
        "",
        f"- Date: `{today.isoformat()}`",
        f"- Task project: [#{task_project['number']}]({task_project['url']})",
        f"- Scenario project: [#{scenario_project['number']}]({scenario_project['url']})",
        "",
        "## Executive Summary",
        "",
        f"- Active tasks: `{task_summary['active']}` / `{task_summary['total']}`",
        f"- Tasks due within `{due_window}` days: `{len(task_summary['due_soon'])}`",
        f"- Overdue tasks: `{len(task_summary['overdue'])}`",
        f"- Blocked tasks: `{len(task_summary['blocked'])}`",
        f"- Active scenarios: `{scenario_summary['active']}` / `{scenario_summary['total']}`",
        f"- Scenarios due within `{due_window}` days: `{len(scenario_summary['due_soon'])}`",
        "",
        "## Task Watchlist",
        "",
    ]
    if not task_summary["overdue"] and not task_summary["due_soon"]:
        lines.append("- No task deadlines need attention in the current window.")
    else:
        if task_summary["overdue"]:
            lines.extend(["### Overdue", ""])
            for item in task_summary["overdue"][:8]:
                lines.append(_format_item_line(item, label=item.priority or "Task"))
            lines.append("")
        if task_summary["due_soon"]:
            lines.extend([f"### Due In {due_window} Days", ""])
            for item in task_summary["due_soon"][:10]:
                lines.append(_format_item_line(item, label=item.priority or "Task"))
            lines.append("")

    lines.extend(["## Blockers", ""])
    if not task_summary["blocked"]:
        lines.append("- No blocked task is marked in the GitHub task board.")
        lines.append("")
    else:
        for item in task_summary["blocked"]:
            due = item.due_date.isoformat() if item.due_date else "n/a"
            lines.append(f"- `{due}` | **{item.title}** | owner: `{item.owner or 'Unassigned'}`")
        lines.append("")

    lines.extend(["## Scenario Watchlist", ""])
    if not scenario_summary["due_soon"]:
        lines.append("- No scenario deadline falls inside the current reminder window.")
        lines.append("")
    else:
        for item in scenario_summary["due_soon"][:8]:
            due = item.due_date.isoformat() if item.due_date else "n/a"
            label = item.severity or item.scenario_type or "Scenario"
            lines.append(f"- `{due}` | `{label}` | **{item.title}** | target: `{item.target_track or item.stack}`")
        lines.append("")

    lines.extend(["## Owner Actions", ""])
    owner_buckets = _owner_buckets(task_summary)
    if not owner_buckets:
        lines.append("- No owner action is generated from the current task deadlines.")
        lines.append("")
    else:
        for owner, items in owner_buckets.items():
            lines.append(f"### {owner}")
            lines.append("")
            for item in items[:5]:
                due = item.due_date.isoformat() if item.due_date else "n/a"
                lines.append(f"- `{due}` | **{item.title}** | `{item.priority or item.track or 'Task'}`")
            lines.append("")

    lines.extend(_render_run_section(run_summary))
    lines.extend(
        [
            "## Delivery Rule",
            "",
            "- Stable closed-loop delivery remains the quarter gate.",
            "- Site proxy and corner cases must accumulate as reusable assets, not one-off scripts.",
            "- UE5 / E2E reminders are preparation items until the stable path is repeatable.",
            "",
        ]
    )
    return "\n".join(lines)


def render_digest_html(markdown_text: str) -> str:
    escaped = (
        markdown_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Project Digest</title>"
        "<style>"
        "body{font-family:Segoe UI,Arial,sans-serif;margin:32px;background:#f6f8fb;color:#102039;}"
        "pre{white-space:pre-wrap;line-height:1.6;background:#fff;padding:24px;border:1px solid #dbe3ee;border-radius:16px;}"
        "</style></head><body><pre>"
        f"{escaped}"
        "</pre></body></html>"
    )


def load_project_automation_config(path: Path) -> dict[str, Any]:
    config = load_yaml(path)
    if "projects" not in config:
        raise ValueError(f"{path} must define a 'projects' mapping")
    return config


def _resolve_csv_env(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def send_digest_email(
    *,
    config: dict[str, Any],
    subject: str,
    markdown_text: str,
    html_text: str,
) -> dict[str, Any]:
    email_cfg = config.get("email", {})
    recipients = _resolve_csv_env(email_cfg.get("recipients_env", "TEAM_REMINDER_TO"))
    cc = _resolve_csv_env(email_cfg.get("cc_env", "TEAM_REMINDER_CC"))
    smtp_host = os.environ.get(email_cfg.get("smtp_host_env", "SMTP_HOST"), "")
    smtp_port_raw = os.environ.get(email_cfg.get("smtp_port_env", "SMTP_PORT"), "") or "587"
    smtp_port = int(smtp_port_raw)
    smtp_username = os.environ.get(email_cfg.get("smtp_username_env", "SMTP_USERNAME"), "")
    smtp_password = os.environ.get(email_cfg.get("smtp_password_env", "SMTP_PASSWORD"), "")
    smtp_from = os.environ.get(email_cfg.get("smtp_from_env", "SMTP_FROM"), "")
    use_starttls = str(os.environ.get(email_cfg.get("smtp_starttls_env", "SMTP_STARTTLS"), "true")).lower() != "false"

    if not recipients:
        return {"sent": False, "reason": "missing_recipients"}
    if not smtp_host or not smtp_from:
        return {"sent": False, "reason": "missing_smtp_configuration", "recipients": recipients, "cc": cc}

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = ", ".join(recipients)
    if cc:
        message["Cc"] = ", ".join(cc)
    message.set_content(markdown_text)
    message.add_alternative(html_text, subtype="html")

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            if use_starttls:
                server.starttls()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        return {
            "sent": False,
            "reason": "smtp_error",
            "error": str(exc),
            "recipients": recipients,
            "cc": cc,
        }

    return {"sent": True, "reason": "delivered", "recipients": recipients, "cc": cc}


def write_digest_outputs(
    *,
    output_dir: Path,
    markdown_text: str,
    html_text: str,
    payload: dict[str, Any],
) -> dict[str, str]:
    ensure_dir(output_dir)
    markdown_path = output_dir / "digest.md"
    html_path = output_dir / "digest.html"
    summary_path = output_dir / "digest_summary.json"
    markdown_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    dump_json(summary_path, payload)
    return {"markdown": str(markdown_path), "html": str(html_path), "summary": str(summary_path)}
