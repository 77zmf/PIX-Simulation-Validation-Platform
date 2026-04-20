# Project Automation

This repository now uses a GitHub-only project-operations path.

## Scope

The automation does three things:

1. read the GitHub task board and scenario board
2. generate a digest with overdue work, due-soon work, blockers, scenario watch items, and validation status
3. publish that digest as workflow artifacts, step summary text, and a maintained GitHub issue

There is no external wiki sync path or mail-delivery path in the current repository baseline.

## Data Sources

- Task board: `https://github.com/users/77zmf/projects/1`
- Scenario board: `https://github.com/users/77zmf/projects/2`
- Local validation outputs: `runs/**/run_result.json` or `runs/report/summary.json`
- Config: `ops/project_automation.yaml`

## CLI

Generate a digest locally:

```powershell
python -m simctl digest --config ops/project_automation.yaml --output-dir artifacts/project_digest
```

## GitHub Actions

The scheduled workflow is:

- `.github/workflows/project_management.yml`

It runs on:

- manual dispatch
- a weekday schedule for the morning digest

Outputs:

- `digest.md`
- `digest.html`
- `digest_summary.json`
- GitHub Actions job summary
- one auto-maintained GitHub digest issue in the repo

## Required Secrets

Required:

- `GH_PROJECT_TOKEN` only when the default workflow token cannot read the target GitHub Project

Notes:

- For GitHub Project v2, the token should include `read:project` or `project` scope as needed.
- No external wiki token is required.
- No mail-delivery secret is required.

## Reminder Policy

The digest currently highlights:

- overdue tasks
- tasks due within 3 days
- blocked tasks
- overdue scenarios
- scenarios due within 3 days
- owner-specific action lists
- the latest validation snapshot, when local report data exists

## Recommended Operating Model

- Keep GitHub Project as the single project-management source in this repo.
- Keep task status, owner, due date, track, and blocker fields clean enough for digest generation.
- Use the digest issue for asynchronous review and weekly preparation.
- Use the weekly review for scope control, risk handling, and escalation.

## Current Limitation

- The pipeline is implemented and usable in GitHub-only mode.
- Live GitHub Project reads still depend on a token with the needed project scopes.
- Digest quality still depends on board field completeness and assignee discipline.
