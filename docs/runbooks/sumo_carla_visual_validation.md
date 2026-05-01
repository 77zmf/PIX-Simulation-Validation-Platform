# SUMO-CARLA Visual Validation Runbook

## Objective

Capture repeatable visual evidence that SUMO traffic actors are synchronized into CARLA and visible alongside the PIX ego vehicle in the stable validation stack.

This visual evidence path is now part of the formal `stable_l1_sumo_town01_traffic_smoke` validation chain. It does not replace the SUMO KPI gate or make SUMO a standalone simulator runtime.

## Runtime Host

- Host: company Ubuntu 22.04 runtime host
- Stack: `stable`
- CARLA: `0.9.15`
- Scenario: `scenarios/l1/sumo_town01_traffic_smoke.yaml`
- Required process cleanup: always run `simctl down` for the same run directory after capture.

## Standard Command

Preferred path: run the scenario, then use `simctl validate` so the scenario metadata launches the visual probe automatically:

```bash
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

python3 -m simctl.cli run \
  --scenario scenarios/l1/sumo_town01_traffic_smoke.yaml \
  --run-root runs \
  --slot stable-slot-01 \
  --execute

python3 -m simctl.cli validate \
  --run-dir <run_dir> \
  --execute \
  --finalize \
  --report
```

For operator-visible co-simulation, enable all three desktop views before `simctl run`:

```bash
export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority
export SIMCTL_CARLA_RENDER_MODE=visual
export SIMCTL_CARLA_RES_X=960
export SIMCTL_CARLA_RES_Y=540
export SIMCTL_CARLA_DISPLAY=:0
export SIMCTL_CARLA_XAUTHORITY=/run/user/1000/gdm/Xauthority
export SIMCTL_SUMO_GUI=true
export SIMCTL_AUTOWARE_RVIZ=true
export SIMCTL_AUTOWARE_RVIZ_CONFIG=/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware/install/autoware_launch/share/autoware_launch/rviz/planning_bev.rviz
export SIMCTL_VISUAL_SCREENSHOT_WAIT_SEC=12
```

This keeps the scenario and KPI gate unchanged but makes the startup screenshot include the Autoware planning/control RViz view when the desktop session is available.

Manual probe invocation remains useful for isolated debugging:

```bash
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

python3 ops/runtime_probes/carla_actor_visual_capture.py \
  --run-dir <run_dir> \
  --profile town01_sumo_visual_smoke \
  --carla-root /home/pixmoving/CARLA_0.9.15 \
  --carla-port 2000 \
  --ego-role-name ego_vehicle \
  --npc-role-name sumo_driver \
  --npc-role-prefix sumo \
  --min-npcs 1 \
  --min-captures 3 \
  --max-npcs 3 \
  --image-width 960 \
  --image-height 540 \
  --worker-timeout-sec 220

python3 -m simctl.cli validate \
  --run-dir <run_dir> \
  --execute \
  --finalize \
  --report
```

## Expected Evidence

The visual probe writes:

- `<run_dir>/screenshots/visual_startup.png`
- `<run_dir>/screenshots/visual_startup.json`
- `<run_dir>/screenshots/carla_actor_visual_<timestamp>/npc_*_close.png`
- `<run_dir>/screenshots/carla_actor_visual_<timestamp>/npc_*_side.png`
- `<run_dir>/screenshots/carla_actor_visual_<timestamp>/npc_group_topdown_all_sumo_driver.png`
- `<run_dir>/runtime_verification/metric_probe_carla_actor_visual_<timestamp>/metric_probe_carla_actor_visual_<timestamp>.json`

The finalized `run_result.json` should include numeric metrics:

- `carla_actor_visual_vehicle_count`
- `carla_actor_visual_ego_seen`
- `carla_actor_visual_npc_count`
- `carla_actor_visual_capture_count`

## Acceptance Criteria

- CARLA visual evidence shows at least one non-ego `sumo_driver` actor.
- The finalized gate sees `carla_actor_visual_ego_seen=1.0`.
- The finalized gate sees `carla_actor_visual_npc_count>=1.0`.
- The finalized gate sees `carla_actor_visual_capture_count>=3.0`.
- The probe reports `overall_passed=true`.
- `simctl finalize` keeps the SUMO KPI gate result explainable as `passed` or `failed`.
- `simctl down --execute` clears CARLA, SUMO, Autoware, TraCI, and stack ports.

## Rollback

If the host must temporarily drop visual capture requirements, remove `carla_actor_visual_capture.py` from `scenarios/l1/sumo_town01_traffic_smoke.yaml` and delete the three visual metrics from `evaluation/kpi_gates/sumo_public_road_smoke.yaml`. Remove generated `screenshots/carla_actor_visual_*` and `runtime_verification/metric_probe_carla_actor_visual_*` directories if the run was only exploratory.
