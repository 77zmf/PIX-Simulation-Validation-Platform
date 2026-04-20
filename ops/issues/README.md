# GitHub Issue Pack

This directory stores reusable issue-plan drafts and publishing helpers for the current quarter.

## Current Pack

- `2026_q2/manifest.json`
- `2026_q2/*.md`

These markdown files are not a live issue state mirror.
They are the repo-side source of truth for the issue bodies we want to create or update on GitHub.

## Why This Exists

- keep owner-facing plans versioned with the repository
- make teammate onboarding repeatable
- capture what to read, which subagents to use, and what to deliver
- avoid letting important execution plans live only in chat

## Publish Locally

If you have a GitHub token with issue write permission:

```bash
export GITHUB_TOKEN=<token>
python tools/publish_issue_plan.py \
  --repo 77zmf/PIX-Simulation-Validation-Platform \
  --manifest ops/issues/2026_q2/manifest.json \
  --lsx-username <lsx_github_username> \
  --yang-username <yang_github_username> \
  --coordinator-username 77zmf
```

Dry-run without publishing:

```bash
python tools/publish_issue_plan.py \
  --repo 77zmf/PIX-Simulation-Validation-Platform \
  --manifest ops/issues/2026_q2/manifest.json \
  --lsx-username <lsx_github_username> \
  --yang-username <yang_github_username> \
  --coordinator-username 77zmf \
  --dry-run \
  --render-dir artifacts/issue_plan_dry_run
```

## Publish From GitHub Actions

The repository includes a workflow:

- `.github/workflows/publish_issue_plan.yml`

Current default mentions:

- `罗顺雄 / lsx -> @lsxala`
- `杨志朋 / Zhipeng Yang -> @yzp333666`
- `Coordinator -> @77zmf`

You can run it from the Actions page and provide:

- `lsx_username`
- `yang_username`
- optional `coordinator_username`

If the usernames are not provided, the workflow now falls back to the current defaults above. Dry-run mode is still used when publishing is explicitly disabled or credentials are unavailable.
