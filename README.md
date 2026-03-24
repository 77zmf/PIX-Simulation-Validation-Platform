# Autoware + CARLA Simulation Validation Platform

This repository is the control plane for an autonomous-driving simulation validation platform.

It is not just an environment setup repo. The current goal is to build a team-usable validation baseline for:

- `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` stable closed-loop verification
- automated regression, replay, KPI gating, and reporting
- site proxy and corner-case accumulation from real map and pointcloud assets
- a future `UE5 / E2E` experiment line that starts with `BEV baseline + VAD shadow`

## Current Focus

The current three-month delivery is organized around four priorities:

1. Make the `stable` stack usable in closed loop.
2. Make `bootstrap / up / run / batch / replay / report` usable for daily validation.
3. Turn the `gy_qyhx_gsh20260302` site assets into reusable site proxy and corner-case inputs.
4. Prepare `UE5 / E2E shadow` as the next-stage capability without destabilizing the main line.

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
- `Luo Shunxiong / lsx`: site proxy, real-site map and pointcloud assets, corner-case replay
- `Yang Zhipeng / Zhipeng Yang`: UE5 remote line, perception and E2E shadow preparation

## Technical Tracks

### Stable Main Line

- Windows host runs CARLA rendering and host-side orchestration
- WSL2 Ubuntu 22.04 runs Autoware Universe, ROS 2 Humble, and bridge components
- CARLA version is fixed to `0.9.15`
- Primary success signal is a repeatable closed loop:
  `startup -> localization -> planning -> control -> goal reached -> report`

### Site Proxy and Corner Cases

- First site bundle: `site_gy_qyhx_gsh20260302`
- Target asset bundle shape:
  - `lanelet2_map.osm`
  - `map_projector_info.yaml`
  - `pointcloud_map.pcd/`
  - `metadata.yaml`
- Large raw assets stay out of Git history and are referenced by manifests

### Future E2E Route

The current recommended route is:

- keep the existing `BEV` perception stack as the production baseline
- run `VAD` in `shadow` mode first
- compare trajectory, behavior, collision, TTC, and route-completion signals
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
- the first reusable `site proxy` scenario still needs to move from asset structure into repeatable validation input
- digest automation works now, but real mail delivery still depends on SMTP secrets and remote UE5 work still depends on a GPU host

## Current Asset Note

The archive `gy_qyhx_gsh20260302_map.zip` remains outside Git tracking because of GitHub file-size constraints. The repository tracks manifests and normalized paths instead of the raw archive itself.
