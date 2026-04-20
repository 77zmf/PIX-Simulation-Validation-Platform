Use the `repo-verification` skill.

Review this pull request for the PIX Simulation Validation Platform.
Focus on concrete correctness, regression risk, and whether the diff improves or weakens this chain:

`assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest`

Requirements:
- Prefer exact file references.
- Only raise issues that are supported by the diff or by repository rules.
- Say when the work is still stub-only versus real runtime-affecting.
- Call out missing validation commands if the diff touches runtime, CLI, workflows, scenarios, evaluation, assets, or ops.
- Do not ask for Notion or SMTP integration; current project automation is GitHub-only.

Output format:
1. Verdict
2. Major findings
3. Validation gaps
4. Suggested commands or artifacts to verify
5. Merge conditions
