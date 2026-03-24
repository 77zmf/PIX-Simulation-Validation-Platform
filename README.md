# Autoware + CARLA Simulation Validation Platform

This repository is the control plane for an autonomous-driving simulation validation platform.

It is not just an environment setup repo. The current goal is to build a team-usable validation baseline for:

- `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` stable closed-loop verification
- automated regression, replay, KPI gating, and reporting
- public-road map, reconstruction, and corner-case accumulation from real assets
- a future `UE5 / E2E` experiment line that starts with `BEVFusion + UniAD-style shadow`, with `VADv2` as the comparison baseline

## Current Focus

The current three-month delivery is organized around four priorities:

1. Make the `stable` stack usable in closed loop.
2. Make `bootstrap / up / run / batch / replay / report` usable for daily validation.
3. Turn the `gy_qyhx_gsh20260302` assets into reusable public-road map and corner-case inputs.
4. Prepare public-road `UE5 / E2E shadow` as the next-stage capability without destabilizing the main line.

## Public Entry Points

- Repository: [77zmf/zmf_ws](https://github.com/77zmf/zmf_ws)
- GitHub Project: [Task Board](https://github.com/users/77zmf/projects/1)
- GitHub Scenario Project: [Scenario Board](https://github.com/users/77zmf/projects/2)
- GitHub Digest Inbox: [project-digest issues](https://github.com/77zmf/zmf_ws/issues?q=is%3Aissue+is%3Aopen+label%3Aproject-digest)
- GitHub Pages: [77zmf.github.io/zmf_ws](https://77zmf.github.io/zmf_ws/)
- Notion project book: [Project Book](https://www.notion.so/32cef7e6aaa98064a3a4ef0d00935f8f)
- Notion execution board: [Program Board](https://www.notion.so/dc730999bb7140338b871dd33dfbfeec)
- Notion two-week view: [Next 2 Weeks](https://www.notion.so/dc730999bb7140338b871dd33dfbfeec?v=32cef7e6aaa9819b9826000c4b519313)
- Notion scenario backlog: [Scenario Backlog](https://www.notion.so/2fb616fb48d5429cbb01a7b6299b84e9)

## Team Ownership

- `Zhu Minfeng`: stable stack, control plane, automation, project rhythm
- `Luo Shunxiong / lsx`: public-road map and pointcloud assets, reconstruction inputs, corner-case replay
- `Yang Zhipeng / Zhipeng Yang`: `BEVFusion` perception baseline, public-road perception / E2E shadow preparation

## Technical Tracks

### Stable Main Line

- Windows host runs CARLA rendering and host-side orchestration
- WSL2 Ubuntu 22.04 runs Autoware Universe, ROS 2 Humble, and bridge components
- CARLA version is fixed to `0.9.15`
- Primary success signal is a repeatable closed loop:
  `startup -> localization -> planning -> control -> goal reached -> report`

### Public-Road Assets and Corner Cases

- First public-road bundle: `site_gy_qyhx_gsh20260302`
- Target asset bundle shape:
  - `lanelet2_map.osm`
  - `map_projector_info.yaml`
  - `pointcloud_map.pcd/`
  - `metadata.yaml`
- Large raw assets stay out of Git history and are referenced by manifests
- Reconstruction direction is staged:
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
infra/       Host, WSL2, Ubuntu, and remote preparation scripts
stack/       Stable and UE5 stack profiles plus launch helpers
assets/      Asset manifests, site metadata, and sensor profiles
scenarios/   L0-L3 and UE5 scenario definitions
evaluation/  KPI gates, reports, and failure taxonomy
adapters/    Planning, perception, and E2E profile examples
src/simctl/  CLI and control-plane implementation
tests/       Local verification for the control plane
docs/        Public portal, team plan, and project-management snapshots
```

## Control Plane Commands

The unified CLI entrypoints are:

- `bootstrap`
- `up`
- `down`
- `run`
- `batch`
- `replay`
- `report`
- `digest`
- `notion-check`

## Quick Start

1. Create a virtual environment and install the package.

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -e .
   ```

2. Inspect the stable bootstrap plan.

   ```powershell
   simctl bootstrap --stack stable
   ```

3. Run a local smoke scenario and generate a report.

   ```powershell
   simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root runs
   simctl report --run-root runs
   ```

4. Batch a set of scenarios.

   ```powershell
   simctl batch --glob "scenarios/l1/*.yaml" --run-root runs --mock-result passed
   simctl report --run-root runs
   ```

5. Generate the project digest used by the management automation.

   ```powershell
   simctl digest --config ops/project_automation.yaml --output-dir artifacts/project_digest
   ```

6. Validate the Notion API connection used by the automation.

   ```powershell
   simctl notion-check --config ops/project_automation.yaml
   ```

## Current Planning Documents

The repo-side planning documents live in:

- `docs/TEAM_90_DAY_PLAN.md`
- `docs/TEAM_OPERATING_RHYTHM.md`
- `docs/QUARTER_ACCEPTANCE.md`
- `docs/PROJECT_MANAGEMENT_OVERVIEW_CN.md`
- `docs/PROJECT_CYCLE_AND_FEASIBILITY.md`
- `docs/ALGORITHM_RESEARCH_ROADMAP_CN.md`
- `docs/PROJECT_AUTOMATION.md`
- `docs/PROJECT_REVIEW_AND_OPTIMIZATION_CN.md`

The public portal entry is:

- `docs/index.html`

## Current Gaps

The project-management and control-plane layers are in place, but three delivery gates still matter most:

- the real `Autoware + CARLA` runtime path still needs to be brought up on the target machine
- the first reusable public-road scenario still needs to move from asset structure into repeatable validation input
- digest automation works now, but real mail delivery still depends on SMTP secrets and remote UE5 work still depends on a GPU host

## Current Asset Note

The archive `gy_qyhx_gsh20260302_map.zip` remains outside Git tracking because of GitHub file-size constraints. The repository tracks manifests and normalized paths instead of the raw archive itself.
