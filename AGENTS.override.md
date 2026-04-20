# AGENTS.override.md

This override is for the PIX Simulation Validation Platform.

Optimize for **deterministic validation closure** and **repeatable engineering evidence**.
Do **not** optimize for free-form multi-agent experimentation or AI-driven real-time control.

## 1. Mission

The current quarter has four priorities:

1. Close the `stable` validation loop on the company Ubuntu 22.04 host.
2. Make `simctl` the single control-plane entry for bring-up, run, batch, finalize, replay, report, and digest.
3. Promote one public-road asset bundle into a reusable validation case.
4. Keep `BEVFusion` as the stable baseline while `UniAD-style / VADv2` remain shadow-only research lines.

## 2. Non-negotiable boundaries

- AI/Codex is **not** part of the real-time driving control loop.
- Stable closed-loop delivery takes precedence over research expansion.
- `launch_submitted` is **not** a final validation result.
- Prefer extending `simctl`, stack profiles, scenario YAML, KPI gates, reports, and manifests over adding one-off scripts.
- Do not introduce a new simulator runtime. `CARLA 0.9.15` on the stable stack remains the formal baseline.
- Large maps, point clouds, reconstruction outputs, checkpoints, and generated artifacts stay outside Git history and are referenced by manifests.

## 3. Read order

Read in this order unless the user task requires something more specific:

1. `README.md`
2. `AGENTS.md`
3. `AGENTS.override.md`
4. `docs/CODEX_PROJECT_SNAPSHOT_CN.md`
5. `docs/CODEX_TASK_ROUTING_CN.md`
6. `docs/PROJECT_PLAN_CODEX_READY_CN.md`
7. task-specific files under `src/`, `stack/`, `infra/`, `assets/`, `scenarios/`, `evaluation/`, `ops/`, or `tests/`

## 4. Current project truth

Treat the following as the most important project truths:

- The control plane is already taking shape.
- The biggest remaining gap is real runtime closure on the Ubuntu host.
- Public-road assets must become reusable scenario inputs rather than one-off demonstrations.
- Shadow research must not destabilize the stable main line.
- A useful result is not a startup log alone; it is a finalized validation artifact chain.

## 5. Definition of done

A stable-line execution task is done only when all of the following are true:

- the run has a concrete `run_result.json`
- runtime evidence exists and is traceable
- KPI gate evaluation has produced a final status
- report and replay entry points exist
- slot/process cleanup is known
- the result can be explained as `passed` or `failed`, not only `launch_submitted`

The preferred result chain is:

`assets/scenario -> simctl run/up --execute -> runtime evidence -> finalized run_result -> KPI gate -> report/replay -> digest`

## 6. How to reason about tasks

### Stable runtime / host closure
Focus on:
- `src/simctl/`
- `stack/profiles/`
- `stack/slots/`
- `stack/stable/`
- `infra/ubuntu/`
- `evaluation/`
- `tests/`

Look for:
- stub vs real execute differences
- runtime evidence gaps
- host readiness gaps
- slot lifecycle problems
- finalization gaps
- report / digest contract drift

### Public-road asset and scenario promotion
Focus on:
- `assets/`
- `scenarios/`
- `adapters/profiles/`
- `evaluation/kpi_gates/`
- `tools/`

Look for:
- missing semantic asset checks
- bundle-to-scenario promotion gaps
- route / localization / projector consistency
- reusable scenario templates rather than one-off case descriptions

### Shadow research
Focus on:
- comparison contracts
- output metrics
- interface assumptions
- non-blocking integration with the stable line

Do not treat shadow outputs as production acceptance evidence.

### Project automation / digest
Focus on:
- state semantics
- blocker surfacing
- owner next actions
- alignment between board status and validation status

## 7. Preferred output contract

Default to this structure in answers:

1. **objective**
2. **scope / assumptions**
3. **evidence**
4. **analysis / decision**
5. **changes / next steps**
6. **validation**
7. **risk / rollback**

When analyzing runtime issues, always distinguish:
- what is already deterministic
- what is still placeholder / mocked
- what requires the real Ubuntu runtime host

## 8. What to recommend first

Prefer the smallest changes that improve repeatability this week:

- finalize / collect stage after execute
- host BOM and preflight artifacts
- slot lease / cleanup improvements
- semantic asset checks
- stable vs shadow report separation
- test coverage for schemas and result finalization

## 9. First commands to keep in mind

- `simctl bootstrap --stack stable`
- `simctl up --stack stable --scenario scenarios/l0/smoke_stub.yaml`
- `simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root runs`
- `simctl run --scenario scenarios/l1/regression_follow_lane.yaml --run-root runs --slot stable-slot-01`
- `simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed`
- `simctl report --run-root runs`
- `simctl digest`

If the user asks for design changes, prefer repository-local changes that reinforce this command chain.
