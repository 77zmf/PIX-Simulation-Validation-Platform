# Team Operating Rhythm

This document defines how the team should run the current 90-day cycle.

## Weekly Review

Cadence: once per week

Participants:

- Zhu Minfeng
- Luo Shunxiong (`lsx`)
- Yang Zhipeng (`Zhipeng Yang`)

Agenda:

1. Last week delivered artifacts
2. Current-week P0 progress
3. Risks and blockers
4. Cross-team support needed
5. Next-week actions

## Review Inputs

- `Program Board` in Notion
- `Scenario Backlog` in Notion
- latest `run_result.json`
- latest generated reports
- newly added public-road scenario definitions, map assets, or reconstruction manifests

## Minimum Weekly Outputs

- one updated weekly-review note
- updated owner and status for P0/P1 items
- explicit blocker actions for any active risk
- explicit next-week actions for each team member

## Owner Matrix

### Zhu Minfeng

- Stable stack environment
- Control-plane scripts
- KPI gates and reporting
- Weekly steering

### Luo Shunxiong (`lsx`)

- Public-road map and pointcloud preparation
- Reconstruction and localization-support assets
- Public-road and corner-case scenario inputs

### Yang Zhipeng (`Zhipeng Yang`)

- `BEVFusion` perception baseline
- Public-road perception / E2E shadow preparation
- UE5 remote host preparation

## Escalation Rules

- If a P0 task slips by more than one weekly review, escalate in the same review.
- If a risk is marked blocked without a next action, the review is incomplete.
- If a new field issue appears, it must land in the scenario backlog before the next review.
