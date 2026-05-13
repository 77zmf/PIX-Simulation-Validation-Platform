# Stable Validation Checklist

Formal stable validation requires the company Ubuntu 22.04 runtime host.

## Formal Evidence Chain

- [ ] Scenario selected.
- [ ] Runtime host recorded.
- [ ] Branch / tag / commit recorded.
- [ ] Run command recorded.
- [ ] `run_result.json` exists.
- [ ] KPI gate result exists.
- [ ] Report exists.
- [ ] Replay entry point exists.
- [ ] Digest exists or is explicitly not required.
- [ ] Artifact path recorded.
- [ ] Verdict recorded.
- [ ] Blocker recorded when not passed.
- [ ] Rollback or containment recorded.

## Runtime Baseline

- [ ] Ubuntu 22.04 host.
- [ ] ROS 2 Humble.
- [ ] Autoware Universe expected baseline.
- [ ] CARLA 0.9.15.
- [ ] UE4.26.
- [ ] Expected map and scenario assets present.
- [ ] Slot / process cleanup is known.

## Verdict Rules

- `passed`: final KPI meets acceptance.
- `failed`: KPI or observable fails.
- `blocked`: cannot run or a required dependency is missing.
- `draft`: docs, stub, or incomplete path only.
- `needs more evidence`: artifact chain is insufficient.

