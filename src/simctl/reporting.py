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


def _metric_stats(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def summarize_shadow_comparison(run_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    profile_buckets: dict[str, dict[str, Any]] = {}
    shared_metric_order: list[str] = []
    profile_specific_metric_order: list[str] = []

    for result in run_results:
        algorithm = result.get("resolved_profiles", {}).get("algorithm", {})
        if not isinstance(algorithm, dict):
            continue
        interface_contract = algorithm.get("interface_contract", {})
        if not isinstance(interface_contract, dict):
            continue
        comparison_metrics = interface_contract.get("comparison_metrics", {})
        if not isinstance(comparison_metrics, dict):
            continue

        common_metrics = [str(name) for name in comparison_metrics.get("common", [])]
        if not common_metrics:
            continue

        profile_specific_metrics = [str(name) for name in comparison_metrics.get("profile_specific", [])]
        profile_id = str(algorithm.get("profile_id") or result.get("scenario_params", {}).get("algorithm_profile") or "unknown")
        bucket = profile_buckets.setdefault(
            profile_id,
            {
                "profile_id": profile_id,
                "run_count": 0,
                "passed_runs": 0,
                "gate_passed_runs": 0,
                "scenario_ids": [],
                "shared_metric_stats": {},
                "profile_specific_metric_stats": {},
            },
        )

        bucket["run_count"] += 1
        if result.get("status") == "passed":
            bucket["passed_runs"] += 1
        if result.get("gate", {}).get("passed"):
            bucket["gate_passed_runs"] += 1

        scenario_id = str(result.get("scenario_id", "unknown"))
        if scenario_id not in bucket["scenario_ids"]:
            bucket["scenario_ids"].append(scenario_id)

        kpis = result.get("kpis", {})
        if not isinstance(kpis, dict):
            kpis = {}

        for name in common_metrics:
            if name not in shared_metric_order:
                shared_metric_order.append(name)
            value = kpis.get(name)
            if isinstance(value, (int, float)):
                bucket["shared_metric_stats"].setdefault(name, []).append(float(value))

        for name in profile_specific_metrics:
            if name not in profile_specific_metric_order:
                profile_specific_metric_order.append(name)
            value = kpis.get(name)
            if isinstance(value, (int, float)):
                bucket["profile_specific_metric_stats"].setdefault(name, []).append(float(value))

    if not profile_buckets:
        return None

    profiles = []
    for profile_id in sorted(profile_buckets):
        bucket = profile_buckets[profile_id]
        profiles.append(
            {
                "profile_id": bucket["profile_id"],
                "run_count": bucket["run_count"],
                "passed_runs": bucket["passed_runs"],
                "gate_passed_runs": bucket["gate_passed_runs"],
                "scenario_ids": bucket["scenario_ids"],
                "shared_metric_stats": {
                    name: _metric_stats(values)
                    for name, values in sorted(bucket["shared_metric_stats"].items())
                    if values
                },
                "profile_specific_metric_stats": {
                    name: _metric_stats(values)
                    for name, values in sorted(bucket["profile_specific_metric_stats"].items())
                    if values
                },
            }
        )

    return {
        "profile_count": len(profiles),
        "shared_metric_order": shared_metric_order,
        "profile_specific_metric_order": profile_specific_metric_order,
        "profiles": profiles,
    }


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
        "shadow_comparison": summarize_shadow_comparison(run_results),
        "runs": run_results,
    }


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
    shadow_comparison = summary.get("shadow_comparison")
    if shadow_comparison:
        lines.extend(
            [
                "",
                "## Shadow Comparison",
                "",
                f"- Profiles compared: `{shadow_comparison['profile_count']}`",
                "",
            ]
        )
        shared_metrics = list(shadow_comparison.get("shared_metric_order", []))
        if shared_metrics:
            header = "| Profile | Runs | Gate Passed | " + " | ".join(f"{metric} avg" for metric in shared_metrics) + " |"
            separator = "| --- | ---: | ---: | " + " | ".join("---:" for _ in shared_metrics) + " |"
            lines.extend([header, separator])
            for profile in shadow_comparison["profiles"]:
                stats = profile.get("shared_metric_stats", {})
                metric_cells = []
                for metric in shared_metrics:
                    metric_stat = stats.get(metric)
                    metric_cells.append("n/a" if metric_stat is None else str(metric_stat["avg"]))
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            f"`{profile['profile_id']}`",
                            str(profile["run_count"]),
                            str(profile["gate_passed_runs"]),
                            *metric_cells,
                        ]
                    )
                    + " |"
                )
        profile_specific_metrics = list(shadow_comparison.get("profile_specific_metric_order", []))
        if profile_specific_metrics:
            lines.extend(["", "### Profile-Specific Signals", ""])
            for profile in shadow_comparison["profiles"]:
                stats = profile.get("profile_specific_metric_stats", {})
                rendered = ", ".join(
                    f"`{metric}` avg={stats[metric]['avg']}" for metric in profile_specific_metrics if metric in stats
                )
                if rendered:
                    lines.append(f"- `{profile['profile_id']}`: {rendered}")
    lines.extend(["", "## Runs", "", "| Run ID | Scenario | Stack | Status | Gate Passed |", "| --- | --- | --- | --- | --- |"])
    for result in summary["runs"]:
        gate_passed = result.get("gate", {}).get("passed")
        lines.append(
            f"| `{result['run_id']}` | `{result['scenario_id']}` | `{result['stack']}` | `{result['status']}` | `{gate_passed}` |"
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
            "</tr>"
        )
    cluster_items = "".join(
        f"<li><code>{', '.join(cluster['labels'])}</code>: {cluster['count']} run(s)</li>" for cluster in summary["failure_clusters"]
    ) or "<li>None</li>"
    shadow_section = ""
    shadow_comparison = summary.get("shadow_comparison")
    if shadow_comparison:
        shared_metrics = list(shadow_comparison.get("shared_metric_order", []))
        if shared_metrics:
            shadow_header = "".join(f"<th>{metric} avg</th>" for metric in shared_metrics)
            shadow_rows = []
            for profile in shadow_comparison["profiles"]:
                stats = profile.get("shared_metric_stats", {})
                metric_cells = "".join(
                    f"<td><code>{stats[metric]['avg'] if metric in stats else 'n/a'}</code></td>" for metric in shared_metrics
                )
                shadow_rows.append(
                    "<tr>"
                    f"<td><code>{profile['profile_id']}</code></td>"
                    f"<td><code>{profile['run_count']}</code></td>"
                    f"<td><code>{profile['gate_passed_runs']}</code></td>"
                    f"{metric_cells}"
                    "</tr>"
                )
            shadow_section = (
                "<h2>Shadow Comparison</h2>"
                f"<p>Profiles compared: <code>{shadow_comparison['profile_count']}</code></p>"
                "<table><thead><tr><th>Profile</th><th>Runs</th><th>Gate Passed</th>"
                f"{shadow_header}</tr></thead><tbody>{''.join(shadow_rows)}</tbody></table>"
            )
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
  {shadow_section}
  <h2>Runs</h2>
  <table>
    <thead>
      <tr><th>Run ID</th><th>Scenario</th><th>Stack</th><th>Status</th><th>Gate Passed</th></tr>
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
