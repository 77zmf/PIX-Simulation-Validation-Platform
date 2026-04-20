---
name: pix-run-result-triage
description: Use when reviewing PIX simctl run artifacts, batch results, run_result.json, KPI gate outputs, report/replay summaries, health.json, launch_submitted or launch_failed states, or any request that needs a concise verdict, evidence anchors, owner, and next action for a validation run.
---

# PIX run result triage

Use this skill to turn raw validation artifacts into an engineering decision. It complements `runtime-closure-audit`: this skill explains one run or batch; `runtime-closure-audit` decides whether the whole validation chain is closed.

## Procedure

1. Locate the relevant artifacts before judging:
   - `runs/**/run_result.json`
   - `runs/**/health.json`
   - `runs/**/start_plan.json`
   - `runs/**/report.md`, `report.html`, or `summary.json`
   - KPI gate outputs under `evaluation/kpi_gates/` or generated report folders
   - `automation_outputs/runtime_audit/` when reviewing stub-safe automation output
2. Classify the run path:
   - `stub` or mock result
   - dry-run control-plane check
   - real company Ubuntu 22.04 runtime-host execution
   - incomplete launch/report path
3. Classify status conservatively:
   - Treat `passed` or `failed` as final only when KPI evidence is present.
   - Treat `launch_submitted` as incomplete, not as success.
   - Treat `launch_failed` as a bring-up or health-check failure until runtime evidence says otherwise.
   - Treat missing KPI gates as a validation gap even when reports exist.
4. Tie the evidence back to the chain:

```text
assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest
```

5. Produce the smallest useful owner action. Prefer exact file paths, command lines, scenario names, KPI names, and missing artifacts.

## Output

Use this structure unless the user asks for something else:

1. Run identity
2. Scenario and profile
3. Verdict
4. Evidence
5. KPI status
6. Missing links
7. Owner and next action

## Rules

- Separate observed facts from hypotheses.
- Keep stable-line results separate from shadow or research-line results.
- Do not infer real runtime-host success from CI stub results.
- If the next step needs the Ubuntu host, say that explicitly.
- Prefer extending `simctl` outputs or reports over proposing one-off parsers.
