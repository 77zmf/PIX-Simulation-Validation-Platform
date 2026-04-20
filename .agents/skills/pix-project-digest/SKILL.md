---
name: pix-project-digest
description: Use when generating or reviewing PIX project digests, GitHub Project blocker triage, weekly review prep, owner next actions, due-soon work, scenario watchlists, milestone status, or PMO summaries for the simulation validation platform.
---

# PIX project digest

Use this skill to turn project-board state and local validation artifacts into an owner-oriented digest. It is a PIX-named wrapper for the repository's GitHub-only project automation and PMO rhythm.

## Procedure

1. Prefer the existing GitHub-only automation path. Do not assume Notion, SMTP, or external databases are active in this repo baseline.
2. Generate or read digest artifacts:

```bash
bash .agents/skills/project-digest-triage/scripts/build_digest.sh automation_outputs/project_digest
```

For fixture-safe local validation:

```bash
bash .agents/skills/project-digest-triage/scripts/build_digest.sh automation_outputs/project_digest tests/fixtures/project_tasks.json tests/fixtures/project_scenarios.json
```

3. Read:
   - `automation_outputs/project_digest/digest.md`
   - `automation_outputs/project_digest/digest_summary.json`
   - `ops/project_automation.yaml`
   - recent `run_result.json` or report artifacts when present
4. Classify work by lane:
   - stable validation line
   - public-road asset or scenario work
   - shadow/research comparison
   - reconstruction support
5. Convert blockers into owner next actions. If owner, due date, status, or evidence is missing, call that out as project-board hygiene.

## Output

Use this structure:

1. Milestone status
2. Top blockers
3. Due-soon or stale work
4. Scenario watchlist
5. Latest validation signal
6. Owner next actions
7. Top three moves for the next work session

## Rules

- Keep the digest concise enough to paste into an issue, inbox item, or weekly review.
- Do not invent owners or completion evidence.
- Keep stable-line advice separate from shadow/research advice.
- State when live GitHub Project reads failed and fixture data was used instead.
