---
name: autoware-release-check
description: Use this skill when the user asks whether the current Autoware-based workspace is ready for release, field test, build-workstation handoff, or OTA packaging.
---

# Purpose
Run a conservative release-readiness check for Autoware-based delivery workflows.

# Use this skill when
- preparing a daily or weekly test delivery build
- verifying branch / tag / dirty files before packaging
- summarizing release risk before handoff to another engineer or workstation
- comparing current workspace against a release anchor or baseline

# Required checks
1. current workspace identity
2. release anchor / baseline comparison
3. multi-repo consistency under `src/`
4. build-risk indicators
5. delivery and rollback readiness

# Required output
### Release verdict
### Workspace snapshot
### Risks
### Recommended actions
### Handoff summary

# Decision rules
Mark **Ready** only when branch/tag identity, rollback point, dirty state, and multi-repo status are all clear.
Mark **Conditionally ready** when the build is likely usable but there are record-or-cleanup actions left.
Mark **Not ready** when workspace identity, dirty state, baseline comparison, or multi-repo state is too unclear for a safe handoff.

# Style rules
- Be conservative.
- Do not say a build succeeded unless there is evidence.
- Prefer exact commands over vague advice.
- Prefer rollback clarity over speed.

# Companion references
See `references/release_checklist.md` and `scripts/collect_repo_status.sh`.
