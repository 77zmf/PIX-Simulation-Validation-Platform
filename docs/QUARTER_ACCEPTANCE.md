# Quarter Acceptance

This document defines what "done enough for this quarter" means.

## Must-Have Outcomes

### 1. Stable Closed Loop

- CARLA 0.9.15 starts on the company Ubuntu host
- `ROS 2 Humble`, Autoware workspace, and the CARLA interface are ready on the same host
- Autoware and the CARLA interface can be brought up through the established workflow
- at least one basic route can run as a repeatable minimal closed loop

### 2. Automation

- `simctl bootstrap --stack stable`
- `simctl up --stack stable`
- `simctl run --scenario ...`
- `simctl batch ...`
- `simctl replay --run-result ...`
- `simctl report --run-root ...`

All of the above must be usable and documented.

### 3. Public-Road Asset Standardization

- `gy_qyhx_gsh20260302` is represented as a standardized public-road asset bundle
- lanelet, projector info, and pointcloud tiles map cleanly into the asset manifest
- the first public-road scenario input path is defined

### 4. Team Delivery Discipline

- the Notion `Program Board` reflects actual task owners and statuses
- weekly review is in active use
- risks have owners and next actions

### 5. Next-Cycle Readiness

- UE5 remote host assumptions are documented
- public-road E2E shadow metrics are drafted
- the team can begin the next cycle without redesigning the experiment line
