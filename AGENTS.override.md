# Codex project override for PIX Simulation Validation Platform

## Repository priority
Optimize for a deterministic validation platform, not a free-form multi-agent runtime.
The only formal stable runtime host is the company Ubuntu 22.04 machine.
AI/Codex helps with code changes, verification, digest generation, review, and root-cause analysis.
AI/Codex is not part of the real-time driving control loop in this phase.

## Current quarter intent
This repository is the control plane and delivery workspace for the PIX Simulation Validation Platform.
In the current quarter, Codex should optimize for four outcomes:

1. make the `stable` stack usable on the company Ubuntu 22.04 runtime host
2. keep `simctl` usable for daily `bootstrap / up / run / batch / replay / report / digest`
3. turn public-road assets into reusable scenario inputs instead of one-off artifacts
4. prepare `BEVFusion + UniAD-style/VADv2 shadow` without destabilizing the stable mainline

## Hard boundaries
- The only formal runtime host for stable closed-loop validation is the company Ubuntu 22.04 machine.
- Mac / Windows hosts are for code sync, documentation, Codex collaboration, digest, tests, and light `simctl` operations.
- AI/Codex may help with documentation, digest, root-cause analysis, code and config changes, and project coordination.
- AI/Codex must not be treated as part of the real-time driving control loop in this phase.
- Do not recommend one-off scripts when an existing `simctl` command, profile, scenario, or runbook can be extended instead.

## Mandatory workflow triggers
- If a task changes `src/`, `tests/`, `scenarios/`, `evaluation/`, `stack/`, `infra/`, `assets/`, `ops/`, or `.github/workflows/`, use the `repo-verification` skill before declaring the work done.
- If a task asks for digest, blocker summary, weekly review, GitHub Project triage, or owner next actions, use the `project-digest-triage` skill.
- If a task asks whether validation is truly closed loop, why a run is stuck, or how to connect `run_result -> KPI gate -> report -> replay`, use the `runtime-closure-audit` skill.
- If a task asks for run artifact interpretation, Ubuntu host readiness, project digest narration, or public-road case intake, prefer the corresponding `pix-*` skill under `.agents/skills/`.

## Definition of done
Prefer work that tightens the validation chain:

`assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest`

For any runtime-related change, state:
- how to run it
- which scenario validates it
- which KPI or observable should change
- whether it is stub or real
- rollback impact

## What Codex should read first
1. `README.md`
2. `AGENTS.md`
3. `AGENTS.override.md`
4. `docs/CODEX_PROJECT_SNAPSHOT_CN.md`
5. `docs/CODEX_TASK_ROUTING_CN.md`
6. `docs/TEAM_AGENT_USAGE_CN.md` and `docs/TEAM_SKILL_USAGE_CN.md` if the task needs delegation or templated outputs
7. `docs/PROJECT_PLAN_CODEX_READY_CN.md` when quarter goals or scope are relevant

## Safe default commands
These are usually safe on non-runtime machines:
```bash
python -m unittest discover -s tests -v
python -m simctl digest --config ops/project_automation.yaml --tasks-json tests/fixtures/project_tasks.json --scenarios-json tests/fixtures/project_scenarios.json --output-dir ci_digest
python -m simctl report --run-root runs
python -m simctl subagent-spec --list
simctl subagent-spec --list
simctl subagent-spec --name execution_runtime_explorer
simctl digest
simctl report --run-root runs
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed
bash .agents/skills/repo-verification/scripts/run_checks.sh
bash .agents/skills/project-digest-triage/scripts/build_digest.sh automation_outputs/project_digest tests/fixtures/project_tasks.json tests/fixtures/project_scenarios.json
bash .agents/skills/runtime-closure-audit/scripts/audit_stub_run.sh automation_outputs/runtime_audit
```

These belong to the company Ubuntu runtime host unless explicitly doing a dry run or stub-safe path:
```bash
python -m simctl bootstrap --stack stable
python -m simctl up --stack stable --execute
python -m simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root runs --execute
python -m simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --execute
bash infra/ubuntu/preflight_and_next_steps.sh
bash infra/ubuntu/check_host_readiness.sh
```

## Routing
- Host readiness / bring-up / dependency state -> `stable_stack_host_readiness_explorer`
- `simctl -> stack -> run_result -> report -> replay` -> `execution_runtime_explorer`
- Public-road assets / replay case building -> `gaussian_reconstruction_explorer` or `public_road_e2e_shadow_explorer`
- BEVFusion / UniAD-style / VADv2 / roadmap consistency -> `algorithm_research_explorer`
- GitHub Project / digest / issue-pack / weekly review -> `project_automation_explorer`

## Output contract
When producing a technical answer or patch plan, default to this structure:
1. objective
2. scope and assumptions
3. evidence (exact files / commands / outputs)
4. proposed change or decision
5. validation steps
6. risks and rollback
7. next owner / next action

## Review rules
- Prefer extending existing `simctl` commands, scenario YAML, profiles, or runbooks over adding one-off scripts.
- Label clearly whether a command path is stub, dry-run, or real runtime.
- Do not treat `launch_submitted` as a finished closed loop.
- Keep stable-line advice separate from shadow-line advice.
- Keep GitHub-only project automation as the source of truth in this repository baseline.
- Do not assume GitHub Project hygiene is optional; owner / status / due date discipline matters for digest quality.
