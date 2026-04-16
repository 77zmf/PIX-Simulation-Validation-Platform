# Subagent Catalog

This repository stores reusable Codex subagent definitions under `ops/subagents/`.

These files do not sync live spawned agents across machines. Live subagents are session-scoped.
What is synchronized is the reusable definition so another machine can recreate the same subagent with the same role and prompt.

## Available Specs

- `execution_runtime_explorer`
- `algorithm_research_explorer`
- `project_automation_explorer`
- `gaussian_reconstruction_explorer`
- `public_road_e2e_shadow_explorer`
- `stable_stack_host_readiness_explorer`

## CLI

List available specs:

```powershell
python -m simctl subagent-spec --list
```

Render one spec as JSON payload for `spawn_agent`:

```powershell
python -m simctl subagent-spec --name execution_runtime_explorer
```

List onboarding profiles:

```powershell
python -m simctl subagent-spec --list-onboarding
```

Render one onboarding profile:

```powershell
python -m simctl subagent-spec --onboarding yzp333666
```

Render only the prompt text:

```powershell
python -m simctl subagent-spec --name algorithm_research_explorer --format prompt
```

Render a ready-to-use `spawn_agent` payload:

```powershell
python -m simctl subagent-spec --name execution_runtime_explorer --format spawn_json
```

## Recommended Fixed Roles

- `execution_runtime_explorer`: stable execution chain, slot-based parallel runs, launch/result bottlenecks
- `algorithm_research_explorer`: planning, perception, E2E shadow, reconstruction, and cross-track roadmap consistency
- `project_automation_explorer`: GitHub Project, issue packs, digest workflow, secrets, and sync reliability
- `gaussian_reconstruction_explorer`: static/dynamic Gaussian reconstruction, source assets, gates, and roadmap alignment
- `public_road_e2e_shadow_explorer`: BEVFusion to UniAD/VADv2 shadow path, scenarios, metrics, and implementation gaps
- `stable_stack_host_readiness_explorer`: company Ubuntu host, CARLA/Autoware bring-up, readiness probes, and repeatability gaps

## Project Fit

This repository is centered on four active pressures:

- stable closed-loop repeatability on the Ubuntu host
- public-road `BEVFusion + shadow E2E` preparation
- Gaussian reconstruction and map-refresh research
- GitHub / digest automation for execution tracking

Because of that, not all specs should be used with the same frequency.

### Core Daily Drivers

- `execution_runtime_explorer`
  Use when the problem is in `simctl -> stack -> runtime -> run_result`, especially if slots, ports, namespaces, or run-dir isolation are involved.
- `stable_stack_host_readiness_explorer`
  Use when the problem is in Ubuntu host readiness, CARLA/Autoware bring-up, environment variables, package state, or service health.
- `public_road_e2e_shadow_explorer`
  Use when the question is about `BEVFusion`, `UniAD-style`, `VADv2`, shadow planner interfaces, or public-road E2E scenarios on the stable runtime baseline.
- `gaussian_reconstruction_explorer`
  Use when the question is about `map_refresh`, `static_gaussians`, `dynamic_gaussians`, or 3D reconstruction execution gaps.

### Secondary, Use As Needed

- `algorithm_research_explorer`
  Use when you want one cross-track view spanning planning, perception, E2E, and reconstruction together.
- `project_automation_explorer`
  Use when the question is about GitHub Project, digest workflow, secrets, or synchronization reliability.

### Default Routing

- Runtime or launch issue: start with `execution_runtime_explorer`.
- Host or bring-up issue: start with `stable_stack_host_readiness_explorer`.
- Public-road E2E issue: start with `public_road_e2e_shadow_explorer`.
- Reconstruction issue: start with `gaussian_reconstruction_explorer`.
- Multi-track roadmap question: use `algorithm_research_explorer`.
- Planning board or digest issue: use `project_automation_explorer`.

### What To Avoid

- Do not use `algorithm_research_explorer` for a narrow runtime bug when `execution_runtime_explorer` is enough.
- Do not use `project_automation_explorer` for algorithm debugging.
- Do not use `public_road_e2e_shadow_explorer` for host bring-up.
- Do not use `gaussian_reconstruction_explorer` for general planning/control discussions unless reconstruction is the actual focus.

## Recommended Use

1. Pull the latest repo on the other machine.
2. Activate the repo environment.
3. Run `python -m simctl subagent-spec --list`.
4. Run `python -m simctl subagent-spec --list-onboarding` if you want role-based guidance first.
5. Render the spec or onboarding profile you want.
6. Use `--format spawn_json` if you want a direct `spawn_agent` parameter object.
7. Use the emitted JSON as the `spawn_agent` input in Codex.

## Notes

- Specs are versioned with the repository, so prompt changes travel with normal git sync.
- If you need a new reusable subagent role, add a new YAML file under `ops/subagents/`.
- Repo-level agent defaults also live in `AGENTS.md`; keep the catalog and `AGENTS.md` aligned.
