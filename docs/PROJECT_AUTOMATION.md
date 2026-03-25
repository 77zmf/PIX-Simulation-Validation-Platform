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
- Notion Program Board: `https://www.notion.so/dc730999bb7140338b871dd33dfbfeec`
- Notion Scenario Backlog: `https://www.notion.so/2fb616fb48d5429cbb01a7b6299b84e9`
- Local validation outputs: `runs/**/run_result.json` or `runs/report/summary.json`
- Config: `ops/project_automation.yaml`

Repository note:

- the code repository and digest issue target now live at `pixmoving-moveit/zmf_ws`
- the GitHub Project v2 boards are still user-owned under `77zmf` until they are migrated on the GitHub side

## CLI

Generate a digest locally:

```powershell
python -m simctl digest --config ops/project_automation.yaml --output-dir artifacts/project_digest
```

Validate the Notion connection path:

```powershell
python -m simctl notion-check --config ops/project_automation.yaml
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
- one auto-maintained GitHub digest issue in the repo
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

## Required Secret For Notion API Access

- `NOTION_TOKEN`

Notes:

- The integration must have access to the relevant Notion databases.
- The config is set to `provider: auto`, so the digest will prefer Notion when `NOTION_TOKEN` is available and fall back to GitHub Projects otherwise.
- `python -m simctl notion-check` prints the resolved data source status and visible property names, which is useful when the Notion schema changes.
- If you want to use Codex MCP instead of `NOTION_TOKEN`, the local Codex config must enable `rmcp_client`, add the Notion MCP server, and complete OAuth login before restarting Codex.

Notes:

- `GH_PROJECT_TOKEN` is only needed if the default workflow token cannot read the user-owned GitHub Projects.
- For GitHub Project v2, the token must include `read:project` to read the board and `project` to write it.
- `SMTP_USERNAME` and `SMTP_PASSWORD` are only required when the mail server requires authentication.

## Reminder Policy

The digest currently highlights:

- overdue tasks
- tasks due within 3 days
- blocked tasks
- scenarios due within 3 days
- owner-specific action lists
- the latest validation snapshot, when local report data exists

When SMTP secrets are not configured, the workflow still stays useful because it:

- uploads the digest as an artifact
- writes the digest to the workflow summary
- creates or updates a GitHub issue labeled `project-digest`

## Recommended Operating Model

- Keep Notion as the detailed planning source of truth.
- Keep GitHub Projects as the public execution mirror and automation input.
- Use daily digest automation for operational reminders.
- Use the weekly review for management decisions, scope control, and escalation.

## Current Limitation

- The pipeline is implemented and verifiable in dry-run mode.
- Real email delivery still depends on mail credentials being configured in GitHub Secrets.
- Live GitHub Project v2 sync still depends on a token with `read:project` or `project` scopes.
- Live Notion sync still depends on either a valid `NOTION_TOKEN` or a completed local Notion MCP login.
- The repository has moved to `pixmoving-moveit/zmf_ws`, but the task and scenario boards still use the existing `77zmf` project URLs until a separate board migration is completed.
