# Subagent Catalog

This repository stores reusable Codex subagent definitions under `ops/subagents/`.

These files do not sync live spawned agents across machines. Live subagents are session-scoped.
What is synchronized is the reusable definition so another machine can recreate the same subagent with the same role and prompt.

## Available Specs

- `execution_runtime_explorer`
- `algorithm_research_explorer`

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

## Recommended Use

1. Pull the latest repo on the other machine.
2. Activate the repo environment.
3. Run `python -m simctl subagent-spec --list`.
4. Render the spec you want.
5. Use the emitted JSON fields as the `spawn_agent` input in Codex.

## Notes

- Specs are versioned with the repository, so prompt changes travel with normal git sync.
- If you need a new reusable subagent role, add a new YAML file under `ops/subagents/`.
