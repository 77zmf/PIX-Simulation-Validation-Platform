# Team Operating Rhythm

Detailed AI Superbody daily workflow: `docs/AI_SUPERBODY_WORKFLOW_OPTIMIZATION_CN.md`.

## North Star

The weekly operating goal is to move one validation chain toward a final `passed / failed / blocked` verdict:

```text
assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest
```

`launch_submitted` is an intermediate state. It is not a weekly delivery result.

## Daily

- Check GitHub Task Board
- Check Scenario Board
- Review digest summary
- Update blocker status if anything slipped
- Pick one P0 main task and at most two support tasks
- Record today's expected artifact before starting work

Daily command baseline:

```bash
git status --short --branch
python -m unittest discover -s tests -v
simctl digest
```

## Weekly

- One weekly review meeting
- Confirm completed work, current blockers, next-week actions
- Validate whether the quarter gate is still on track
- Monday: freeze the single weekly gate and required artifacts
- Wednesday: clean blockers by owner, reason, and date
- Friday: review evidence, not only activity updates

## Required Signals

- Every owner must have a visible next action
- Every blocker must have an owner and a date
- Every research result must point to a scenario and KPI
- Every stable-line status must distinguish repo-local validation from Ubuntu-host acceptance
- Every completed item must reference a command, artifact, issue, or PR

## Current Rule

- Stable delivery remains the quarter gate
- E2E shadow remains a research track on top of `CARLA 0.9.15 / UE4.26`

## Blocker Labels

Use a small blocker vocabulary so digest output stays actionable:

- `needs_host`
- `needs_assets`
- `needs_runtime_evidence`
- `needs_kpi_gate`
- `needs_report_replay`
- `needs_decision`

## Owner Update Format

Use this format in daily updates, digest comments, and weekly review prep:

```text
Owner:
Track: stable mainline / asset-scenario / shadow comparison / reconstruction / PMO
Today artifact:
Blocker:
Next action + date:
```
