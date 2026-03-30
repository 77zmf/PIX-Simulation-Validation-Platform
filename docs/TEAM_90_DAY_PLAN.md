# Team 90-Day Plan

## Quarter Goal

Build a reusable simulation validation baseline around:

- `Autoware Universe main`
- `ROS 2 Humble`
- `CARLA 0.9.15`
- `UE4.26`

By the end of the quarter, the team should have:

- one repeatable stable closed-loop path
- one working automation data loop
- one standardized public-road asset bundle
- one E2E shadow research path running on the same CARLA 0.9.15 baseline

## Phase Breakdown

### Weeks 1-4

- Ubuntu host bring-up
- ROS 2 / Autoware workspace preparation
- CARLA 0.9.15 runtime verification
- first L0 smoke result

### Weeks 5-8

- repeatable `run_result -> report -> replay`
- L0/L1 regression templates
- KPI gates and report format

### Weeks 9-12

- public-road asset normalization
- Top 5 corner cases
- BEVFusion / UniAD-style / VADv2 shadow comparison on CARLA 0.9.15

## Ownership

- `Zhu Minfeng`: stable stack, host bring-up, control plane, quarter gate
- `Luo Shunxiong / lsx`: assets, map/pointcloud inputs, corner cases
- `Yang Zhipeng`: BEVFusion baseline and E2E shadow research
- `Codex PMO`: digest, weekly prep, blocker tracking
