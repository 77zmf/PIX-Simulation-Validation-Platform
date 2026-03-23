# simctl

`simctl` 是这个仓库的控制平面，用来编排两条仿真验证线：

- `stable`：`Autoware Universe main + ROS 2 Humble + CARLA 0.9.15`
- `ue5`：远端 GPU 主机上的 `CARLA 0.10.x / UE5`

这个仓库不直接托管大型点云、地图切片和 UE 资产；它托管的是脚本、配置、场景定义、KPI 门禁、适配器接口和轻量运行工件。

## Layout

```text
infra/       Host and remote preparation scripts
stack/       Stack launch profiles and helper scripts
assets/      Asset manifests, map metadata, sensor profiles
scenarios/   L0-L3 and UE5 scenario definitions
evaluation/  KPI gates, reports, failure taxonomy
adapters/    Algorithm profile examples
src/simctl/  CLI and control-plane implementation
tests/       Local verification for the control plane
```

## Team Planning

The repo-side quarter plan and operating documents live in:

- `docs/TEAM_90_DAY_PLAN.md`
- `docs/TEAM_OPERATING_RHYTHM.md`
- `docs/QUARTER_ACCEPTANCE.md`
- `docs/PROJECT_MANAGEMENT_OVERVIEW_CN.md`

These documents should stay aligned with the team Notion project pages and the current `Program Board`.

## Project Management Portal

The current project-management snapshot is available in:

- `docs/PROJECT_MANAGEMENT_OVERVIEW_CN.md`
- `docs/index.html`

If GitHub Pages is enabled for this repository, the static portal is expected at:

- `https://77zmf.github.io/zmf_ws/`

## Quick Start

1. Create a virtual environment and install the package:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -e .
   ```

2. Inspect bootstrap plans for the stable stack:

   ```powershell
   simctl bootstrap --stack stable
   ```

3. Run a local stub smoke scenario and generate a report:

   ```powershell
   simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root runs
   simctl report --run-root runs
   ```

4. Batch a few scenarios with synthetic pass/fail outcomes:

   ```powershell
   simctl batch --glob "scenarios/l1/*.yaml" --run-root runs --mock-result passed
   simctl report --run-root runs
   ```

## Key Concepts

- `asset_bundle`: a reusable site or map bundle that points to the authoritative map and pointcloud assets.
- `scenario.yaml`: the execution contract for one experiment.
- `kpi_gate`: threshold policy that determines whether a run passes.
- `run_result.json`: the canonical output for one run.

## Environment Defaults

- Windows host runs CARLA rendering and local orchestration.
- WSL2 Ubuntu 22.04 runs Autoware Universe, ROS 2 Humble, and CARLA bridge components.
- UE5 workloads are submitted to a remote GPU host.

## Current Site Asset

The first site proxy bundle is `site_gy_qyhx_gsh20260302`. It references:

- `lanelet2_map.osm`
- `map_projector_info.yaml`
- `pointcloud_map.pcd/` tiles from `gy_qyhx_gsh20260302_map.zip`

The archive itself remains out of Git history and is referenced through the asset manifest.
