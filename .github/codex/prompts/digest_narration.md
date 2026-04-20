Use the `pix-project-digest` skill.

Read:
- `automation_outputs/project_digest/digest.md`
- `automation_outputs/project_digest/digest_summary.json` if present
- `ops/project_automation.yaml`
- `AGENTS.md`
- `AGENTS.override.md`

Turn the existing project digest into a short operator-facing summary for the PIX Simulation Validation Platform.

Requirements:
- Start with the top blockers and owner next actions.
- Label items as stable validation, public-road asset/scenario work, shadow/research, or reconstruction support.
- Call out stale owner, due date, status, or evidence hygiene when it weakens digest quality.
- Mention the latest validation signal and whether it is stub-safe, dry-run, or real runtime-host evidence.
- End with the three most useful moves for the next work session.

Output format:
1. Weekly/daily status
2. Blockers
3. Owner next actions
4. Validation signal
5. Next three moves
