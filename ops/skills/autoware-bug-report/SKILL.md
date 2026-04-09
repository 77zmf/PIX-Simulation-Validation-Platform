---
name: autoware-bug-report
description: Use this skill when field-test findings, logs, bags, version data, or现场描述 must be turned into a structured Autoware bug report, GitHub issue draft, or reproducible engineer handoff.
---

# Purpose
Turn messy test evidence into a reproducible, engineer-friendly issue package.

# When to use
Use this skill when the task includes one or more of:
- on-road / on-vehicle phenomenon description
- timestamped abnormal event
- rosbag or log references
- branch / tag / commit / version references
- need to create a GitHub issue draft
- need to hand off a bug to perception / planning / control / localization engineers

# When not to use
Do not use this skill for:
- release checklist generation
- CARLA case creation
- generic code debugging without field evidence
- documentation-only work

# Required output structure
Always produce these sections unless data is missing:
1. Title
2. Phenomenon / symptom
3. Expected behavior
4. Actual behavior
5. Reproduction conditions
6. Time / vehicle / map / environment
7. Software version
8. Evidence attached
9. Suspected module / ownership
10. Severity / impact
11. Recommended next action

# Operating rules
- Preserve exact timestamps, version strings, and vehicle IDs.
- Separate facts from hypotheses.
- If ownership is uncertain, provide primary and secondary suspect.
- If logs mention frequency drops, timeout, MRM, emergency stop, degraded mode, or emergency braking, call that out explicitly.
- If bag slicing is requested but raw bag is not available, generate a slicing plan instead of pretending it was done.
- Prefer GitHub-ready Markdown when the user is likely to paste the result into an issue.

# Default issue title patterns
- [Bug] <module>: <short symptom>
- [Regression] <module>: <behavior changed after update>
- [Runtime] <module>: <failure under scenario>
- [Simulation] <module>: <abnormal behavior in case>

# Companion references
See `references/issue-template.md` for a default issue body.
