---
name: repo-verification
description: Use when a task changes Python code, CLI behavior, tests, scenarios, evaluation gates, assets manifests, workflow files, or ops automation. This skill runs the repository's standard verification stack and reports exactly what passed, failed, or remained stub.
---

# Repo verification

Use this skill for any change that could affect the validation control plane or repository automation.

## Goal
Prove whether a code or config change keeps the repo healthy on a non-runtime machine.

## Standard procedure
1. Confirm the changed paths and decide whether they touch runtime-facing code or only docs.
2. For docs-only changes, explain why the full stack is unnecessary.
3. For code, config, workflow, scenario, evaluation, asset-manifest, or ops changes, run the deterministic verification script:

```bash
bash .agents/skills/repo-verification/scripts/run_checks.sh
```

4. Read the generated outputs under `ci_runs/`, `ci_digest/`, and the test logs.
5. In the final answer, state:
   - what changed
   - which commands ran
   - which artifacts were generated
   - whether the change is still stub-only or affects real runtime paths
   - what remains unverified on the company Ubuntu runtime host

## Output requirements
Always include:
- changed file groups
- verification commands actually run
- pass/fail status
- missing coverage or runtime-only gaps
- exact rollback or follow-up steps

## Boundaries
- This skill is for repo verification, not for real vehicle or live simulator control.
- Keep stable mainline and shadow/research discussion explicitly separated.
