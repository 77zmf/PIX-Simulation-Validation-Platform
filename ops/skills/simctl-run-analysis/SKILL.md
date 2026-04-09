---
name: simctl-run-analysis
description: Use this skill when a simctl run, batch result, run_result.json, KPI gate result, report, or replay summary needs to be interpreted into a concise engineering review.
---

# Purpose
Convert raw run outputs into a concise result review that supports regression decisions, replay debugging, and digest generation.

# Use this skill when
- reviewing `run_result.json`
- summarizing L0 smoke or L1 regression results
- interpreting KPI gate failures
- preparing replay or log-slice guidance
- generating a short engineering digest after batch execution

# Required output structure
1. Run identity
2. Scenario / profile summary
3. Result verdict
4. KPI summary
5. Failure taxonomy guess
6. Evidence anchors needed for replay / logs
7. Recommended owner and next action

# Rules
- Separate observed result from hypothesis.
- If a KPI gate is missing, say so explicitly.
- If a run is incomplete, mark the result as partial rather than pass/fail.
- Prefer brief engineering summaries that can be pasted into Notion or GitHub.
- If multiple runs are compared, group by scenario, profile, or failure type.

# Companion references
See `references/run_result_review_template.md`, `references/kpi_gate_template.yaml`, and `references/digest_template.md`.
