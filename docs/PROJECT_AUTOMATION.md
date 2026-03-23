# Project Automation

This repository now supports a lightweight project-operations automation path centered on GitHub Projects and a daily digest.

## Automation Scope

The automation is designed to do three things:

1. read the public GitHub task board and scenario board
2. generate a digest with overdue work, due-soon work, blockers, scenario watch items, and validation status
3. send that digest by email if SMTP credentials are configured

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

Generate a digest and attempt email delivery:

```powershell
python -m simctl digest --config ops/project_automation.yaml --output-dir artifacts/project_digest --send-email
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
- email delivery if SMTP settings are present

## Required Secrets For Email Delivery

Do not commit real email addresses or mail credentials to this public repository. Use repository secrets instead.

Required secrets:

- `TEAM_REMINDER_TO`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_FROM`

Optional secrets:

- `TEAM_REMINDER_CC`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `GH_PROJECT_TOKEN`

Notes:

- `GH_PROJECT_TOKEN` is only needed if the default workflow token cannot read the user-owned GitHub Projects.
- `SMTP_USERNAME` and `SMTP_PASSWORD` are only required when the mail server requires authentication.

## Reminder Policy

The digest currently highlights:

- overdue tasks
- tasks due within 3 days
- blocked tasks
- scenarios due within 3 days
- owner-specific action lists
- the latest validation snapshot, when local report data exists

## Recommended Operating Model

- Keep Notion as the detailed planning source of truth.
- Keep GitHub Projects as the public execution mirror and automation input.
- Use daily digest automation for operational reminders.
- Use the weekly review for management decisions, scope control, and escalation.

## Current Limitation

The pipeline is implemented and verifiable in dry-run mode. Real email delivery still depends on mail credentials being configured in GitHub Secrets.
