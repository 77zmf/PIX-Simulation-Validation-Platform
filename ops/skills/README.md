# Repo-side Skill Pack

This directory version-controls the repo-specific skill pack used by the PIX Simulation Validation Platform team.

## Included skills

- `autoware-bug-report`
- `autoware-release-check`
- `carla-case-builder`
- `simctl-run-analysis`
- `ai-superbody-pmo`

## Why these skills are stored here

- keep skill prompts aligned with the repo delivery priorities
- let different machines pull the same skill pack from git
- avoid letting useful skill definitions live only in one local `.codex` directory
- make onboarding reproducible for Windows, Mac, and future Ubuntu-side Codex usage

## Relationship to local Codex

These files are the repo-side source of truth.
Local Codex still reads installed skills from:

- `~/.codex/skills/`

The repo copy exists so the team can:

- review skill changes
- sync them by normal git pull
- discuss skill content in issues / PRs
- reinstall the same skill pack on another machine

## Current install source

This pack was imported from the local Codex skill installation used by the project owner.

## Companion docs

- `docs/TEAM_SKILL_USAGE_CN.md`
- `docs/TEAM_AGENT_USAGE_CN.md`
- `docs/SUBAGENT_CATALOG.md`
- `AGENTS.md`
