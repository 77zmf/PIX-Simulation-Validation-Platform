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

Render only the prompt text:

```powershell
python -m simctl subagent-spec --name algorithm_research_explorer --format prompt
```

## Recommended Fixed Roles

- `execution_runtime_explorer`: execution chain, host/runtime, stack readiness, launch/result bottlenecks
- `algorithm_research_explorer`: planning, perception, E2E, and cross-track roadmap consistency
- `project_automation_explorer`: GitHub Project, Notion, digest workflow, secrets, and sync reliability
- `gaussian_reconstruction_explorer`: static/dynamic Gaussian reconstruction, gates, and roadmap alignment
- `public_road_e2e_shadow_explorer`: BEVFusion to UniAD/VADv2 shadow path, scenarios, metrics, and implementation gaps
- `stable_stack_host_readiness_explorer`: Ubuntu host, CARLA/Autoware bring-up, readiness probes, and repeatability gaps

## Recommended Use

1. Pull the latest repo on the other machine.
2. Activate the repo environment.
3. Run `python -m simctl subagent-spec --list`.
4. Render the spec you want.
5. Use the emitted JSON fields as the `spawn_agent` input in Codex.

## Notes

- Specs are versioned with the repository, so prompt changes travel with normal git sync.
- If you need a new reusable subagent role, add a new YAML file under `ops/subagents/`.
