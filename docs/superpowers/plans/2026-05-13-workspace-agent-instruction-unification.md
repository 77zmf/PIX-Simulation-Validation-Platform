# Workspace Agent Instruction Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the accidental global PIX-specific Codex instructions with workspace-neutral guidance and add lightweight local guidance for the active note-maintenance workspaces.

**Architecture:** The implementation keeps global rules portable and routes domain-specific behavior back to each workspace's nearest `AGENTS.md` or `AGENTS.override.md`. It edits only three instruction files outside runtime code: the global Codex guidance file, `zmf_terminal/AGENTS.md`, and `Obsidian Vault/AGENTS.md`.

**Tech Stack:** Markdown instruction files, Codex `AGENTS.md` discovery, shell validation with `test`, `readlink`, `sed`, and `git status`.

---

## File Structure

- Modify: `/Users/cyber/.codex/AGENTS.md`
  - Responsibility: global workspace-neutral Codex collaboration guidance.
  - Current state: symlink to `/Users/cyber/Documents/zmf_ws/AGENTS.md`.
- Create: `/Users/cyber/Documents/zmf_terminal/AGENTS.md`
  - Responsibility: local guidance for AI Superbody note and PMO maintenance.
- Create: `/Users/cyber/Documents/Obsidian Vault/AGENTS.md`
  - Responsibility: local guidance for conservative user knowledge-vault edits.
- Read only: `/Users/cyber/Documents/zmf_ws/docs/superpowers/specs/2026-05-13-workspace-agent-instruction-unification-design.md`
  - Responsibility: approved design source.
- Read only: `/Users/cyber/Documents/zmf_ws`
  - Responsibility: ensure runtime files are not modified by this cleanup.

## Task 1: Baseline Safety Check

**Files:**
- Read: `/Users/cyber/.codex/AGENTS.md`
- Read: `/Users/cyber/Documents/zmf_ws/docs/superpowers/specs/2026-05-13-workspace-agent-instruction-unification-design.md`
- Read: `/Users/cyber/Documents/zmf_ws`

- [ ] **Step 1: Confirm `zmf_ws` has no uncommitted changes**

Run:

```bash
git -C /Users/cyber/Documents/zmf_ws status --short --branch
```

Expected output shape:

```text
## main...origin/main [ahead N]
```

There should be no `M`, `A`, `D`, or `??` entries. If entries appear, stop and ask the user before editing.

- [ ] **Step 2: Confirm the current global guidance is a symlink**

Run:

```bash
test -L /Users/cyber/.codex/AGENTS.md && readlink /Users/cyber/.codex/AGENTS.md
```

Expected output:

```text
/Users/cyber/Documents/zmf_ws/AGENTS.md
```

If it is already a regular file, inspect it before overwriting:

```bash
sed -n '1,220p' /Users/cyber/.codex/AGENTS.md
```

- [ ] **Step 3: Confirm the two target workspace directories exist**

Run:

```bash
test -d /Users/cyber/Documents/zmf_terminal && echo zmf_terminal-ok
test -d "/Users/cyber/Documents/Obsidian Vault" && echo obsidian-vault-ok
```

Expected output:

```text
zmf_terminal-ok
obsidian-vault-ok
```

If either directory is missing, skip only that directory's `AGENTS.md` task and record the skip in the final validation.

## Task 2: Replace Global Codex Guidance

**Files:**
- Modify: `/Users/cyber/.codex/AGENTS.md`

- [ ] **Step 1: Remove the symlink**

Run:

```bash
rm /Users/cyber/.codex/AGENTS.md
```

Expected: no output and exit code 0.

- [ ] **Step 2: Create the regular global guidance file**

Write this exact content to `/Users/cyber/.codex/AGENTS.md`:

```markdown
# Global Codex Guidance

## Purpose

This file contains workspace-neutral Codex collaboration rules. Project-specific behavior belongs in the nearest workspace `AGENTS.md`, `AGENTS.override.md`, `.codex/config.toml`, or `.agents/skills/` directory.

## First steps in every workspace

- Identify the current working directory and the nearest project root before acting.
- Read and follow project-local guidance before making assumptions.
- If a task matches an available skill description, use that skill before acting.
- Keep each workspace's domain rules local: PIX simulation, vehicle road tests, publication workflows, Cyrus learning, and Obsidian notes are separate work modes.

## Editing rules

- Protect dirty worktrees. Do not stage, revert, delete, or overwrite unrelated user changes.
- Prefer small, reversible edits that match the current workspace's existing patterns.
- Do not move domain-specific commands into global guidance.
- Do not treat Mac/local checks as company Ubuntu host acceptance for PIX stable runtime work.
- Do not treat note synthesis as source evidence; keep source paths and synthesized notes distinct.

## Verification

- Before claiming completion, state the commands or checks that validate the work.
- If a task cannot be fully validated in the current environment, say exactly what remains blocked and where it must be validated.
- For code changes, run the narrowest relevant checks first, then broader checks when the project-local guidance requires them.

## Active workspace routing

- `/Users/cyber/Documents/zmf_ws`: PIX Simulation Validation Platform. Follow its repo `AGENTS.md`, `AGENTS.override.md`, and PIX skills.
- `/Users/cyber/Documents/zmf_test-data`: road-test evidence, vehicle-side operations, GitHub issue evidence, and OSS failcase handoff.
- `/Users/cyber/Documents/zmf_ws_publish`: publication and portable workflow sharing for PIX materials.
- `/Users/cyber/Documents/Cyrus-Learning-Manager`: TypeScript learning manager, local sync service, Obsidian/Notion sync, and GitHub Pages app.
- `/Users/cyber/Documents/zmf_terminal`: AI Superbody note, PMO, and document maintenance workspace.
- `/Users/cyber/Documents/Obsidian Vault`: user knowledge vault. Edit conservatively and preserve existing structure.
```

- [ ] **Step 3: Verify it is a regular file**

Run:

```bash
test -f /Users/cyber/.codex/AGENTS.md && test ! -L /Users/cyber/.codex/AGENTS.md && echo global-agents-regular-file
```

Expected output:

```text
global-agents-regular-file
```

- [ ] **Step 4: Verify PIX-only commands are not global defaults**

Run:

```bash
rg -n "simctl bootstrap|CARLA 0.9.15|run_result -> KPI gate|Autoware Universe main" /Users/cyber/.codex/AGENTS.md
```

Expected: no matches and exit code 1.

## Task 3: Add `zmf_terminal` Workspace Guidance

**Files:**
- Create: `/Users/cyber/Documents/zmf_terminal/AGENTS.md`

- [ ] **Step 1: Check whether the file already exists**

Run:

```bash
test -e /Users/cyber/Documents/zmf_terminal/AGENTS.md; echo $?
```

Expected output before this implementation:

```text
1
```

If the output is `0`, inspect the existing file and merge the guidance instead of overwriting:

```bash
sed -n '1,220p' /Users/cyber/Documents/zmf_terminal/AGENTS.md
```

- [ ] **Step 2: Create the local guidance file**

Write this exact content to `/Users/cyber/Documents/zmf_terminal/AGENTS.md`:

```markdown
# AGENTS.md for zmf_terminal

## Workspace purpose

This workspace is for AI Superbody note maintenance, PMO synthesis, document preparation, and Codex collaboration around project state. It is not the formal runtime workspace for PIX stable validation.

## Source of truth

- Use `/Users/cyber/Documents/zmf_ws` as the source layer for PIX Simulation Validation Platform evidence and runtime state.
- Use `/Users/cyber/Documents/Obsidian Vault` as the destination layer for long-lived notes unless the user gives a different path.
- Preserve explicit evidence paths, dates, owners, blockers, and validation status when turning source material into notes.

## Working rules

- Extend the existing AI Superbody and PMO note structure instead of creating a parallel vault or duplicate hierarchy.
- Keep validated facts, blockers, next actions, and broader ideas separate.
- Do not present local Mac checks as stable Ubuntu host acceptance.
- Do not overwrite user-authored notes unless the user explicitly asks for a replacement.
- When runtime evidence has mixed pass/fail results, preserve that nuance.

## Expected validation

- For note edits, verify the target files exist and the changed sections are readable.
- For PMO refreshes, cite the source documents or local evidence paths used.
- For generated docs, keep the output in Markdown unless the user requests another format.
```

- [ ] **Step 3: Verify the new file contains the workspace purpose**

Run:

```bash
rg -n "AI Superbody note maintenance|not the formal runtime workspace|Preserve explicit evidence paths" /Users/cyber/Documents/zmf_terminal/AGENTS.md
```

Expected output includes three matching lines.

## Task 4: Add Obsidian Vault Workspace Guidance

**Files:**
- Create: `/Users/cyber/Documents/Obsidian Vault/AGENTS.md`

- [ ] **Step 1: Check whether the file already exists**

Run:

```bash
test -e "/Users/cyber/Documents/Obsidian Vault/AGENTS.md"; echo $?
```

Expected output before this implementation:

```text
1
```

If the output is `0`, inspect the existing file and merge the guidance instead of overwriting:

```bash
sed -n '1,220p' "/Users/cyber/Documents/Obsidian Vault/AGENTS.md"
```

- [ ] **Step 2: Create the local guidance file**

Write this exact content to `/Users/cyber/Documents/Obsidian Vault/AGENTS.md`:

```markdown
# AGENTS.md for Obsidian Vault

## Workspace purpose

This directory is the user's Obsidian knowledge vault. Treat it as a long-lived personal knowledge base, not a scratch workspace.

## Working rules

- Preserve existing folder structure, note names, links, tags, canvases, and user-authored wording unless the user asks for a rewrite.
- Prefer extending existing notes over creating duplicate notes with similar purpose.
- Keep source evidence separate from synthesis. When a note summarizes project state, include source paths or links that support the summary.
- Do not bulk-reformat the vault.
- Do not delete notes, attachments, canvases, or generated indexes unless the user explicitly asks.
- Avoid writing raw logs, large binary references, or transient build output into notes; link to source artifact paths instead.

## AI Superbody and Cyrus Knowledge

- AI Superbody updates should preserve PMO-style owner, blocker, next-action, and validation-state structure.
- Cyrus Knowledge updates should preserve the learning-system framing and connect notes back to concrete tasks, evidence, and review outputs.

## Expected validation

- After editing notes, verify changed Markdown files render as readable plain Markdown.
- For generated or synchronized notes, ensure repeated runs will not overwrite unrelated user edits.
- For cross-linked notes, check that referenced paths or wiki links are spelled consistently.
```

- [ ] **Step 3: Verify the new file contains conservative edit rules**

Run:

```bash
rg -n "long-lived personal knowledge base|Do not bulk-reformat|source paths or links" "/Users/cyber/Documents/Obsidian Vault/AGENTS.md"
```

Expected output includes three matching lines.

## Task 5: Final Validation And Reporting

**Files:**
- Read: `/Users/cyber/.codex/AGENTS.md`
- Read: `/Users/cyber/Documents/zmf_terminal/AGENTS.md`
- Read: `/Users/cyber/Documents/Obsidian Vault/AGENTS.md`
- Read: `/Users/cyber/Documents/zmf_ws`

- [ ] **Step 1: Validate all target instruction files**

Run:

```bash
test -f /Users/cyber/.codex/AGENTS.md && test ! -L /Users/cyber/.codex/AGENTS.md && echo global-ok
test -f /Users/cyber/Documents/zmf_terminal/AGENTS.md && echo zmf-terminal-ok
test -f "/Users/cyber/Documents/Obsidian Vault/AGENTS.md" && echo obsidian-vault-ok
```

Expected output:

```text
global-ok
zmf-terminal-ok
obsidian-vault-ok
```

- [ ] **Step 2: Confirm `zmf_ws` runtime files remain untouched**

Run:

```bash
git -C /Users/cyber/Documents/zmf_ws status --short --branch
```

Expected output shape:

```text
## main...origin/main [ahead N]
?? docs/superpowers/plans/2026-05-13-workspace-agent-instruction-unification.md
```

If the plan file has been committed before execution, the output may only show the branch line. There must be no runtime file modifications from this instruction cleanup.

- [ ] **Step 3: Confirm the global file routes to local workspace rules**

Run:

```bash
rg -n "Active workspace routing|zmf_ws|zmf_test-data|Cyrus-Learning-Manager|Obsidian Vault" /Users/cyber/.codex/AGENTS.md
```

Expected output includes the active routing section and entries for the listed workspaces.

- [ ] **Step 4: Report the result**

Final response should include:

```text
Changed:
- Replaced /Users/cyber/.codex/AGENTS.md symlink with workspace-neutral global guidance.
- Added /Users/cyber/Documents/zmf_terminal/AGENTS.md.
- Added /Users/cyber/Documents/Obsidian Vault/AGENTS.md.

Validated:
- ~/.codex/AGENTS.md is now a regular file.
- Global guidance no longer contains PIX-only runtime commands as defaults.
- zmf_ws runtime files were not touched.

Notes:
- Existing project-specific AGENTS files and repo-local skills were preserved.
```

## Self-Review

Spec coverage:

- Global symlink replacement is covered by Task 2.
- `zmf_terminal` guidance is covered by Task 3.
- `Obsidian Vault` guidance is covered by Task 4.
- Dirty worktree and runtime-file protection are covered by Tasks 1 and 5.
- Project-specific guidance preservation is covered by the file structure and validation tasks.

Placeholder scan:

- Placeholder scan passed. The plan contains concrete target files, exact file contents, exact commands, and expected outputs.

Type and path consistency:

- `/Users/cyber/.codex/AGENTS.md`, `/Users/cyber/Documents/zmf_terminal/AGENTS.md`, and `/Users/cyber/Documents/Obsidian Vault/AGENTS.md` are used consistently across all tasks.
