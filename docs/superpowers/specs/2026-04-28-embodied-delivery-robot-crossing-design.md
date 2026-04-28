# Embodied Delivery Robot Crossing Design

## Objective

Add a first embodied-intelligence simulation case to the PIX Simulation Validation Platform without changing the stable acceptance line.

The first case is an L2 CARLA Town01 shadow/research scenario where an embodied low-speed delivery robot crosses the ego route from an occluded area. The validation should check both sides of the interaction:

- the ego vehicle yields or avoids safely
- the delivery robot completes its crossing task without collision or deadlock

This is a research/shadow extension. It must not be reported as stable closed-loop acceptance unless the normal Ubuntu-host chain also produces final runtime evidence, KPI gate output, report, and replay.

## Scope

In scope:

- CARLA 0.9.15 / Town01 only
- delivery robot represented by an existing CARLA small four-wheel vehicle blueprint
- scripted plus reactive robot policy
- runtime probe that spawns and controls the robot
- scenario YAML, adapter profile, KPI gate, runtime evidence folding, and focused tests
- output through the existing `simctl run -> validate -> finalize -> report` chain

Out of scope for this first version:

- custom Unreal/CARLA delivery robot blueprint authoring
- Isaac Sim, MuJoCo, Habitat, Genesis, or another simulator runtime
- learned VLA/RL policy inference
- direct production control takeover
- public-road `site_gy_qyhx_gsh20260310` migration

## Architecture

The feature should extend the existing runtime-probe pattern instead of introducing a new stack.

New scenario:

- `scenarios/l2/embodied_delivery_robot_occluded_crossing.yaml`

New adapter profile:

- `adapters/profiles/embodied_delivery_robot_shadow.yaml`

New KPI gate:

- `evaluation/kpi_gates/embodied_delivery_robot_crossing_gate.yaml`

New runtime probe:

- `ops/runtime_probes/carla_embodied_agent_probe.py`

Evidence integration:

- extend `src/simctl/runtime_evidence.py` so `simctl finalize` can collect embodied probe JSON artifacts from `runtime_verification/`

Tests:

- extend `tests/test_runtime_evidence.py` with a synthetic embodied probe artifact
- add probe serialization tests if the probe grows dedicated helper functions

## Scenario Contract

The scenario should follow existing `ScenarioConfig` fields and add embodied-agent details under metadata or execution config without changing the base schema first.

Recommended scenario shape:

```yaml
scenario_id: embodied_delivery_robot_occluded_crossing
stack: stable
map_id: Town01
asset_bundle: carla_town01
ego_init:
  pose:
    x: 229.7817
    y: -2.0201
    z: 0.0
    yaw_deg: 0.0
goal:
  pose:
    x: 314.2435
    y: -1.9826
    z: 0.0
    yaw_deg: 0.0
traffic_profile:
  mode: embodied_delivery_robot_crossing
  vehicles: 1
  pedestrians: 0
weather_profile:
  preset: ClearNoon
sensor_profile: robobus_pixrover14_application_topology
algorithm_profile: embodied_delivery_robot_shadow
kpi_gate: embodied_delivery_robot_crossing_gate
metadata:
  validation_command: >
    python3 ops/runtime_probes/carla_embodied_agent_probe.py
    --run-dir <run_dir>
    --carla-port <carla_rpc_port>
    --robot-blueprint-filter vehicle.*
    --policy scripted_reactive_crossing
```

The exact Town01 spawn points should be calibrated during implementation against an executable CARLA instance. Until then, the scenario is a repo-local contract and not proof of runtime acceptance.

## Runtime Probe Behavior

The probe controls a robot-like vehicle actor:

1. Connect to CARLA on the selected slot port.
2. Spawn a small vehicle blueprint near an occlusion/crossing area.
3. Move the robot along a crossing route.
4. Apply reactive behavior:
   - slow down or pause when ego distance/TTC is unsafe
   - continue when the crossing window is safe
5. Sample ego and robot states at a fixed tick rate.
6. Record collision, TTC, route progress, yield events, pauses, and deadlock conditions.
7. Write one JSON artifact under `runtime_verification/`.

The probe should be deterministic for the same seed and scenario parameters.

## Evidence Contract

The runtime probe should write JSON with this minimum structure:

```json
{
  "kind": "embodied_delivery_robot_probe",
  "scenario_id": "embodied_delivery_robot_occluded_crossing",
  "profile": "scripted_reactive_crossing",
  "overall_passed": true,
  "summary": {
    "ego_yield_success": true,
    "robot_policy_success": true,
    "robot_route_completion": 1.0,
    "collision_count": 0,
    "min_ttc_sec": 2.1,
    "interaction_deadlock": false
  },
  "metrics": {
    "ego_yield_success": 1.0,
    "robot_policy_success": 1.0,
    "robot_route_completion": 1.0,
    "collision_count": 0.0,
    "min_ttc_sec": 2.1,
    "interaction_deadlock": 0.0
  },
  "artifacts": {
    "samples": "runtime_verification/embodied_delivery_robot_samples.jsonl"
  }
}
```

`simctl finalize` should fold the latest valid embodied artifact into `runtime_evidence.metrics`, with `metric_sources` set to `runtime_embodied_agent_probe`.

## KPI Gate

Initial gate:

```yaml
gate_id: embodied_delivery_robot_crossing_gate
description: Shadow gate for embodied delivery robot crossing interaction
failure_labels:
  - embodied_robot_collision
  - embodied_robot_deadlock
  - embodied_robot_task_failure
  - ego_yield_failure
metrics:
  collision_count:
    op: "<="
    value: 0
  min_ttc_sec:
    op: ">="
    value: 1.8
  ego_yield_success:
    op: ">="
    value: 1
  robot_route_completion:
    op: ">="
    value: 0.95
  robot_policy_success:
    op: ">="
    value: 1
  interaction_deadlock:
    op: "<="
    value: 0
```

This gate is a shadow/research gate. It should not be used to claim stable acceptance.

## Data Flow

Expected command chain:

```bash
simctl run --scenario scenarios/l2/embodied_delivery_robot_occluded_crossing.yaml --run-root runs --slot stable-slot-01 --execute
simctl validate --run-dir runs/<run_id> --execute --finalize --report
simctl replay --run-result runs/<run_id>/run_result.json
```

Flow:

1. `simctl run` creates the run directory and starts the stable stack.
2. `simctl validate` runs the scenario validation command.
3. The runtime probe writes embodied evidence JSON.
4. `simctl finalize` folds metrics into `run_result.json`.
5. `simctl report` shows the shadow/research result.
6. Replay remains based on the normal run artifacts.

## Error Handling

The probe should fail clearly when:

- CARLA Python API is unavailable
- CARLA RPC cannot be reached
- ego actor is missing
- no usable vehicle blueprint exists for the robot
- robot spawn fails
- the probe produces no samples

These failures should be encoded as runtime evidence when possible and should result in a failed KPI gate rather than a silent pass.

## Validation

Repo-local validation:

```bash
PYTHONPATH=src python3 -m unittest tests.test_runtime_evidence -v
PYTHONPATH=src python3 -m simctl --repo-root . run --scenario scenarios/l0/smoke_stub.yaml --run-root /tmp/embodied_shadow_smoke
PYTHONPATH=src python3 -m simctl --repo-root . report --run-root /tmp/embodied_shadow_smoke
```

Ubuntu-host validation:

```bash
simctl run --scenario scenarios/l2/embodied_delivery_robot_occluded_crossing.yaml --run-root runs --slot stable-slot-01 --execute
simctl validate --run-dir runs/<run_id> --execute --finalize --report
```

Mac/local validation only proves schema, evidence folding, and reporting behavior. It does not prove CARLA closed-loop acceptance.

## Risks And Rollback

Risks:

- existing CARLA vehicle blueprints may not visually resemble a delivery robot
- Town01 spawn points may need calibration on the Ubuntu host
- ego yield detection may need tuning to avoid false positives
- probe failures could be misread as stable stack failures if reporting is not clearly labeled as shadow/research

Rollback:

- remove the scenario from campaigns
- keep the probe unused
- do not include the new KPI gate in stable acceptance reports

