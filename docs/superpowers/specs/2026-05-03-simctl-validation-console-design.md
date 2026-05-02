# Simctl Validation Console Design

## Objective

Add a first UI surface to the AI Superbody plan so project members can run and review validation work without memorizing the full `simctl` command set.

The UI must make daily validation easier for Zhu Minfeng and collaborators while preserving the repository's formal evidence chain:

`assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest`

This is a workflow and usability layer. It must not become a separate simulator runtime, a separate source of validation truth, or a bypass around `simctl`.

## Reference

The external reference is `9900ff/CARLA_GUI`:

- Repository: <https://github.com/9900ff/CARLA_GUI>
- README: <https://github.com/9900ff/CARLA_GUI/blob/master/readme.md>
- Dependencies: <https://github.com/9900ff/CARLA_GUI/blob/master/requirements.txt>

Useful ideas from the reference:

- one-click CARLA server start and stop
- connection and server status display
- vehicle spawn and basic control
- spectator follow and camera movement
- map and weather controls
- saved local configuration
- low-friction packaged usage for non-core developers

Boundaries for this repository:

- Use `CARLA_GUI` as a product reference first, not as copied source code.
- Do not vendor external code until license and maintenance ownership are checked.
- Keep CARLA direct manipulation in a debug/shadow area unless it is encoded back into scenario YAML, runtime evidence, and KPI gates.

## Scope

In scope for the first version:

- A lightweight validation console for `simctl` workflows.
- Scenario selection from existing `scenarios/`.
- Slot selection from `stack/slots/stable_slots.yaml`.
- Run mode selection: repo-local dry run, mock result, or host execute.
- Command preview before execution.
- Controlled execution of existing commands:
  - `simctl run`
  - `simctl batch`
  - `simctl validate --finalize --report`
  - `simctl report`
  - `simctl replay`
  - `simctl digest`
- Status display from `run_result.json`, report outputs, and digest outputs.
- Read-only reviewer mode for teammates who only need to inspect results.
- Debug/shadow tab inspired by `CARLA_GUI`, limited to CARLA connection status, weather/map visibility, spectator notes, and operator hints.

Out of scope for the first version:

- Replacing `simctl`.
- Direct AI or UI involvement in real-time driving control.
- A new simulator runtime.
- Direct stable acceptance based on UI state alone.
- Full CARLA actor authoring or manual scene editing as a stable validation source.
- Copying or vendoring `CARLA_GUI` source code.
- Editing large maps, point clouds, reconstruction outputs, model checkpoints, or generated artifacts.

## Users

Primary user:

- Zhu Minfeng, who needs to start runs, inspect artifacts, and keep the validation loop moving.

Secondary users:

- Collaborators who need to review `passed`, `failed`, or `blocked` evidence without knowing every `simctl` command.
- Asset and scenario owners who need to see whether their scenario has enough inputs and evidence.
- PMO reviewers who need a concise path from a project item to run evidence, report, replay, and digest.

## Architecture

Recommended first implementation:

- A repo-local web UI served by a small `simctl`-owned backend.
- The backend is a thin command and artifact layer, not a new orchestration engine.
- The frontend stays static or near-static enough that it can be used by teammates through a browser.

Proposed modules:

- `src/simctl/console.py`
  - loads scenarios, slots, run roots, reports, and run results
  - builds command previews
  - validates requested actions against an allowlist
- `src/simctl/console_server.py`
  - optional local HTTP server entry point
  - starts from a future command such as `simctl console`
- `src/simctl/console_static/`
  - HTML, CSS, and JavaScript assets if the first implementation avoids a frontend build step
- `tests/test_console.py`
  - command preview, artifact indexing, allowlist, and status semantics

The current `pyproject.toml` only depends on `PyYAML`. The first implementation should avoid adding a heavy frontend framework unless static assets are no longer enough. If a Python HTTP dependency is added, document why it is needed and how to run it on the company Ubuntu host.

## UI Surface

### 1. Run Console

Purpose: start one controlled validation run.

Controls:

- scenario picker grouped by L0, L1, L2, L3, and E2E/shadow
- stack selector, default `stable`
- slot selector, default from available stable slots
- run root input, default `runs`
- mode selector:
  - local dry run
  - mock result
  - host execute
- checkboxes for:
  - finalize
  - report
  - digest
- command preview area
- run button

Rules:

- The UI must show the exact command before execution.
- Host execute must display that formal stable acceptance still requires company Ubuntu host evidence.
- The UI must not silently add CARLA debug changes to a stable run.

### 2. Review Console

Purpose: let teammates understand what happened after a run.

Data sources:

- `runs/**/run_result.json`
- `runs/**/runtime_evidence.json`
- `runs/**/preflight_report.json`
- `runs/**/health.json`
- `runs/**/report/report.md`
- `runs/**/report/report.html`
- digest outputs under `artifacts/project_digest/`

Display:

- run id
- scenario id
- owner if present in metadata
- status: `passed`, `failed`, `blocked`, `launch_failed`, `launch_submitted`, or `runtime_collecting`
- KPI gate verdict
- failed metrics and failure labels
- host and preflight summary when present
- report link
- replay command or replay plan link
- digest link when present

Rules:

- `launch_submitted` must be displayed as incomplete, not as pass.
- Mac/local stub evidence must be labeled as repo-local validation only.
- Shadow results must be visually separated from stable acceptance.

### 3. Debug Console

Purpose: provide a controlled place for CARLA convenience features inspired by `CARLA_GUI`.

First version:

- show configured CARLA host and port
- show connection status if a slot is active
- show active map, weather, sync mode, and actor count if available from existing probes
- link to relevant run logs and health output
- document operator notes for spectator or manual visual checks

Deferred:

- direct weather changes
- direct map switching
- direct actor spawn
- vehicle teleport
- manual driving

These deferred controls can be added later only if each action is either debug-only or converted into a scenario/probe artifact that can be repeated.

## Command Contract

The console must produce commands equivalent to existing CLI usage.

Single scenario, local-safe:

```bash
simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root runs --slot stable-slot-01
simctl validate --run-dir runs/<run_id> --finalize --report
```

Single scenario, host execute:

```bash
simctl run --scenario scenarios/l1/regression_follow_lane.yaml --run-root runs --slot stable-slot-01 --execute
simctl validate --run-dir runs/<run_id> --execute --finalize --report
```

Batch review:

```bash
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --finalize --report
simctl report --run-root runs
simctl digest --run-root runs
```

Replay:

```bash
simctl replay --run-result runs/<run_id>/run_result.json
```

The console must store an operator action log in the run directory when it executes commands. The log must include timestamp, command, return code, stdout path, stderr path, and user-facing mode.

## Data Flow

1. User opens `simctl console`.
2. Backend indexes scenarios, slots, and recent runs.
3. User selects scenario and mode.
4. Backend builds command preview.
5. User confirms execution.
6. Backend runs the allowlisted command and streams or records logs.
7. Backend re-indexes the run root.
8. UI displays `run_result.json`, KPI verdict, reports, replay entry, and digest links.

The UI reads artifacts after `simctl` writes them. It must not infer a pass or fail result without a run artifact.

## Status Semantics

The UI must follow the existing stable-line semantics:

- `planned`: command prepared but not launched
- `launch_failed`: startup failed before useful runtime evidence
- `launch_submitted`: startup accepted but final evidence is not complete
- `runtime_collecting`: probes or finalization are still collecting evidence
- `passed`: KPI gate produced a passing final status
- `failed`: KPI gate produced a failing final status
- `blocked`: missing host, missing assets, missing config, auth failure, or command failure that prevents execution

Reviewer mode defaults to sorting by `blocked`, `failed`, `runtime_collecting`, `launch_submitted`, then `passed`.

## Error Handling

The console must fail closed.

Blocked examples:

- requested scenario path is outside `scenarios/`
- requested slot is not in `stack/slots/stable_slots.yaml`
- requested command is not in the allowlist
- host execute is selected on a machine without required runtime readiness
- `run_result.json` is missing after a run
- finalize or report exits non-zero
- the run is shadow-only but the user tries to mark it as stable acceptance

Every blocked state must produce:

- human-readable reason
- exact command or file that failed
- next action
- rollback or cleanup hint when relevant

## Security And Safety

- No arbitrary shell input in the first version.
- All commands are constructed from parsed scenario, slot, and mode choices.
- Paths are normalized under the repository root or configured run root.
- Host execute is disabled by default unless explicitly enabled.
- Stable execution and debug CARLA manipulation must be separate UI modes.
- The console must not expose secrets, DingTalk webhooks, GitHub tokens, or proxy values.

## Validation

Repo-local validation:

```bash
PYTHONPATH=src python3 -m unittest tests.test_console -v
PYTHONPATH=src python3 -m simctl --repo-root . run --scenario scenarios/l0/smoke_stub.yaml --run-root /tmp/simctl_console_smoke --slot stable-slot-01
PYTHONPATH=src python3 -m simctl --repo-root . report --run-root /tmp/simctl_console_smoke
```

UI smoke validation after implementation:

```bash
PYTHONPATH=src python3 -m simctl --repo-root . console --run-root /tmp/simctl_console_smoke --host 127.0.0.1 --port 8765
```

Expected UI smoke:

- scenario list renders
- command preview matches CLI arguments
- local smoke run creates a `run_result.json`
- report link appears after report generation
- `launch_submitted` is not shown as pass
- shadow scenarios are labeled separately

Ubuntu-host validation:

```bash
simctl console --run-root runs --host 0.0.0.0 --port 8765
```

Then from the console:

- run one L0 or L1 stable scenario with `--execute`
- finalize and report
- confirm final KPI status appears
- confirm replay entry is visible

Mac/local validation only proves UI wiring, command construction, artifact indexing, and reporting. It does not prove stable closed-loop acceptance.

## Rollout

Phase 1:

- Add spec and plan.
- Keep implementation out of the current dirty runtime work.

Phase 2:

- Add read-only artifact browser.
- Add tests for run indexing and status semantics.

Phase 3:

- Add command preview and local-safe run execution.
- Add operator action log.

Phase 4:

- Add controlled host execute mode.
- Add CARLA debug status panel.

Phase 5:

- Consider whether selected `CARLA_GUI`-style controls are worth adding as debug-only actions.
- Only promote a debug action into stable workflow if it is represented by scenario YAML, runtime evidence, KPI gates, report, and replay.

## Risks And Rollback

Risks:

- A convenient UI can hide important validation semantics if status labels are too friendly.
- Direct CARLA controls can create non-repeatable scene state.
- A heavy frontend stack can make the repo harder for collaborators to run.
- Host execute through a browser can create safety and access-control concerns.
- External code reuse may be blocked by licensing or maintenance ownership.

Rollback:

- Disable or remove `simctl console`.
- Keep all `simctl` CLI commands unchanged.
- Preserve generated run artifacts.
- Remove the UI from docs and daily workflow without affecting stable validation.

## Decision

The first UI addition to the AI Superbody plan is `UI-001: simctl validation console`.

It prioritizes teammate usability through controlled command preview, run review, and artifact browsing. `CARLA_GUI` influences the debug experience and packaging expectations, but the stable line remains anchored to `simctl` and final evidence.
