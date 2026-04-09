---
name: carla-case-builder
description: Use this skill when a CARLA or public-road replay case must be created from lanelet2, pointcloud, metadata, problem records, or corner-case ideas.
---

# Purpose
Turn map assets, field issues, and regression intentions into a reusable simulation or replay case package.

# When to use
- building a new CARLA / replay validation case
- turning public-road issue evidence into a regression scenario
- standardizing asset-bundle metadata for a site
- defining success criteria, replay method, and owner for a case

# Required output structure
1. Case objective
2. Related source issue or scenario motivation
3. Asset bundle inputs
4. Scenario assumptions
5. Ego initial condition
6. Dynamic actor and environment assumptions
7. Success criteria and KPI hooks
8. Replay / evaluation method
9. Risks and missing inputs
10. Owner and next action

# Operating rules
- Reuse existing asset bundles before proposing brand-new maps.
- Prefer stable-line validation first; label shadow-only cases clearly.
- If exact actor trajectories are unknown, describe them as assumptions and placeholders.
- If the case comes from a field issue, preserve time anchor, map section, and observable symptom.
- Always note whether the case belongs to L0 smoke, L1 regression, public-road replay, or shadow comparison.

# Companion references
See `references/asset_bundle_template.md`, `references/scenario_template.yaml`, and `references/case_checklist.md`.
