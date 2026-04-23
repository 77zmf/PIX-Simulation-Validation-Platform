# Lidar Calibration Validation

## Objective

Validate the Robobus117th five-lidar automatic extrinsic calibration flow as a
stable-candidate scenario. The external calibration program is the system under
test; `simctl` provides traceability, sensor-topic evidence, KPI evaluation, and
report/replay closure.

## Assets

- Truth, evaluator-only: `assets/calibration/lidar_sensor_kit_truth.yaml`
- Initial guess, calibration-program input: `assets/calibration/lidar_sensor_kit_initial_perturbed.yaml`
- Runtime scenario: `scenarios/calibration/lidar_sensor_kit_extrinsic.yaml`
- Video-derived workshop proxy: `scenarios/calibration/lidar_workshop_bv1qk411d7ta.yaml`
- Workshop scene asset: `assets/calibration/calibration_workshop_bv1qk411d7ta_scene.yaml`
- Imported board asset: `assets/calibration/boards/single_qr_fiducial_board.yaml`
- Workshop scene spawner: `stack/stable/carla_calibration_scene_spawner.py`
- KPI gate: `evaluation/kpi_gates/lidar_sensor_kit_extrinsic.yaml`
- Camera board detector: `ops/runtime_probes/camera_fiducial_board_opencv_probe.py`
- Lidar board-hit detector: `ops/runtime_probes/lidar_fiducial_board_hit_probe.py`
- Metric adapter: `ops/runtime_probes/lidar_calibration_metric_probe.py`

The calibration program must not read the truth asset. It should consume the
initial guess plus lidar pointcloud data and write:

```json
{
  "calibration_type": "lidar_sensor_kit_extrinsic",
  "status": "converged",
  "estimated_transforms": [
    {
      "parent": "sensor_kit_base_link",
      "child": "lidar_ft_base_link",
      "translation_m": [2.459, -0.023, 1.846],
      "rotation_rpy_rad": [0.013, 0.009, 0.012]
    }
  ],
  "metrics": {
    "lidar_extrinsic_translation_error_m": 0.018,
    "lidar_extrinsic_rotation_error_deg": 0.22,
    "lidar_pairwise_registration_rmse_m": 0.032
  }
}
```

Expected path:

```text
<run_dir>/runtime_verification/calibration/lidar_sensor_kit_extrinsic/calibration_result.json
```

## Scene Isolation

Calibration scenarios are calibration-only captures. They must not share the
same CARLA anchor or road segment used by L0/L1/L2 planning-control regression
tests.

The current proxy anchor is:

```text
carla_spawn_point="13.5686,330.4619,-0.5,0,0,0"
```

The driving-regression anchor remains:

```text
carla_spawn_point="229.7817,2.0201,-0.5,0,0,0"
```

The required separation is at least `250 m` from the listed driving-test
scenario anchors. Because the workshop board layout is spawned relative to the
ego vehicle, moving the ego anchor isolates the full calibration bay. Do not add
calibration scenarios to planning-control campaigns such as
`ops/test_campaigns/stable_perception_control.yaml`.

## Local Dry Run

```bash
simctl run --scenario scenarios/calibration/lidar_sensor_kit_extrinsic.yaml --run-root runs --mock-result passed
simctl report --run-root runs
```

This only verifies the control-plane contract and KPI schema. It is not stable
closed-loop acceptance.

For the Bilibili calibration-workshop proxy scene:

```bash
simctl run --scenario scenarios/calibration/lidar_workshop_bv1qk411d7ta.yaml --run-root runs --mock-result passed
simctl report --run-root runs
```

This scenario is traceable to `https://www.bilibili.com/video/BV1qK411D7TA/`
and records the source title, publisher, and date in metadata. It is a proxy
layout until measured target positions, indoor-map geometry, and CARLA/UE
textured calibration-target assets are imported. The current proxy uses twelve
dimensioned single-QR calibration panels around the vehicle: front/rear rails,
left/right side stands, and four angled corner stands. Each panel is modeled as
a `1.6 m x 1.6 m` rigid matte board with a `1.05 m` QR print, frame, thickness,
and either weighted floor stands or rail mounting. Each board has exactly one QR
payload, generated from the target id with the `PXC:{target_id}` template.
CARLA renders this as a static prop plus debug-overlay panel frame, stand/rail,
and QR marker pattern when `--debug-draw` is enabled.
The colleague calibration program reference remains
`https://github.com/pixmoving-moveit/camera_to_lidar_autoCalib`, but that
repository currently uses an AprilTag16h5 detector, so native consumption of
these QR boards needs a QR detector adapter.

To inspect the CARLA spawn plan without a running simulator:

```bash
python3 stack/stable/carla_calibration_scene_spawner.py \
  --run-dir /tmp/lidar_workshop_scene_plan \
  --scene-file assets/calibration/calibration_workshop_bv1qk411d7ta_scene.yaml \
  --dry-run
```

On the Ubuntu runtime host, after CARLA and the ego vehicle are up, spawn the
workshop proxy targets:

```bash
python3 stack/stable/carla_calibration_scene_spawner.py \
  --run-dir <run_dir> \
  --scene-file assets/calibration/calibration_workshop_bv1qk411d7ta_scene.yaml \
  --carla-port 2000 \
  --ego-vehicle-role-name ego_vehicle \
  --delete-existing \
  --debug-draw
```

Then verify that CARLA lidar rays hit the QR-board surfaces:

```bash
python3 ops/runtime_probes/lidar_fiducial_board_hit_probe.py \
  --run-dir <run_dir> \
  --scene-spawn-artifact <run_dir>/runtime_verification/calibration_scene/calibration_workshop_bv1qk411d7ta_scene_spawn.json \
  --sensor-calibration assets/calibration/lidar_sensor_kit_truth.yaml \
  --capture-from-carla \
  --carla-port 2000 \
  --ego-vehicle-role-name ego_vehicle \
  --lidar-frame-count 5 \
  --min-boards-hit 3 \
  --min-lidars-hit 3 \
  --min-total-hit-count 100
```

This writes a metric-probe artifact under:

```text
<run_dir>/runtime_verification/metric_probe_lidar_fiducial_board_hits_*/lidar_fiducial_board_hits.json
```

Then verify that camera evidence can see fiducial boards through OpenCV:

```bash
python3 ops/runtime_probes/camera_fiducial_board_opencv_probe.py \
  --run-dir <run_dir> \
  --capture-from-carla \
  --carla-port 2000 \
  --ego-vehicle-role-name ego_vehicle \
  --expected-board-count 12 \
  --min-detections 1
```

The detector writes:

```text
<run_dir>/runtime_verification/calibration/camera_fiducial_board_detection/detection_result.json
```

Then project the saved lidar board-hit samples onto the captured camera images:

```bash
python3 ops/runtime_probes/lidar_camera_projection_probe.py \
  --run-dir <run_dir> \
  --scene-spawn-artifact <run_dir>/runtime_verification/calibration_scene/calibration_workshop_bv1qk411d7ta_scene_spawn.json \
  --image-dir <run_dir>/runtime_verification/calibration/camera_fiducial_board_detection/images \
  --min-in-frame-count 20 \
  --min-projected-views 1
```

This writes projection images and a metric-probe JSON under:

```text
<run_dir>/runtime_verification/metric_probe_lidar_camera_projection_*/
```

## Ubuntu Runtime Validation

```bash
simctl run \
  --scenario scenarios/calibration/lidar_sensor_kit_extrinsic.yaml \
  --run-root runs \
  --slot stable-slot-01 \
  --execute
```

After the external calibration program writes `calibration_result.json`, run:

```bash
simctl validate --run-dir <run_dir> --execute --finalize
simctl report --run-root runs
```

To run the video-derived workshop proxy instead, replace the scenario path with:

```text
scenarios/calibration/lidar_workshop_bv1qk411d7ta.yaml
```

## Gate

The gate requires:

- `calibration_converged == 1.0`
- `calibrated_lidar_count >= 5.0`
- `lidar_extrinsic_translation_error_m <= 0.05`
- `lidar_extrinsic_rotation_error_deg <= 0.5`
- `lidar_pairwise_registration_rmse_m <= 0.08`
- `sensor_topic_coverage >= 1.0`
- `sensor_sample_coverage >= 1.0`

## Runtime Gaps

- The current repository does not include the colleague's calibration program.
- CARLA bridge behavior for `robobus117th_objects.json` versus the five-lidar
  sensor mapping still needs confirmation on the Ubuntu host.
- The Bilibili-derived workshop scene is a proxy. Exact target dimensions,
  printed single-QR board materials, surveyed panel-corner coordinates, and
  indoor lighting still need measured evidence before it can become a
  physical-fidelity case.
- The OpenCV probe can use ArUco/QR detection plus a binary fiducial fallback.
  A real production acceptance run should prefer textured board assets over
  debug overlay markers.
- On the current Ubuntu host, OpenCV 4.5.4 detects generated QR corners but is
  not linked with QUIRC, so QR payload text decoding is unavailable until the
  OpenCV build or board-texture path is updated.
- The lidar board-hit probe can run in `--capture-from-carla` mode and capture
  CARLA `sensor.lidar.ray_cast` pointclouds from the configured five-lidar
  extrinsics, then count points that land inside each board ROI. Closed-loop
  acceptance still needs live ROS topic samples or a rosbag from the bridge.
- Mac/local validation must not be reported as stable closed-loop acceptance.

## Rollback

Exclude `scenarios/calibration/lidar_sensor_kit_extrinsic.yaml` from campaigns.
The scenario, assets, gate, and metric probe do not modify existing CARLA bridge
mapping or planning-control scenarios.
