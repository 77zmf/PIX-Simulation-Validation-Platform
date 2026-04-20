---
name: runtime-closure-audit
description: Use when a task asks whether the validation loop is truly closed, why a run is stuck at launch or health-check stages, or how to connect run_result, KPI gate, report, replay, and digest into one auditable chain. This skill collects stub-safe evidence and pinpoints the missing closure link.
---

# Runtime closure audit

Use this skill when someone asks "is it really closed loop yet?" or requests a concrete closure plan.

## Goal
Audit the current artifact chain and identify which link is present, missing, or still stub-only.

## Standard procedure
1. On a non-runtime machine, use the stub-safe audit script:

```bash
bash .agents/skills/runtime-closure-audit/scripts/audit_stub_run.sh automation_outputs/runtime_audit
```

2. Read:
   - `automation_outputs/runtime_audit/runtime_audit_summary.json`
   - the latest `run_result.json`
   - `report/summary.json` when present
3. Map the evidence to this chain:

`assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest`

4. State clearly whether the current result is:
   - a real closed loop
   - a launch/report loop
   - a stub-only validation path
   - blocked on external runtime host evidence

## Output requirements
Always answer with:
- present links
- missing links
- exact next code/config/action to close the gap
- what must be run on the Ubuntu runtime host
- rollback or containment advice if the gap is risky

## Boundaries
- Do not claim runtime closure based only on launch success or report file existence.
- Distinguish local stub evidence from real runtime evidence.
