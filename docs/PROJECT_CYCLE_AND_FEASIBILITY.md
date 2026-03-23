# Project Cycle And Feasibility

This document defines the full 12-week delivery cycle for the current quarter and records what is feasible now, what is feasible later, and what depends on external inputs.

## Quarter Goal

By the end of the current 3-month cycle, the team should have:

- one repeatable stable closed-loop path based on `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15`
- one reusable automation path based on `bootstrap / up / run / batch / replay / report`
- one standardized site asset bundle based on `gy_qyhx_gsh20260302`
- one prioritized `Scenario Backlog` with site proxy and corner-case templates
- one prepared `UE5 / E2E` seed path based on `BEV baseline + VAD shadow`

## Week-By-Week Cycle

### Weeks 1-2

- prepare Windows host, WSL2, Ubuntu 22.04, and ROS 2 Humble
- validate the local CARLA 0.9.15 bring-up path
- compile the Autoware workspace
- keep `simctl` as the only repo-level control-plane entry

Primary owner:
- Zhu Minfeng

Exit gate:
- environment steps are repeatable and documented

### Weeks 3-4

- connect `autoware_carla_interface`
- validate clock, TF, and control feedback behavior
- lock the first L0 smoke route and report template
- standardize the first site asset directory

Primary owners:
- Zhu Minfeng
- Luo Shunxiong

Exit gate:
- the team can execute one minimal loop and produce one report artifact set

### Weeks 5-6

- run the first L1 regression batch
- make `run_result.json`, replay, and report the default outputs
- create the first field-data index
- finalize the Top 5 corner-case candidates

Primary owners:
- Zhu Minfeng
- Luo Shunxiong

Exit gate:
- regression can be repeated without ad hoc operator steps

### Weeks 7-8

- stabilize the KPI gate thresholds
- create the first site proxy execution template
- confirm the remote GPU host access path
- map `BEV` outputs to `VAD shadow` interfaces

Primary owners:
- Zhu Minfeng
- Yang Zhipeng

Exit gate:
- the stable line is ready for weekly regression and the next-cycle E2E route is technically framed

### Weeks 9-10

- execute the first site proxy scenario
- validate at least one P0 corner case
- produce the first scenario-backed report package
- define the first E2E shadow metric set

Primary owners:
- Luo Shunxiong
- Yang Zhipeng

Exit gate:
- at least one site proxy scenario is part of the normal validation flow

### Weeks 11-12

- freeze the quarter acceptance set
- review all blocked P0/P1 items
- publish the quarter summary
- prepare the next-cycle handoff for UE5 and E2E work

Primary owners:
- Zhu Minfeng
- Luo Shunxiong
- Yang Zhipeng

Exit gate:
- the quarter closes with a repeatable baseline, not a one-time demo

## Feasibility Matrix

### Feasible Now

- GitHub task board and scenario board as public execution mirrors
- repo-side control plane, documentation, and automated digest generation
- Notion-driven planning with GitHub public synchronization
- stable-line planning and KPI-gate structure

### Feasible In This Quarter

- WSL2 + Windows host split for stable validation
- one repeatable CARLA 0.9.15 smoke loop
- first L1 regression batch
- first site asset bundle and first site proxy scenario
- first `BEV + VAD shadow` comparison path

### Feasible Next Quarter After The Current Gate

- larger-scale site proxy coverage
- more than one field-backed corner-case library
- UE5 remote data generation at higher fidelity
- deeper `VAD shadow` integration and controlled closed-loop trial

### Blocked By External Inputs

- real email delivery without SMTP credentials or mail API credentials
- real remote execution without remote GPU host access and runner setup
- true UE5 production validation on the current local machine
- direct end-to-end control takeover in the current quarter

## Validation Plan

The quarter is considered valid only if the following checks hold:

- environment setup is reproducible on a clean machine
- at least one closed-loop run is repeatable
- `bootstrap / up / run / batch / replay / report` works as one workflow
- the first site bundle is normalized and used by at least one scenario
- the scenario backlog is tracked in both Notion and GitHub
- the automation digest runs and produces owner-specific reminders

## Decision Rule

If a feature does not improve one of the following within the current cycle, it is not on the main line:

- stable closed-loop repeatability
- regression automation
- site proxy scenario reuse
- E2E shadow readiness for the next cycle
