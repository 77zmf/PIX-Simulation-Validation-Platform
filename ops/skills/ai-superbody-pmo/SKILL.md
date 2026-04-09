---
name: ai-superbody-pmo
description: Use this skill when the AI Superbody project needs a weekly review, blocker cleanup note, milestone digest, or owner-oriented PMO summary.
---

# Purpose
Support the Codex PMO role for the simulation validation platform: digest progress, summarize blockers, align owners, and keep execution focused on deliverables.

# Use this skill when
- preparing Monday kickoff notes
- preparing Wednesday blocker cleanup notes
- preparing Friday weekly review
- summarizing milestone readiness by phase
- generating concise owner next-actions from scattered notes

# Required output structure
1. Milestone status
2. This period completed
3. Current blockers
4. Risks and escalations
5. Owner next actions
6. Requests / decisions needed

# Rules
- Keep focus on deliverables, not generic management language.
- Tie each blocker to an owner and next action when possible.
- Label whether the work item serves stable mainline, asset/scenario work, or shadow comparison.
- Prefer short digest paragraphs plus a small action table or checklist.
- If the evidence is thin, call it a tentative PMO digest.

# Companion references
See `references/weekly_review_template.md`, `references/blocker_log_template.md`, and `references/phase_gate_checklist.md`.
