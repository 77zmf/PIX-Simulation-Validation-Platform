from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import dump_json, ensure_dir, utc_now
from .evaluation import cluster_failures, summarize_statuses


def load_run_result(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_run_results(run_root: Path) -> list[Path]:
    return sorted(run_root.rglob("run_result.json"))


def aggregate_run_results(run_results: list[dict[str, Any]]) -> dict[str, Any]:
    stack_summary: dict[str, dict[str, int]] = {}
    for result in run_results:
        bucket = stack_summary.setdefault(
            result["stack"],
            {"total": 0, "passed": 0, "failed": 0, "planned": 0, "launch_submitted": 0, "launch_failed": 0},
        )
        bucket["total"] += 1
        bucket[result["status"]] = bucket.get(result["status"], 0) + 1
    return {
        "generated_at": utc_now(),
        "total_runs": len(run_results),
        "statuses": summarize_statuses(run_results),
        "stacks": stack_summary,
        "failure_clusters": cluster_failures(run_results),
        "runs": run_results,
    }


def _evidence_items(result: dict[str, Any]) -> list[str]:
    artifacts = result.get("artifacts", {})
    items: list[str] = []
    runtime_health = result.get("runtime_health")
    if isinstance(runtime_health, dict):
        health_label = "passed" if runtime_health.get("passed") else "failed"
        items.append(f"runtime_health:{health_label}")
    if artifacts.get("visual_screenshot"):
        items.append("visual_screenshot")
    if artifacts.get("operator_action_log"):
        items.append("operator_action_log")
    if artifacts.get("health_report"):
        items.append("health_report")
    if artifacts.get("rosbag2"):
        items.append("rosbag2")
    if artifacts.get("carla_recorder"):
        items.append("carla_recorder")
    return items


def _evidence_markdown(result: dict[str, Any]) -> str:
    items = _evidence_items(result)
    if not items:
        return "`none`"
    return "<br>".join(f"`{item}`" for item in items)


def _evidence_html(result: dict[str, Any]) -> str:
    items = _evidence_items(result)
    if not items:
        return "<code>none</code>"
    return "<br>".join(f"<code>{item}</code>" for item in items)


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Simulation Report",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Total runs: `{summary['total_runs']}`",
        "",
        "## Status",
        "",
    ]
    for status, count in sorted(summary["statuses"].items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(
        [
            "",
            "## Stacks",
            "",
            "| Stack | Total | Passed | Failed | Planned | Launch Submitted | Launch Failed |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for stack, bucket in sorted(summary["stacks"].items()):
        lines.append(
            f"| `{stack}` | {bucket.get('total', 0)} | {bucket.get('passed', 0)} | {bucket.get('failed', 0)} | {bucket.get('planned', 0)} | {bucket.get('launch_submitted', 0)} | {bucket.get('launch_failed', 0)} |"
        )
    lines.extend(["", "## Failure Clusters", ""])
    if not summary["failure_clusters"]:
        lines.append("- None")
    else:
        for cluster in summary["failure_clusters"]:
            labels = ", ".join(f"`{label}`" for label in cluster["labels"])
            lines.append(f"- {labels}: {cluster['count']} run(s)")
    lines.extend(
        [
            "",
            "## Runs",
            "",
            "| Run ID | Scenario | Stack | Status | Gate Passed | Evidence |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for result in summary["runs"]:
        gate_passed = result.get("gate", {}).get("passed")
        lines.append(
            f"| `{result['run_id']}` | `{result['scenario_id']}` | `{result['stack']}` | `{result['status']}` | `{gate_passed}` | {_evidence_markdown(result)} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_html(summary: dict[str, Any]) -> str:
    rows = []
    for result in summary["runs"]:
        rows.append(
            "<tr>"
            f"<td><code>{result['run_id']}</code></td>"
            f"<td><code>{result['scenario_id']}</code></td>"
            f"<td><code>{result['stack']}</code></td>"
            f"<td><code>{result['status']}</code></td>"
            f"<td><code>{result.get('gate', {}).get('passed')}</code></td>"
            f"<td>{_evidence_html(result)}</td>"
            "</tr>"
        )
    cluster_items = "".join(
        f"<li><code>{', '.join(cluster['labels'])}</code>: {cluster['count']} run(s)</li>" for cluster in summary["failure_clusters"]
    ) or "<li>None</li>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Simulation Report</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 32px; color: #102039; background: #f6f8fb; }}
    h1, h2 {{ color: #0d274d; }}
    code {{ background: #e8eef9; padding: 2px 4px; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; background: white; }}
    th, td {{ border: 1px solid #d6deee; padding: 8px 10px; text-align: left; }}
    th {{ background: #e8eef9; }}
  </style>
</head>
<body>
  <h1>Simulation Report</h1>
  <p>Generated at <code>{summary['generated_at']}</code></p>
  <p>Total runs: <code>{summary['total_runs']}</code></p>
  <h2>Failure Clusters</h2>
  <ul>{cluster_items}</ul>
  <h2>Runs</h2>
  <table>
    <thead>
      <tr><th>Run ID</th><th>Scenario</th><th>Stack</th><th>Status</th><th>Gate Passed</th><th>Evidence</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""


def write_report(output_dir: Path, summary: dict[str, Any]) -> dict[str, str]:
    ensure_dir(output_dir)
    markdown_path = output_dir / "report.md"
    html_path = output_dir / "report.html"
    summary_path = output_dir / "summary.json"
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    html_path.write_text(render_html(summary), encoding="utf-8")
    dump_json(summary_path, summary)
    return {"markdown": str(markdown_path), "html": str(html_path), "summary": str(summary_path)}
