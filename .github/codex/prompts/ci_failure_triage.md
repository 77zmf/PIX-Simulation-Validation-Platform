Use the `pix-run-result-triage`, `pix-host-readiness`, and `repo-verification` skills as relevant.

Read:
- `automation_outputs/ci_failure/run_metadata.md`
- `automation_outputs/ci_failure/failed_workflow.log`
- `AGENTS.md`
- `AGENTS.override.md`
- the workflow file that failed, when identifiable

Produce a concise CI failure triage for the PIX Simulation Validation Platform.

Requirements:
- Identify the failed workflow/run and the most likely failing step.
- Separate repo-code failures from runner, dependency, token, secret, or external-service failures.
- Say whether the failure affects the stable validation line, project automation, shadow/research work, or only CI hygiene.
- Include exact evidence lines or artifact paths.
- Give the smallest next action, likely owner, and verification command.
- If the failure is from stub-only CI, do not imply real Ubuntu runtime-host validation failed.

Output format:
1. Failure summary
2. Evidence
3. Likely root cause
4. Impact
5. Owner next action
6. Verification
