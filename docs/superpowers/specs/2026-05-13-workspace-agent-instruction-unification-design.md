# Workspace Agent Instruction Unification Design

Date: 2026-05-13

## Objective

Create a safe first-round improvement for all active workspaces by separating global Codex collaboration rules from project-specific rules, then adding only the smallest missing workspace guidance needed to prevent cross-project instruction leakage.

## Scope

This design covers the active workspace set approved by the user:

- `/Users/cyber/.codex`
- `/Users/cyber/Documents/zmf_ws`
- `/Users/cyber/Documents/zmf_test-data`
- `/Users/cyber/Documents/zmf_ws_publish`
- `/Users/cyber/Documents/Cyrus-Learning-Manager`
- `/Users/cyber/Documents/zmf_terminal`
- `/Users/cyber/Documents/Obsidian Vault`

This first round does not cover every historical trusted project in `~/.codex/config.toml`.

## Current Evidence

The global file `/Users/cyber/.codex/AGENTS.md` is currently a symlink to `/Users/cyber/Documents/zmf_ws/AGENTS.md`. That makes PIX Simulation Validation Platform rules global by accident, including stable runtime, CARLA, `simctl`, and Ubuntu host expectations. Those rules are correct for `zmf_ws`, but incorrect for learning-system, road-test evidence, publication, and note-maintenance workspaces.

The active workspaces already differ by role:

- `zmf_ws` has project-specific PIX simulation instructions, `.codex/config.toml`, and repo-local PIX skills.
- `zmf_test-data` has road-test and vehicle-side instructions plus planning and OSS failcase skills.
- `zmf_ws_publish` mirrors PIX publication workflow instructions and skills.
- `Cyrus-Learning-Manager` has learning-system instructions and Cyrus-specific skills.
- `zmf_terminal` has no local `AGENTS.md` discovered.
- `Obsidian Vault` has no local `AGENTS.md` discovered.

The `zmf_ws` worktree currently has many unrelated runtime, reconstruction, test, and docs changes. This instruction cleanup must not stage, revert, or edit those unrelated files.

## Recommended Approach

Use a minimal unified global layer.

1. Replace the global symlink `/Users/cyber/.codex/AGENTS.md` with a real global guidance file.
2. Keep global guidance limited to cross-workspace collaboration rules.
3. Preserve existing project-specific `AGENTS.md`, `AGENTS.override.md`, `.codex/config.toml`, and `.agents/skills`.
4. Add lightweight `AGENTS.md` files only where active workspaces lack them: `zmf_terminal` and `Obsidian Vault`.
5. Defer skill restructuring and broad template rollout to later rounds.

## Alternatives Considered

### Option 1: Minimal unified layer

This is the recommended option. It fixes the highest-risk problem first: global PIX instruction leakage. It also keeps the change surface small and easy to review.

Tradeoff: it does not fully standardize every repo or skill in one pass.

### Option 2: Unified template plus repo patches

This would add a common template and update each workspace in the same pass.

Tradeoff: it gives stronger consistency but creates unnecessary risk in dirty worktrees, especially `zmf_ws`.

### Option 3: Full platformization

This would add or rewrite `AGENTS.md`, `.codex/config.toml`, `.agents/skills`, checklists, and templates across all active workspaces.

Tradeoff: it is the most complete, but it is too broad for a first pass and should be split into separate specs per workspace family.

## Design

### Global Codex guidance

The new `/Users/cyber/.codex/AGENTS.md` should be a real file, not a symlink. It should contain only portable rules:

- identify the current workspace before acting
- read and follow the nearest project `AGENTS.md` or `AGENTS.override.md`
- use relevant skills when a task matches their descriptions
- protect dirty worktrees and never revert unrelated user changes
- keep stable runtime, vehicle testing, learning-system, publication, and note-maintenance work separated
- state verification evidence before claiming completion
- prefer small, reversible edits

It must not include `simctl`, CARLA, Autoware stable-line, road-test vehicle, Cyrus learning, or Obsidian-specific commands as universal defaults.

### `zmf_ws`

No first-round edits are required. Its current repo-specific guidance should remain the source of truth for PIX simulation validation work.

If implementation discovers that `zmf_ws/AGENTS.md` and `zmf_ws/AGENTS.override.md` need clarification, that should be handled in a later repo-local spec because the worktree is already dirty.

### `zmf_test-data`

No first-round edits are required. Its existing `AGENTS.md` already captures road-test, vehicle-side, issue, evidence, and destructive-command safety rules.

The global layer should point agents back to this local guidance instead of importing road-test rules globally.

### `zmf_ws_publish`

No first-round edits are required. It already has project-specific instructions and repo-local skills for publication and share-bundle work.

The global layer should not infer that all workspaces are publication repos.

### `Cyrus-Learning-Manager`

No first-round edits are required. Its existing `AGENTS.md` and `.codex/config.toml` already describe the TypeScript, React, Express, SQLite, Obsidian, and Notion sync workflow.

The global layer should not override its npm-based verification workflow with PIX runtime commands.

### `zmf_terminal`

Add a small `AGENTS.md` if the directory exists. The file should say this workspace is for AI Superbody note maintenance, PMO synthesis, and document operations, not a runtime execution repo.

Its guidance should tell agents to use `zmf_ws` as the evidence/source layer when AI Superbody content depends on PIX simulation state, and to preserve the existing Obsidian vault structure.

### `Obsidian Vault`

Add a small `AGENTS.md` if the directory exists. The file should say this is a user knowledge vault and should be edited conservatively.

Its guidance should prevent accidental generated-content overwrites, require extending existing note structures, and distinguish source evidence from synthesized notes.

## Implementation Boundaries

The first implementation plan should modify only:

- `/Users/cyber/.codex/AGENTS.md`
- `/Users/cyber/Documents/zmf_terminal/AGENTS.md` if missing
- `/Users/cyber/Documents/Obsidian Vault/AGENTS.md` if missing

It should not modify:

- runtime code under `src/`, `stack/`, `scenarios/`, `assets/`, `evaluation/`, or `tests/`
- repo-local skills in `.agents/skills/`
- `.codex/config.toml` files
- existing dirty files unrelated to this instruction cleanup

## Validation

The implementation is valid when:

1. `~/.codex/AGENTS.md` is a regular file, not a symlink.
2. The global file no longer contains PIX-only rules as universal defaults.
3. Existing project-specific `AGENTS.md` files remain in place.
4. `zmf_terminal` has workspace guidance if the directory exists.
5. `Obsidian Vault` has workspace guidance if the directory exists.
6. `git -C /Users/cyber/Documents/zmf_ws status --short --branch` shows no runtime files newly touched by this cleanup.
7. Any staged or committed change is limited to this spec or the approved instruction files.

## Risk And Rollback

The main risk is over-broad global guidance that weakens project-specific rules. Keep the global file short and route domain decisions back to local workspace instructions.

Rollback is simple:

1. Restore the previous symlink only if a temporary emergency fallback is needed:

```bash
rm /Users/cyber/.codex/AGENTS.md
ln -s /Users/cyber/Documents/zmf_ws/AGENTS.md /Users/cyber/.codex/AGENTS.md
```

2. Remove the two new lightweight workspace guidance files if they cause unexpected behavior:

```bash
rm /Users/cyber/Documents/zmf_terminal/AGENTS.md
rm "/Users/cyber/Documents/Obsidian Vault/AGENTS.md"
```

The preferred rollback after this design is not to restore the symlink permanently, but to adjust the global file until it is truly workspace-neutral.
