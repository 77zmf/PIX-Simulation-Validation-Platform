# Planning/Control Bughunt Automation

This runbook defines the stable-line process for finding Autoware planning/control bugs with CARLA scenarios and handing evidence to development owners. The test flow must not patch planning/control code.

## Objective

Automatically run scenario regressions, finalize KPI evidence, generate reports, and create GitHub-ready Markdown bug drafts for planning/control failures.

## Runtime Host

Run this only on the company Ubuntu 22.04 host. Mac/local runs can validate schemas and dry-run plans, but they are not stable closed-loop acceptance.

## Command

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
export PYTHONPATH=src
python3 -m simctl.cli campaign \
  --config ops/test_campaigns/stable_planning_control_bughunt.yaml \
  --slot stable-slot-01 \
  --execute \
  --keep-going
```

The campaign writes:

- `runs/campaign_stable_planning_control_bughunt/campaign_result.json`
- `runs/campaign_stable_planning_control_bughunt/report/report.md`
- `runs/campaign_stable_planning_control_bughunt/bugpack/summary.json`
- `runs/campaign_stable_planning_control_bughunt/bugpack/index.md`
- `runs/campaign_stable_planning_control_bughunt/bugpack/issues/*.md`

The default campaign uses `stop_after_each: true` and `cooldown_sec: 60` so CARLA/Autoware processes have time to exit and host load can drop before the next scenario starts.

## Manual Bugpack Regeneration

If a campaign already exists, regenerate only the issue handoff package:

```bash
python3 -m simctl.cli bugpack \
  --run-root runs/campaign_stable_planning_control_bughunt \
  --output-dir runs/campaign_stable_planning_control_bughunt/bugpack \
  --owner planning-control
```

Use `--include-infra` only when runtime or actor-bridge blockers should also become issue drafts. By default, bugpack creates issue drafts only for planning/control KPI failures.

## Vehicle And Speed40 Prechecks

Before treating a speed or route-follow failure as an Autoware planning/control bug, run the low-level vehicle checks:

```bash
python3 ops/runtime_probes/carla_vehicle_blueprint_probe.py \
  --run-dir <run_dir> \
  --profile robobus117th_vehicle_blueprint

python3 ops/runtime_probes/carla_vehicle_dynamics_probe.py \
  --run-dir <run_dir> \
  --profile robobus117th_vehicle_dynamics \
  --reset-pose \
  --throttle 0.9 \
  --throttle-duration-sec 12.0
```

Use `scenarios/l1/robobus117th_town01_speed40_probe.yaml` for the 40km/h regression. Its closed-loop probe records `max_speed_mps`, `max_speed_kph`, `target_speed_reached`, and `target_speed_deficit_mps`; a failure here is actionable only after the blueprint and direct-throttle probes pass in the same clean stack.

For vehicle-critical scenarios, set `execution.stable_runtime.carla_actor_health_check: "true"`. Default is off so legacy stable scenarios keep their current behavior; when enabled, `simctl run --execute` requires the CARLA Python API to see the configured `carla_vehicle_type` and `carla_ego_vehicle_role_name` before reporting launch health as passed. Owner is the stable runtime maintainer. Rollback is to remove that scenario key, which restores process/port/ROS-topic-only launch health.

## Triage Policy

- `passed` runs are recorded in `summary.json` but do not create issue drafts.
- `launch_submitted`, `planned`, or missing final KPI evidence is incomplete evidence, not a planning/control bug.
- `launch_failed` or failed runtime health is a runtime blocker unless `--include-infra` is set.
- KPI failures on route completion, TTC, collision, yielding, lateral/longitudinal error, jerk, or control command are planning/control bug candidates.
- Sensor topic, SUMO, or actor-count failures are integration blockers unless they directly produce planning/control KPI violations.

## Developer Handoff Contract

Each generated issue draft contains:

- symptom and failed KPI
- expected and actual behavior
- reproduction commands
- run id, scenario path, stack, map, vehicle/sensor profile
- software versions from `run_result.json`
- evidence paths for `run_result.json`, runtime evidence, health report, logs, screenshots, rosbag, and CARLA recorder when present
- suspected module and owner
- next action for the responsible developer

## Rollback

Disable the automation by removing or ignoring `ops/test_campaigns/stable_planning_control_bughunt.yaml`. Existing narrower campaigns remain available:

- `ops/test_campaigns/stable_perception_control.yaml`
- `ops/test_campaigns/stable_l3_occlusion.yaml`
- `ops/test_campaigns/stable_sumo_traffic.yaml`
