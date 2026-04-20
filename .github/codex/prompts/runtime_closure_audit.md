Use the `runtime-closure-audit` skill.

Read the outputs under `automation_outputs/runtime_audit/` and audit whether the validation chain is truly closed.

Requirements:
- Identify which links are present and which are missing.
- Distinguish stub-safe evidence from real runtime-host evidence.
- Say whether this is a real closed loop, a launch/report loop, or only a stub validation path.
- Give the exact next code/config/action that would close the most important missing link.
- Mention rollback or containment advice if the gap could mislead the team.

Output format:
1. Current closure status
2. Present links
3. Missing links
4. Exact next step
5. Risk note
