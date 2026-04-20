---
name: project-digest-triage
description: Use when a task asks for GitHub Project digest generation, blocker triage, owner next actions, weekly review prep, or project-operations automation. This skill builds the digest using the repo's GitHub-only automation path and produces a concise risk summary.
---

# Project digest triage

Use this skill for project-management automation inside this repository.

## Goal
Build or inspect the current project digest and summarize the blockers, due-soon work, scenario watch items, and validation snapshot.

## Standard procedure
1. Prefer the repository's GitHub-only automation path. Do not assume Notion or SMTP are part of the active baseline.
2. Generate the digest with:

```bash
bash .agents/skills/project-digest-triage/scripts/build_digest.sh automation_outputs/project_digest
```

For dry-run or local validation with fixtures:

```bash
bash .agents/skills/project-digest-triage/scripts/build_digest.sh automation_outputs/project_digest tests/fixtures/project_tasks.json tests/fixtures/project_scenarios.json
```

3. Read:
   - `automation_outputs/project_digest/digest.md`
   - `automation_outputs/project_digest/digest_summary.json`
4. Produce:
   - top blockers
   - due-soon tasks and scenarios
   - owner next actions
   - latest validation status signal
   - three highest-leverage moves for the next working session

## Output requirements
Keep the final answer concise and operational. Use exact owner, issue, scenario, or file references where possible.

## Boundaries
- If live GitHub Project reads fail because of token scope, say so clearly and use fixtures only if they were explicitly provided.
- Do not invent external sync systems that are not in the current repository baseline.
