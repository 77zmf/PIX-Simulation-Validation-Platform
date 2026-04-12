from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import dump_json, ensure_dir, utc_now
from .evaluation import cluster_failures, load_kpi_gate, summarize_statuses


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


def _format_threshold(rule: dict[str, Any]) -> str:
    return f"{rule['op']}{rule['value']}"


def _display_profile_name(profile_id: str) -> str:
    return {
        "perception_bevfusion_public_road": "BEVFusion perception baseline",
        "e2e_bevfusion_uniad_shadow": "UniAD-style shadow",
        "e2e_bevfusion_vadv2_shadow": "VADv2 shadow",
    }.get(profile_id, profile_id)


def _result_profile_id(result: dict[str, Any]) -> str:
    algorithm = result.get("resolved_profiles", {}).get("algorithm", {})
    if isinstance(algorithm, dict):
        profile_id = algorithm.get("profile_id")
        if profile_id:
            return str(profile_id)
    scenario_params = result.get("scenario_params", {})
    if isinstance(scenario_params, dict) and scenario_params.get("algorithm_profile"):
        return str(scenario_params["algorithm_profile"])
    return "unknown"


def summarize_shadow_comparison(run_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    profile_buckets: dict[str, dict[str, Any]] = {}
    shared_metric_order: list[str] = []
    profile_specific_metric_order: list[str] = []
    gate_cache: dict[str, dict[str, Any]] = {}

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
                "comparison_ready_runs": 0,
                "passed_runs": 0,
                "gate_passed_runs": 0,
                "gate_id": None,
                "scenario_ids": [],
                "shared_metric_stats": {},
                "shared_metric_coverage": {},
                "shared_metric_verdicts": {},
                "profile_specific_metric_stats": {},
                "profile_specific_metric_coverage": {},
                "profile_specific_metric_verdicts": {},
                "comparison_gaps": [],
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

        gate_id = str(result.get("gate", {}).get("gate_id", ""))
        if gate_id and bucket["gate_id"] is None:
            bucket["gate_id"] = gate_id
        gate_metrics: dict[str, dict[str, Any]] = {}
        if gate_id:
            cached_gate = gate_cache.get(gate_id)
            if cached_gate is None:
                gate = load_kpi_gate(gate_id)
                cached_gate = gate.metrics
                gate_cache[gate_id] = cached_gate
            gate_metrics = cached_gate

        kpis = result.get("kpis", {})
        if not isinstance(kpis, dict):
            kpis = {}
        gate_violations = {
            str(item.get("metric")): item for item in result.get("gate", {}).get("violations", []) if item.get("metric")
        }

        missing_shared_metrics: list[str] = []
        for name in common_metrics:
            if name not in shared_metric_order:
                shared_metric_order.append(name)
            verdict = bucket["shared_metric_verdicts"].setdefault(
                name,
                {
                    "threshold": _format_threshold(gate_metrics[name]) if name in gate_metrics else None,
                    "passed_runs": 0,
                    "failed_runs": 0,
                    "missing_runs": 0,
                },
            )
            value = kpis.get(name)
            if isinstance(value, (int, float)):
                bucket["shared_metric_stats"].setdefault(name, []).append(float(value))
                bucket["shared_metric_coverage"][name] = bucket["shared_metric_coverage"].get(name, 0) + 1
                if name in gate_violations:
                    verdict["failed_runs"] += 1
                else:
                    verdict["passed_runs"] += 1
            else:
                missing_shared_metrics.append(name)
                verdict["missing_runs"] += 1

        missing_profile_specific_metrics: list[str] = []
        for name in profile_specific_metrics:
            if name not in profile_specific_metric_order:
                profile_specific_metric_order.append(name)
            verdict = bucket["profile_specific_metric_verdicts"].setdefault(
                name,
                {
                    "threshold": _format_threshold(gate_metrics[name]) if name in gate_metrics else None,
                    "passed_runs": 0,
                    "failed_runs": 0,
                    "missing_runs": 0,
                },
            )
            value = kpis.get(name)
            if isinstance(value, (int, float)):
                bucket["profile_specific_metric_stats"].setdefault(name, []).append(float(value))
                bucket["profile_specific_metric_coverage"][name] = bucket["profile_specific_metric_coverage"].get(name, 0) + 1
                if name in gate_violations:
                    verdict["failed_runs"] += 1
                else:
                    verdict["passed_runs"] += 1
            else:
                missing_profile_specific_metrics.append(name)
                verdict["missing_runs"] += 1

        if not missing_shared_metrics:
            bucket["comparison_ready_runs"] += 1
        if missing_shared_metrics or missing_profile_specific_metrics:
            bucket["comparison_gaps"].append(
                {
                    "run_id": str(result.get("run_id", "unknown")),
                    "scenario_id": scenario_id,
                    "missing_shared_metrics": missing_shared_metrics,
                    "missing_profile_specific_metrics": missing_profile_specific_metrics,
                }
            )

    if not profile_buckets:
        return None

    profiles = []
    for profile_id in sorted(profile_buckets):
        bucket = profile_buckets[profile_id]
        profiles.append(
            {
                "profile_id": bucket["profile_id"],
                "run_count": bucket["run_count"],
                "comparison_ready_runs": bucket["comparison_ready_runs"],
                "passed_runs": bucket["passed_runs"],
                "gate_passed_runs": bucket["gate_passed_runs"],
                "gate_id": bucket["gate_id"],
                "scenario_ids": bucket["scenario_ids"],
                "shared_metric_stats": {
                    name: _metric_stats(values)
                    for name, values in sorted(bucket["shared_metric_stats"].items())
                    if values
                },
                "shared_metric_coverage": {
                    name: {
                        "present_runs": count,
                        "run_count": bucket["run_count"],
                        "ratio": round(count / bucket["run_count"], 4),
                    }
                    for name, count in sorted(bucket["shared_metric_coverage"].items())
                },
                "shared_metric_verdicts": {
                    name: {
                        **verdict,
                        "run_count": bucket["run_count"],
                    }
                    for name, verdict in sorted(bucket["shared_metric_verdicts"].items())
                },
                "profile_specific_metric_stats": {
                    name: _metric_stats(values)
                    for name, values in sorted(bucket["profile_specific_metric_stats"].items())
                    if values
                },
                "profile_specific_metric_coverage": {
                    name: {
                        "present_runs": count,
                        "run_count": bucket["run_count"],
                        "ratio": round(count / bucket["run_count"], 4),
                    }
                    for name, count in sorted(bucket["profile_specific_metric_coverage"].items())
                },
                "profile_specific_metric_verdicts": {
                    name: {
                        **verdict,
                        "run_count": bucket["run_count"],
                    }
                    for name, verdict in sorted(bucket["profile_specific_metric_verdicts"].items())
                },
                "comparison_gaps": bucket["comparison_gaps"],
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


def render_issue_update(summary: dict[str, Any]) -> str:
    shadow_comparison = summary.get("shadow_comparison")
    shadow_profiles = []
    if shadow_comparison:
        shadow_profiles = list(shadow_comparison.get("profiles", []))

    lines = ["本周研究结论："]
    lines.append(f"- 当前 `simctl report` 共汇总 `{summary['total_runs']}` 条运行结果。")
    if shadow_comparison:
        lines.append(
            "- `Shadow Comparison` 已覆盖 "
            + "、".join(f"`{_display_profile_name(profile['profile_id'])}`" for profile in shadow_profiles)
            + "。"
        )
        gap_count = sum(len(profile.get("comparison_gaps", [])) for profile in shadow_profiles)
        if gap_count:
            lines.append(f"- 当前仍有 `{gap_count}` 条 comparison gap，需要先补齐缺失指标再做正式比较。")
        else:
            lines.append("- 当前 `Comparison Gaps` 为 `None`，共享指标已经具备同口径比较条件。")
    else:
        lines.append("- 当前报告里还没有 shadow comparison 数据，尚不能形成 `UniAD-style / VADv2` 对照结论。")

    lines.extend(["", "接口草案变化："])
    lines.append("- 本次报告不新增接口字段，继续沿用 `2026q2-shadow-v1` 契约。")
    lines.append("- `BEVFusion` 仍作为感知基线，`UniAD-style / VADv2` 仍然只做 `shadow` 旁路比较。")

    lines.extend(["", "指标口径变化："])
    if shadow_comparison:
        lines.append(
            "- 共享指标继续沿用 "
            + "、".join(f"`{metric}`" for metric in shadow_comparison.get("shared_metric_order", []))
            + "。"
        )
        for metric in shadow_comparison.get("shared_metric_order", []):
            parts = []
            for profile in shadow_profiles:
                stat = profile.get("shared_metric_stats", {}).get(metric)
                verdict = profile.get("shared_metric_verdicts", {}).get(metric, {})
                avg = "n/a" if stat is None else stat["avg"]
                threshold = verdict.get("threshold") or "n/a"
                parts.append(
                    f"`{_display_profile_name(profile['profile_id'])}` avg=`{avg}` threshold=`{threshold}`"
                )
            lines.append(f"- `{metric}`: " + "；".join(parts))
    else:
        lines.append("- 当前没有可汇总的 shadow 共享指标。")

    lines.extend(["", "当前假设："])
    lines.append("- 当前摘要来自 `simctl report` 汇总结果；正式验收仍应以公司 `Ubuntu 22.04` 主机上的真实 `--execute` 产物为准。")

    lines.extend(["", "当前 blocker："])
    if not shadow_comparison:
        lines.append("- 还缺带有 `comparison_metrics` 的 shadow 运行结果，暂时无法生成正式对照摘要。")
    else:
        gap_lines = []
        for profile in shadow_profiles:
            for gap in profile.get("comparison_gaps", []):
                parts = []
                if gap.get("missing_shared_metrics"):
                    parts.append("缺共享指标 " + "、".join(f"`{metric}`" for metric in gap["missing_shared_metrics"]))
                if gap.get("missing_profile_specific_metrics"):
                    parts.append(
                        "缺 profile-specific 指标 "
                        + "、".join(f"`{metric}`" for metric in gap["missing_profile_specific_metrics"])
                    )
                gap_lines.append(
                    f"- `{_display_profile_name(profile['profile_id'])}` / `{gap['run_id']}`："
                    + "；".join(parts)
                )
        if gap_lines:
            lines.extend(gap_lines)
        else:
            lines.append("- 当前报告已经具备 issue 回贴条件；如果这些结果不是来自公司 Ubuntu 主机真实 `--execute`，则仍缺正式验收回填。")

    lines.extend(["", "下一步实验："])
    if shadow_comparison and not any(profile.get("comparison_gaps") for profile in shadow_profiles):
        lines.append("- 直接把本文件回贴到 `#18 / #27`，并附上 `summary.json / report.md / report.html` 路径。")
        lines.append("- 如需正式验收，在公司 Ubuntu 主机复用同一 `run_root` 跑 3 条真实 `--execute` 后再次执行 `simctl report`。")
    else:
        lines.append("- 先补齐缺失指标或 shadow 运行结果，再重新执行 `simctl report`。")

    lines.extend(["", "运行回填："])
    tracked_profiles = {"perception_bevfusion_public_road"}
    tracked_profiles.update(profile["profile_id"] for profile in shadow_profiles)
    ordered_profiles = [
        "perception_bevfusion_public_road",
        "e2e_bevfusion_uniad_shadow",
        "e2e_bevfusion_vadv2_shadow",
    ]
    ordered_results = []
    for profile_id in ordered_profiles:
        ordered_results.extend(result for result in summary["runs"] if _result_profile_id(result) == profile_id)
    ordered_results.extend(
        result
        for result in summary["runs"]
        if _result_profile_id(result) not in tracked_profiles and result not in ordered_results
    )
    for result in ordered_results:
        lines.append(
            f"- `{_display_profile_name(_result_profile_id(result))}`: "
            f"run_id=`{result['run_id']}`，scenario=`{result['scenario_id']}`，gate_passed=`{result.get('gate', {}).get('passed')}`"
        )

    lines.extend(["", "Gate Verdicts："])
    if shadow_comparison:
        for profile in shadow_profiles:
            shared_passed = sum(
                verdict["passed_runs"] for verdict in profile.get("shared_metric_verdicts", {}).values()
            )
            shared_failed = sum(
                verdict["failed_runs"] for verdict in profile.get("shared_metric_verdicts", {}).values()
            )
            shared_missing = sum(
                verdict["missing_runs"] for verdict in profile.get("shared_metric_verdicts", {}).values()
            )
            specific_passed = sum(
                verdict["passed_runs"] for verdict in profile.get("profile_specific_metric_verdicts", {}).values()
            )
            specific_failed = sum(
                verdict["failed_runs"] for verdict in profile.get("profile_specific_metric_verdicts", {}).values()
            )
            specific_missing = sum(
                verdict["missing_runs"] for verdict in profile.get("profile_specific_metric_verdicts", {}).values()
            )
            lines.append(
                f"- `{_display_profile_name(profile['profile_id'])}`: "
                f"shared passed=`{shared_passed}` failed=`{shared_failed}` missing=`{shared_missing}`；"
                f"profile-specific passed=`{specific_passed}` failed=`{specific_failed}` missing=`{specific_missing}`"
            )
    else:
        lines.append("- 当前没有可汇总的 shadow gate verdict。")

    lines.append("")
    return "\n".join(lines)


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
            header = "| Profile | Runs | Comparison Ready | Gate Passed | " + " | ".join(f"{metric} avg" for metric in shared_metrics) + " |"
            separator = "| --- | ---: | ---: | ---: | " + " | ".join("---:" for _ in shared_metrics) + " |"
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
                            str(profile["comparison_ready_runs"]),
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
        lines.extend(["", "### Gate Verdicts", ""])
        verdict_rows = []
        for profile in shadow_comparison["profiles"]:
            for metric, verdict in profile.get("shared_metric_verdicts", {}).items():
                verdict_rows.append(
                    f"| `{profile['profile_id']}` | `{metric}` | `{verdict.get('threshold')}` | {verdict['passed_runs']} | {verdict['failed_runs']} | {verdict['missing_runs']} |"
                )
        if verdict_rows:
            lines.extend(
                [
                    "| Profile | Metric | Threshold | Passed | Failed | Missing |",
                    "| --- | --- | --- | ---: | ---: | ---: |",
                    *verdict_rows,
                ]
            )
        else:
            lines.append("- None")
        lines.extend(["", "### Comparison Gaps", ""])
        rendered_gap = False
        for profile in shadow_comparison["profiles"]:
            for gap in profile.get("comparison_gaps", []):
                rendered_gap = True
                missing_shared = gap.get("missing_shared_metrics") or []
                missing_profile_specific = gap.get("missing_profile_specific_metrics") or []
                parts = []
                if missing_shared:
                    parts.append("missing shared: " + ", ".join(f"`{metric}`" for metric in missing_shared))
                if missing_profile_specific:
                    parts.append(
                        "missing profile-specific: "
                        + ", ".join(f"`{metric}`" for metric in missing_profile_specific)
                    )
                lines.append(
                    f"- `{profile['profile_id']}` / `{gap['run_id']}` / `{gap['scenario_id']}`: {'; '.join(parts)}"
                )
        if not rendered_gap:
            lines.append("- None")
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
                    f"<td><code>{profile['comparison_ready_runs']}</code></td>"
                    f"<td><code>{profile['gate_passed_runs']}</code></td>"
                    f"{metric_cells}"
                    "</tr>"
                )
            verdict_rows = []
            for profile in shadow_comparison["profiles"]:
                for metric, verdict in profile.get("shared_metric_verdicts", {}).items():
                    verdict_rows.append(
                        "<tr>"
                        f"<td><code>{profile['profile_id']}</code></td>"
                        f"<td><code>{metric}</code></td>"
                        f"<td><code>{verdict.get('threshold')}</code></td>"
                        f"<td><code>{verdict['passed_runs']}</code></td>"
                        f"<td><code>{verdict['failed_runs']}</code></td>"
                        f"<td><code>{verdict['missing_runs']}</code></td>"
                        "</tr>"
                    )
            gap_items = []
            for profile in shadow_comparison["profiles"]:
                for gap in profile.get("comparison_gaps", []):
                    parts = []
                    if gap.get("missing_shared_metrics"):
                        parts.append(
                            "missing shared: "
                            + ", ".join(gap["missing_shared_metrics"])
                        )
                    if gap.get("missing_profile_specific_metrics"):
                        parts.append(
                            "missing profile-specific: "
                            + ", ".join(gap["missing_profile_specific_metrics"])
                        )
                    gap_items.append(
                        "<li>"
                        f"<code>{profile['profile_id']}</code> / <code>{gap['run_id']}</code> / "
                        f"<code>{gap['scenario_id']}</code>: {'; '.join(parts)}"
                        "</li>"
                    )
            gap_list = "".join(gap_items) or "<li>None</li>"
            shadow_section = (
                "<h2>Shadow Comparison</h2>"
                f"<p>Profiles compared: <code>{shadow_comparison['profile_count']}</code></p>"
                "<table><thead><tr><th>Profile</th><th>Runs</th><th>Comparison Ready</th><th>Gate Passed</th>"
                f"{shadow_header}</tr></thead><tbody>{''.join(shadow_rows)}</tbody></table>"
                "<h3>Gate Verdicts</h3>"
                "<table><thead><tr><th>Profile</th><th>Metric</th><th>Threshold</th><th>Passed</th><th>Failed</th><th>Missing</th></tr></thead>"
                f"<tbody>{''.join(verdict_rows)}</tbody></table>"
                "<h3>Comparison Gaps</h3>"
                f"<ul>{gap_list}</ul>"
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
    issue_update_path = output_dir / "issue_update.md"
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    html_path.write_text(render_html(summary), encoding="utf-8")
    issue_update_path.write_text(render_issue_update(summary), encoding="utf-8")
    dump_json(summary_path, summary)
    return {
        "markdown": str(markdown_path),
        "html": str(html_path),
        "summary": str(summary_path),
        "issue_update": str(issue_update_path),
    }
