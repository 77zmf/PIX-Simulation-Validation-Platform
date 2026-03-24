# Team 90-Day Plan

This document captures the team-aligned 90-day delivery plan for the Autoware + CARLA validation platform. It is the repo-side counterpart to the team Notion project pages and should stay consistent with the current quarter plan.

## Objective

Over the next 3 months, the team will move the project from a scaffolded validation platform to a repeatable delivery baseline with:

- a stable `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` closed-loop path
- automated validation and reporting workflows
- a first usable public-road map and reconstruction asset path based on `gy_qyhx_gsh20260302`
- a prepared public-road `UE5 / E2E shadow` experiment line based on `BEVFusion`

## Priority Order

1. Stable stack closed loop is usable.
2. Automation and regression are usable.
3. Public-road map assets and corner-case inputs are standardized.
4. Public-road `UE5 / E2E shadow` is prepared as the next-cycle seed.

## Team Ownership

### Zhu Minfeng

- Owns the stable stack, control-plane implementation, KPI flow, and weekly project steering.
- Must personally drive the closed-loop path, CLI workflow, and milestone acceptance.

### Luo Shunxiong (`lsx`)

- Owns public-road map and pointcloud assets, reconstruction inputs, corner-case discovery, and field-problem replay preparation.
- Converts field issues into reusable simulation assets and scenario templates.

### Yang Zhipeng (`Zhipeng Yang`, 杨志朋)

- Owns the `BEVFusion` perception baseline, public-road perception and E2E shadow preparation, and UE5 remote readiness.
- Prepares the next-cycle high-fidelity validation path without destabilizing the current stable line.

### Codex PMO Support

- Owns digest generation, weekly review preparation, blocker aggregation, and repo-side management support.
- Helps the team keep execution synchronized, but does not replace human owners for technical decisions and delivery.

## Phase Plan

## Phase 1: Foundation And Minimal Loop

Time window: Weeks 1-4

Goals:

- Prepare the company Ubuntu host, `ROS 2 Humble`, and Autoware workspace basics.
- Start CARLA 0.9.15 and validate baseline Town01 behavior on the company host.
- Keep the `simctl` control plane as the single entry point for bootstrap, startup, run, replay, and report.

Required outputs:

- Ubuntu host preparation notes
- baseline CARLA bring-up
- Autoware workspace readiness
- control-plane scripts committed and smoke-tested

Exit criteria:

- the environment can be prepared repeatably
- CARLA 0.9.15 runs on the company Ubuntu host
- the team can execute the minimal validation workflow from the repo

## Phase 2: Closed Loop And Automation

Time window: Weeks 5-8

Goals:

- connect `autoware_carla_interface`
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

## Phase 3: Public-Road Assets And Corner Cases

Time window: Weeks 9-12

Goals:

- standardize the `gy_qyhx_gsh20260302` asset bundle as a public-road map and reconstruction bundle
- organize lanelet, projector, pointcloud, and field-case inputs
- define and prioritize the Top 5 public-road corner cases
- build the first public-road replayable scenario path

Required outputs:

- standardized asset bundle layout
- top-five public-road corner-case list with success signals
- first public-road scenario templates
- scenario backlog aligned with real field problems

Exit criteria:

- at least one public-road scenario is executable through the team workflow
- corner cases are documented as reusable templates instead of one-off scripts

## Parallel Seed: Public-Road E2E Shadow Preparation

Time window: Runs in parallel, but does not displace the stable line

Goals:

- identify the remote GPU host and access model
- define shadow metrics for `BEVFusion + UniAD-style` and `VADv2` experiments
- prepare a remote execution path for the next cycle

Required outputs:

- remote host readiness checklist
- UE5 remote execution notes
- public-road E2E shadow metric draft

Exit criteria:

- the next quarter can start public-road `UE5 / E2E` experiments without re-deciding the host, access, and evaluation model

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
  the first public-road asset bundle is standardized and linked to scenario inputs.
- Team process:
  weekly review, ownership, and progress tracking run through the established Notion workflow.
- Future path:
  public-road E2E shadow metrics and remote readiness are documented for the next cycle.
