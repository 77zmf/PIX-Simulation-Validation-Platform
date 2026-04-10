from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .config import dump_json, ensure_dir, load_yaml
from .reporting import aggregate_run_results, discover_run_results, load_run_result


STATUS_DONE = {"done", "completed", "closed", "finished"}


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
    item_url: str
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
        item_url=_clean_text(normalized.get("item_url") or normalized.get("url")),
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


def load_project_items(
    *,
    owner: str,
    number: int,
    json_override: str | None = None,
    provider: str = "github_project",
    source_name: str = "tasks",
) -> list[ProjectItem]:
    del source_name
    if json_override:
        payload = json.loads(Path(json_override).read_text(encoding="utf-8"))
        return [item_from_payload(item) for item in payload.get("items", [])]

    provider_name = _clean_text(provider) or "github_project"
    if provider_name not in {"github_project", "github", "auto"}:
        raise ValueError(f"Unsupported project provider '{provider_name}'; expected github_project")
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
        "- Source of truth: `GitHub Project`",
        "",
        "## Executive Summary",
        "",
        f"- Active tasks: `{task_summary['active']}` / `{task_summary['total']}`",
        f"- Tasks due within `{due_window}` days: `{len(task_summary['due_soon'])}`",
        f"- Overdue tasks: `{len(task_summary['overdue'])}`",
        f"- Blocked tasks: `{len(task_summary['blocked'])}`",
        f"- Active scenarios: `{scenario_summary['active']}` / `{scenario_summary['total']}`",
        f"- Scenarios due within `{due_window}` days: `{len(scenario_summary['due_soon'])}`",
        f"- Overdue scenarios: `{len(scenario_summary['overdue'])}`",
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
    if not scenario_summary["overdue"] and not scenario_summary["due_soon"]:
        lines.append("- No scenario deadline falls inside the current reminder window.")
        lines.append("")
    else:
        if scenario_summary["overdue"]:
            lines.extend(["### Overdue", ""])
            for item in scenario_summary["overdue"][:8]:
                due = item.due_date.isoformat() if item.due_date else "n/a"
                label = item.severity or item.scenario_type or "Scenario"
                lines.append(f"- `{due}` | `{label}` | **{item.title}** | target: `{item.target_track or item.stack}`")
            lines.append("")
        if scenario_summary["due_soon"]:
            lines.extend([f"### Due In {due_window} Days", ""])
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
            "- E2E shadow reminders stay secondary until the UE4.26 stable path is repeatable.",
            "",
        ]
    )
    return "\n".join(lines)


def render_digest_html(markdown_text: str) -> str:
    escaped = markdown_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
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
