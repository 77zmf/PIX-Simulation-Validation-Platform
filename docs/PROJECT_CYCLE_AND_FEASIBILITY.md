# Project Cycle And Feasibility

This document defines the full 12-week delivery cycle for the current quarter and records what is feasible now, what is feasible later, and what depends on external inputs.

## Quarter Goal

By the end of the current 3-month cycle, the team should have:

- one repeatable stable closed-loop path based on `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15`
- one reusable automation path based on `bootstrap / up / run / batch / replay / report`
- one standardized public-road asset bundle based on `gy_qyhx_gsh20260302`
- one prioritized public-road `Scenario Backlog` with replayable corner-case templates
- one prepared public-road `UE5 / E2E` seed path based on `BEVFusion baseline + UniAD-style shadow`, with `VADv2` as comparison baseline

## Week-By-Week Cycle

### Weeks 1-2

- prepare the company Ubuntu host, access path, development permissions, and `ROS 2 Humble`
- validate the company-host `CARLA 0.9.15` bring-up path
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
- standardize the first public-road asset directory

Primary owners:
- Zhu Minfeng
- Luo Shunxiong

Exit gate:
- the team can execute one minimal loop and produce one report artifact set

### Weeks 5-6

- run the first L1 regression batch
- make `run_result.json`, replay, and report the default outputs
- create the first field-data index
- finalize the Top 5 public-road corner-case candidates

Primary owners:
- Zhu Minfeng
- Luo Shunxiong

Exit gate:
- regression can be repeated without ad hoc operator steps

### Weeks 7-8

- stabilize the KPI gate thresholds
- create the first public-road execution template
- confirm the remote GPU host access path
- map `BEVFusion` outputs to `UniAD-style` and `VADv2` shadow interfaces

Primary owners:
- Zhu Minfeng
- Yang Zhipeng

Exit gate:
- the stable line is ready for weekly regression and the next-cycle E2E route is technically framed

### Weeks 9-10

- execute the first public-road replay scenario
- validate at least one P0 corner case
- produce the first scenario-backed report package
- define the first public-road E2E shadow metric set

Primary owners:
- Luo Shunxiong
- Yang Zhipeng

Exit gate:
- at least one public-road scenario is part of the normal validation flow

### Weeks 11-12

- freeze the quarter acceptance set
- review all blocked P0/P1 items
- publish the quarter summary
- prepare the next-cycle handoff for public-road `UE5 / E2E` work

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

- company Ubuntu host as the stable runtime environment
- one repeatable CARLA 0.9.15 smoke loop
- first L1 regression batch
- first public-road asset bundle and first replayable public-road scenario
- first `BEVFusion + UniAD-style shadow` comparison path

### Feasible Next Quarter After The Current Gate

- broader public-road coverage
- more than one field-backed corner-case library
- UE5 remote data generation at higher fidelity
- deeper `VADv2` or `Hydra-NeXt` integration and controlled closed-loop trial

### Blocked By External Inputs

- real email delivery without SMTP credentials or mail API credentials
- real remote execution without remote GPU host access and runner setup
- true UE5 production validation without a dedicated GPU host
- direct end-to-end control takeover in the current quarter

## Validation Plan

The quarter is considered valid only if the following checks hold:

- environment setup is reproducible on a clean Ubuntu host
- at least one closed-loop run is repeatable
- `bootstrap / up / run / batch / replay / report` works as one workflow
- the first public-road asset bundle is normalized and used by at least one scenario
- the scenario backlog is tracked in both Notion and GitHub
- the automation digest runs and produces owner-specific reminders

## Decision Rule

If a feature does not improve one of the following within the current cycle, it is not on the main line:

- stable closed-loop repeatability
- regression automation
- public-road scenario reuse
- E2E shadow readiness for the next cycle
