# AGENTS.md for pixmoving-moveit/zmf_ws

## Repository intent
This repository is the control plane and delivery workspace for the PIX Simulation Validation Platform.

Current GitHub URL:

- `pixmoving-moveit/zmf_ws`

Display name:

- `PIX Simulation Validation Platform`

## Delivery priorities
1. stable closed-loop verification on the company Ubuntu 22.04 host
2. reproducible `simctl` workflow: bootstrap / up / run / batch / replay / report
3. public-road asset standardization, `site proxy`, and corner-case accumulation
4. KPI-gated regression, digest generation, and owner clarity
5. shadow evaluation preparation without blocking the stable mainline

## Mainline vs research lines
### Stable validation line
- Autoware Universe main
- ROS 2 Humble
- CARLA 0.9.15
- UE4.26
- `run_result -> KPI gate -> report -> replay`
- public-road replay, regression, and stable batch execution

### Shadow / comparison line
- BEVFusion perception baseline
- UniAD-style shadow
- VADv2 comparison
- no direct production control takeover in this phase
- the same `stable` stack and the same CARLA 0.9.15 runtime baseline

### Reconstruction line
- map refresh for asset and localization support
- static Gaussian reconstruction for geometry-rich replay assets
- dynamic Gaussian reconstruction for future actor-aware replay
- must not block stable delivery in this quarter

## Machine roles
### Company Ubuntu host
- the only formal runtime host for stable validation
- responsible for Autoware + CARLA bring-up, execute path validation, and parallel-slot verification

### Home Windows host
- code editing, repo maintenance, documentation, and Codex collaboration
- can prepare plans and scripts, but does not replace the Ubuntu runtime host

### Mac development terminal
- code sync, Codex usage, digest and document maintenance, and lightweight `simctl` operations
- not the formal stable runtime host

## Working rules in this repo
- Prefer extending existing `simctl` commands over creating one-off scripts.
- Every new scenario should be traceable to source assets, owner, and evaluation method.
- Every batch run should be reviewable through result files, KPI gates, and a concise digest.
- Do not add repo complexity that makes regression harder to rerun.
- If adding config, document default, owner, validation path, and rollback impact.
- Keep stable-line advice clearly separated from shadow/research advice.

## Expected directories
- `src/simctl/` CLI control-plane code
- `docs/` project docs, runbooks, and review material
- `scenarios/` scenario YAML and manifests
- `adapters/profiles/` adapter profiles
- `evaluation/kpi_gates/` evaluation gates
- `assets/` manifests, sensor catalogs, and lightweight metadata
- `stack/` stable stack profile, launch scripts, and slot catalog
- `infra/ubuntu/` host preparation and readiness scripts
- `ops/` automation, issue packs, and subagent specs

## Validation expectation
Any code or config change affecting runtime should state:
- how to run it
- which scenario validates it
- which KPI or observable should change
- what is still stub vs real
- how to roll it back

## Subagent expectation
This repo version-controls reusable subagent specs under:

- `ops/subagents/`

Subagents in this repo should:
- help narrow scope, not broaden it
- prefer exact file references and next actions
- explicitly label what is executable, what is placeholder, and what is blocked on external environment
- optimize for stable delivery first, then shadow/research

## Codex overlay import
This repo also carries a Codex-specific overlay in:

- `AGENTS.override.md`
- `.codex/config.toml`
- `.agents/skills/`
- `.github/codex/prompts/`

For automation, PR review, digest triage, and runtime-closure questions, consult `AGENTS.override.md` and the relevant `.agents/skills/*/SKILL.md` file before acting.
