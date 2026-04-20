---
name: pix-public-road-case-builder
description: Use when turning public-road findings, CARLA assets, lanelet2 maps, point clouds, sensor catalogs, vehicle metadata, field-test notes, corner-case ideas, or replay evidence into traceable PIX scenario drafts, asset-intake checklists, KPI hooks, and validation-owner handoffs.
---

# PIX public-road case builder

Use this skill to standardize public-road evidence into reusable scenario or replay cases. Stable validation comes first; shadow/research cases must be labeled as such.

## Procedure

1. Identify the source:
   - field-test finding or issue
   - CARLA map or route
   - lanelet2 map
   - point cloud or reconstruction asset
   - sensor catalog or vehicle metadata
   - corner-case idea without assets yet
2. Check existing repo locations before creating anything new:
   - `assets/`
   - `scenarios/`
   - `docs/`
   - `evaluation/kpi_gates/`
   - `stack/profiles/`
3. Preserve traceability:
   - source asset path or external evidence pointer
   - owner
   - site or route section
   - time anchor when available
   - observed symptom
   - evaluation method
4. Choose the target lane:
   - L0 smoke
   - L1 regression
   - public-road replay
   - shadow comparison
   - reconstruction support
5. Define the validation hook:
   - scenario YAML path
   - profile
   - KPI gate or observable
   - replay/report artifact
   - rollback or exclusion condition

## Output

Use this structure:

1. Case objective
2. Source assets and evidence
3. Scenario draft
4. Ego initial condition
5. Actors and environment assumptions
6. KPI or observable
7. Replay/report plan
8. Missing inputs
9. Owner and next action

## Rules

- Reuse existing asset bundles and scenario structure where possible.
- If trajectories, maps, or sensor alignment are unknown, label them as assumptions or blockers.
- Do not let reconstruction or shadow comparison block the stable validation line.
- Every proposed scenario should have source assets, owner, evaluation method, and rollback/exclusion impact.
