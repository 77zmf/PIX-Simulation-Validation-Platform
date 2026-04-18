# PIX Simulation Validation Platform

Display name: `PIX Simulation Validation Platform`  
Current GitHub URL: `77zmf/PIX-Simulation-Validation-Platform`

This repository is the control plane for a simulation validation platform built around:

- `Autoware Universe main`
- `ROS 2 Humble`
- `CARLA 0.9.15`
- `UE4.26`

The current delivery is not a generic environment-setup effort. It is a reusable validation baseline for:

- stable closed-loop verification on the company Ubuntu host
- automated `bootstrap / up / run / batch / replay / report` workflows
- public-road asset reuse, `site proxy`, and corner-case accumulation
- BEV / VAD / UniAD-style / E2E shadow research on the same CARLA 0.9.15 runtime baseline

## Current Focus

The active quarter is organized around four priorities:

1. Make the `stable` stack usable in closed loop on the company Ubuntu host.
2. Make `simctl` usable for daily validation and reporting.
3. Turn `gy_qyhx_gsh20260302` into reusable public-road map and scenario inputs.
4. Keep E2E shadow research on `CARLA 0.9.15 / UE4.26` without destabilizing the main line.

Near-term gate:

- by `2026-04-05`, finish Ubuntu host bring-up and close the first automation data loop:
  `simctl run -> run_result.json -> report -> replay`

## Public Entry Points

- GitHub URL: [77zmf/PIX-Simulation-Validation-Platform](https://github.com/77zmf/PIX-Simulation-Validation-Platform)
- GitHub Task Board: [Project 1](https://github.com/users/77zmf/projects/1)
- GitHub Scenario Board: [Project 2](https://github.com/users/77zmf/projects/2)
- GitHub Digest Inbox: [project-digest issues](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues?q=is%3Aissue+is%3Aopen+label%3Aproject-digest)

## Team Ownership

- `Zhu Minfeng`: stable stack, Ubuntu host, control plane, automation, KPI gates
- `Luo Shunxiong / lsx`: public-road map and pointcloud assets, reconstruction inputs, corner-case replay
- `Yang Zhipeng / 杨志朋`: `BEVFusion` perception baseline, public-road perception, and E2E shadow research
- `Codex PMO support`: digest generation, weekly review preparation, blocker aggregation, and repo-side management support

## Technical Tracks

### Stable Main Line

- the company `Ubuntu 22.04` host is the primary runtime environment
- the same host runs `ROS 2 Humble`, `Autoware Universe`, `autoware_carla_interface`, and `CARLA 0.9.15`
- the local machine is only for code management, remote access, and artifact review
- primary success signal is a repeatable closed loop:
  `startup -> localization -> planning -> control -> goal reached -> report`

### Public-Road Assets And Corner Cases

- current complete public-road bundle: `site_gy_qyhx_gsh20260310`
- legacy public-road bundle manifest: `site_gy_qyhx_gsh20260302`
- target asset bundle shape:
  - `lanelet2_map.osm`
  - `map_projector_info.yaml`
  - `pointcloud_map.pcd/`
  - `pointcloud_map_metadata.yaml`
- large raw assets stay out of Git history and are referenced by manifests
- reconstruction direction is staged:
  - `map refresh` for asset and localization support
  - `static Gaussian` reconstruction for future geometry-rich replay assets
  - `dynamic Gaussian` reconstruction for future actor-aware replay and high-fidelity simulation

### Future E2E Route

The current recommended route is:

- keep `BEVFusion` as the production perception baseline
- run a `UniAD-style` planner in `shadow` mode first
- keep `VADv2` as the comparison baseline for uncertainty-aware planning
- compare trajectory, behavior, collision, TTC, rule-compliance, and route-completion signals
- preserve fallback to the classical planning and control chain

This repository does not treat direct end-to-end control takeover as the first milestone.

## Repository Layout

```text
infra/       Ubuntu host preparation and operator runbooks
stack/       Stable stack profile, slot catalog, and launch helpers
assets/      Sensor catalogs, manifests, and lightweight metadata
scenarios/   L0-L3 plus E2E research scenarios on the stable stack
evaluation/  KPI gates, reports, and validation summaries
adapters/    Planning-control, perception, reconstruction, and E2E shadow profiles
docs/        Public overview, runbooks, delivery plan, and review notes
references/  Curated local paper PDFs and reading materials
src/         simctl CLI and supporting library code
tests/       Control-plane, digest, and scenario regression tests
ops/         Project automation configuration
tools/       Maintenance and publishing helpers
```

## Runtime Assumptions

- The main runtime host is the company `Ubuntu 22.04` machine.
- `CARLA 0.9.15` is the only official simulator runtime in this repository.
- no secondary simulator runtime is part of the current repository strategy or execution path.
- E2E shadow research stays on the `stable` stack and reuses the same CARLA 0.9.15 baseline.

## Main Commands

Render or execute the stable bring-up plan:

```bash
simctl bootstrap --stack stable
simctl up --stack stable --scenario scenarios/l0/smoke_stub.yaml
```

Run one scenario and generate a result:

```bash
simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root runs
simctl run --scenario scenarios/l1/regression_follow_lane.yaml --run-root runs --slot stable-slot-01
```

Batch runs and reporting:

```bash
simctl batch --glob "scenarios/l1/*.yaml" --run-root runs
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed
simctl report --run-root runs
```

Asset validation:

```bash
simctl asset-check --bundle site_gy_qyhx_gsh20260302
simctl asset-check --bundle site_gy_qyhx_gsh20260310
python tools/validate_reconstruction_assets.py --bundle site_gy_qyhx_gsh20260310
```

Stable slot catalog:

```text
stack/slots/stable_slots.yaml
```

Use `--parallel 2` as the default operating mode. The repository now defines 4 slots, but 4-way execution should only be enabled after host-level pressure testing.

Digest and replay:

```bash
simctl digest
simctl replay --run-result runs/<run_id>/run_result.json
```

## Ubuntu Host Workflow

Operator-facing helpers:

```bash
bash infra/ubuntu/bootstrap_host.sh
bash infra/ubuntu/bootstrap_remote_access_tailscale.sh
bash infra/ubuntu/check_host_readiness.sh
bash infra/ubuntu/preflight_and_next_steps.sh
bash infra/ubuntu/prepare_carla_runtime.sh
bash infra/ubuntu/prepare_autoware_workspace.sh
```

Reference documents:

- [Ubuntu Host Bring-up](./docs/UBUNTU_HOST_BRINGUP_CN.md)
- [Windows Local Setup](./docs/WINDOWS_LOCAL_SETUP_CN.md)
- [Tomorrow Company Host Checklist](./docs/TOMORROW_COMPANY_HOST_CHECKLIST_CN.md)
- [Mac Codex Workflow](./docs/MAC_CODEX_WORKFLOW_CN.md)
- [Team Skill Usage](./docs/TEAM_SKILL_USAGE_CN.md)
- [Server Compile Baseline](./docs/SERVER_COMPILE_BASELINE_CN.md)
- [Algorithm Research Roadmap](./docs/ALGORITHM_RESEARCH_ROADMAP_CN.md)
- [Project Review](./docs/PROJECT_REVIEW_AND_OPTIMIZATION_CN.md)
- [Weekly Repo Sync 2026-04-18](./docs/WEEKLY_REPO_SYNC_2026_04_18_CN.md)
- [Local Reconstruction Validation](./docs/LOCAL_RECONSTRUCTION_VALIDATION_CN.md)

## Subagent Catalog

Render reusable Codex subagent definitions stored in the repo:

```bash
simctl subagent-spec --list
simctl subagent-spec --name execution_runtime_explorer
simctl subagent-spec --name execution_runtime_explorer --format spawn_json
```

Subagent catalog:

- [Subagent Catalog](./docs/SUBAGENT_CATALOG.md)
- repo-side skill pack:
  - `ops/skills/`
  - [Team Skill Usage](./docs/TEAM_SKILL_USAGE_CN.md)
- recommended fixed roles:
  - `execution_runtime_explorer`
  - `algorithm_research_explorer`
  - `project_automation_explorer`
  - `gaussian_reconstruction_explorer`
  - `public_road_e2e_shadow_explorer`
  - `stable_stack_host_readiness_explorer`

## Current Planning Documents

The repo-side planning documents live in:

- `docs/TEAM_90_DAY_PLAN.md`
- `docs/AI_SUPERBODY_PERCEPTION_SUPPLEMENT_CN.md`
- `docs/TEAM_OPERATING_RHYTHM.md`
- `docs/PROJECT_OPERATING_TEAM_CN.md`
- `docs/QUARTER_ACCEPTANCE.md`
- `docs/PLANNING_SYNC_SNAPSHOT_CN.md`
- `docs/PROJECT_MANAGEMENT_OVERVIEW_CN.md`
- `docs/PROJECT_CYCLE_AND_FEASIBILITY.md`
- `docs/UBUNTU_HOST_BRINGUP_CN.md`
- `docs/SERVER_COMPILE_BASELINE_CN.md`
- `docs/ALGORITHM_RESEARCH_ROADMAP_CN.md`
- `docs/PROJECT_AUTOMATION.md`
- `docs/PROJECT_REVIEW_AND_OPTIMIZATION_CN.md`
- `docs/GIT_COLLABORATION_STANDARD_CN.md`
- `docs/FUTURE_EXECUTION_ROADMAP_CN.md`
- `docs/TEAM_AGENT_USAGE_CN.md`
- `docs/TEAM_SKILL_USAGE_CN.md`
- `docs/MAC_CODEX_WORKFLOW_CN.md`
- `docs/PAPER_READING_MAP_CN.md`
- `docs/PAPER_LANDSCAPE_CN.md`
- `docs/LOCAL_PDF_INDEX_CN.md`
- `ops/issues/README.md`

## Git Collaboration

This repository includes a repo-side Git collaboration guide and commit template so the same rules can be reused across different machines.

- collaboration guide: `docs/GIT_COLLABORATION_STANDARD_CN.md`
- commit template: `ops/git/commit-message-template.txt`
- for Codex-created branches, use `codex/<tag>/<short-kebab-case>`
- current repo default branch is `main`, so branch from `main` unless the repo policy changes later

## Validation Rules

- Stable closed-loop delivery remains the quarter gate.
- `site proxy` and corner cases must accumulate as reusable assets, not one-off scripts.
- E2E shadow remains a research path under `CARLA 0.9.15 / UE4.26`.
- Digest automation now uses GitHub Projects and GitHub issues only.

## Current Gaps

The project-management and control-plane layers are in place, but three delivery gates still matter most:

- the real `Autoware + CARLA` runtime path still needs to be brought up on the company Ubuntu host
- the first reusable public-road scenario still needs to move from asset structure into repeatable validation input
- GitHub Project hygiene and digest quality still depend on board field discipline and assignee maintenance

## Current Asset Note

The archives `gy_qyhx_gsh20260302_map.zip` and `gy_qyhx_gsh20260310_map(2).zip` remain outside Git tracking because of GitHub file-size constraints. The repository tracks manifests and normalized paths instead of the raw archives themselves.
