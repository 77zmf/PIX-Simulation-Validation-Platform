# Team 90-Day Plan

This document captures the team-aligned 90-day delivery plan for the Autoware + CARLA validation platform. It is the repo-side counterpart to the team Notion project pages and should stay consistent with the current quarter plan.

## Objective

Over the next 3 months, the team will move the project from a scaffolded validation platform to a repeatable delivery baseline with:

- a stable `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` closed-loop path
- automated validation and reporting workflows
- a first usable `site proxy` asset bundle and scenario input path
- a prepared `UE5 / E2E shadow` experiment line for the next cycle

## Priority Order

1. Stable stack closed loop is usable.
2. Automation and regression are usable.
3. Site assets and corner-case inputs are standardized.
4. UE5 / E2E shadow is prepared as the next-cycle seed.

## Team Ownership

### Zhu Minfeng

- Owns the stable stack, control-plane implementation, KPI flow, and weekly project steering.
- Must personally drive the closed-loop path, CLI workflow, and milestone acceptance.

### Luo Shunxiong (`lsx`)

- Owns site-proxy inputs, pointcloud/map asset handling, corner-case discovery, and field-problem reconstruction inputs.
- Converts field issues into reusable simulation assets and scenario templates.

### Yang Zhipeng (`Zhipeng Yang`)

- Owns the UE5 remote line, remote GPU readiness, and perception / E2E shadow preparation.
- Prepares the next-cycle high-fidelity validation path without destabilizing the current stable line.

## Phase Plan

## Phase 1: Foundation And Minimal Loop

Time window: Weeks 1-4

Goals:

- Prepare Windows host, WSL2, Ubuntu 22.04, ROS 2 Humble, and Autoware workspace basics.
- Start CARLA 0.9.15 and validate baseline Town01 behavior.
- Keep the `simctl` control plane as the single entry point for bootstrap, startup, run, replay, and report.

Required outputs:

- host and WSL preparation notes
- baseline CARLA bring-up
- Autoware workspace readiness
- control-plane scripts committed and smoke-tested

Exit criteria:

- the environment can be prepared repeatably
- CARLA 0.9.15 runs on the Windows host
- the team can execute the minimal validation workflow from the repo

## Phase 2: Closed Loop And Automation

Time window: Weeks 5-8

Goals:

- Connect `autoware_carla_interface`
- establish a minimal closed-loop path
- lock L0 smoke and L1 regression behavior
- produce `run_result.json`, replay paths, and reports from the same workflow

Required outputs:

- stable L0 smoke scenario
- first L1 regression batch
- KPI gate definitions in use
- replay and reporting workflow

Exit criteria:

- at least one stable closed-loop route succeeds
- reports and replay entries are generated consistently
- the team can repeat smoke and regression scenarios without ad hoc manual steps

## Phase 3: Site Proxy And Corner Cases

Time window: Weeks 9-12

Goals:

- standardize the `gy_qyhx_gsh20260302` asset bundle
- organize lanelet, projector, pointcloud, and field-case inputs
- define and prioritize the Top 5 corner cases
- build the first site-proxy scenario path

Required outputs:

- standardized asset bundle layout
- top-five corner-case list with success signals
- first site-proxy scenario templates
- scenario backlog aligned with real field problems

Exit criteria:

- at least one site-proxy scenario is executable through the team workflow
- corner cases are documented as reusable templates instead of one-off scripts

## Parallel Seed: UE5 / E2E Shadow Preparation

Time window: Runs in parallel, but does not displace the stable line

Goals:

- identify the remote GPU host and access model
- define shadow metrics for perception / E2E experiments
- prepare a remote execution path for the next cycle

Required outputs:

- remote host readiness checklist
- UE5 remote execution notes
- E2E shadow metric draft

Exit criteria:

- the next quarter can start UE5 / E2E experiments without re-deciding the host, access, and evaluation model

## Weekly Operating Rhythm

- Hold one `Weekly Review` every week.
- Review only three operational questions:
  - did any `P0` task slip
  - is any risk missing an action owner
  - did the week produce new artifacts, reports, or scenario assets
- Keep Notion as the source of truth for task status and owner assignment.
- Keep the repo as the source of truth for scripts, scenario definitions, KPI gates, and implementation notes.

## Acceptance Criteria For The Quarter

- Stable stack:
  at least one closed-loop validation path works repeatably.
- Automation:
  `bootstrap`, `up`, `run`, `batch`, `replay`, and `report` are all usable.
- Assets:
  the first site-proxy asset bundle is standardized and linked to scenario inputs.
- Team process:
  weekly review, ownership, and progress tracking run through the established Notion workflow.
- Future path:
  UE5 remote readiness and E2E shadow metrics are documented for the next cycle.
