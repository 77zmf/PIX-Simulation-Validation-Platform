# LIO-RF RGB Pointcloud SLAM Pose Prior for Reconstruction

## Objective

Add SLAM as an offline producer for the reconstruction line. The producer outputs a pose prior, registered pointcloud, and diagnostics that downstream `map refresh`, `static Gaussian`, and future `dynamic Gaussian` steps can consume.

This does not add SLAM to the stable real-time control loop.

## Repository Contract

Tracked entry points:

```text
adapters/profiles/reconstruction_fast_lio_slam_pose_prior.yaml
scenarios/l2/reconstruction_fast_lio_slam_pose_prior.yaml
evaluation/kpi_gates/reconstruction_slam_pose_prior_gate.yaml
```

Local LIO-RF checkout:

```text
external/liorf/
```

Producer outputs stay outside Git:

```text
/data/pix/reconstruction/runs/<run_id>/slam/
  liorf_trajectory.tum
  liorf_trajectory.csv
  GlobalMap.pcdrgb
  pointcloud_tiles_manifest.json
  pose_prior_manifest.json
  alignment_diagnostics.json
```

## Required Input

For the RGB pointcloud mapping path, record the compact source bag with:

```bash
bash ops/scripts/record_qiyu_reconstruction_capture.sh \
  --record \
  --out-root /data/pix/road_tests/qiyu_reconstruction_capture
```

When the bag must include the camera frames used by `color_pointscloud/orin` and the producer host can see all required LiDAR/IMU/GNSS topics, run:

```bash
bash ops/scripts/record_qiyu_reconstruction_capture.sh \
  --record \
  --capture-profile rgb-map-camera \
  --out-root /home/nvidia/pix/failcase_data_local/qiyu_reconstruction_capture
```

If the Orin camera publisher does not see the IPC LiDAR topics, record the mapping core on IPC and the two 3mm camera streams on Orin:

```bash
# IPC: LiDAR/IMU/GNSS to external disk
bash /tmp/record_qiyu_reconstruction_capture.sh \
  --record \
  --out-root /home/ipc/pix/failcase_data/117_rgb_map_capture \
  --front-lidar-frame lidar_ft_base_link \
  --rear-lidar-frame lidar_rt_base_link

# Orin: front/rear 3mm camera bag
bash /home/nvidia/pix/record_qiyu_reconstruction_capture.sh \
  --record \
  --capture-profile rgb-camera-only \
  --out-root /home/nvidia/pix/failcase_data_local/117_rgb_map_camera_capture
```

The default `rgb-map` capture profile is equivalent to:

```bash
ros2 bag record \
  -o ros2bag \
  --max-bag-size $((3*1024*1024*1024)) \
  /sensing/lidar/front_top/points \
  /sensing/lidar/rear_top/points \
  /sensing/imu/imu_data \
  /sensing/gnss/fix
```

During preflight the helper also samples `ros2 run tf2_ros tf2_echo base_link <lidar_frame>` for the front and rear LiDAR frames and writes:

```text
<run_id>/tf_extrinsics/
<run_id>/liorf_lidar_extrinsics_from_tf.yaml
```

Copy the generated `lidar_front_trans`, `lidar_front_rot`, `lidar_rear_trans`, and `lidar_rear_rot` values into the LIO-RF config before mapping. If the vehicle uses different frame names, pass `--front-lidar-frame`, `--rear-lidar-frame`, and `--base-frame`.

`rgb-map-camera` follows the `pixmoving-auto/color_pointscloud` `orin` config and adds only the two compressed camera streams used for RGB pointcloud generation:

- `/electronic_rearview_mirror/front_3mm/camera_image_jpeg`
- `/electronic_rearview_mirror/rear_3mm/camera_image_jpeg`
- `/sensing/camera/front_3mm/camera_info`
- `/sensing/camera/rear_3mm/camera_info`

On 117th Orin, `ros2 topic hz` showed both 3mm compressed streams at about 10 Hz. Use `--capture-profile rgb-camera-only` for Orin-side camera capture when LiDAR/IMU/GNSS are recorded separately on IPC. Use `--capture-profile rgb-map-camera-full` only when all six mirror camera streams must be retained. Use `--capture-profile reconstruction-rich` only when camera/object topics are needed for downstream Gaussian/NuRec handoff.

The minimal bag for `pixmoving-auto/liorf` `robobus_color_ros2` should contain:

- `/sensing/lidar/front_top/points`
- `/sensing/lidar/rear_top/points`
- `/sensing/imu/imu_data`
- `/sensing/gnss/fix`
- front/rear LiDAR to `base_link` extrinsics from `ros2 tf`

The `color_pointscloud/orin` RGB pointcloud cache additionally needs the front/rear 3mm compressed camera topics above. If the cameras are recorded on Orin, copy the completed camera bag to the IPC external disk path used for field evidence, for example `/home/ipc/pix/failcase_data/117_rgb_map_camera_capture/`.

The broader validation bag can still include `/tf`, `/tf_static`, `/localization/kinematic_state`, camera topics, and dynamic-object topics if the target is drift comparison or dynamic reconstruction rather than RGB map generation.

## Producer Setup

The RGB pointcloud cache and mapping inputs are external producer dependencies:

```text
pixmoving-auto/color_pointscloud, branch orin
  Generates/caches RGB pointcloud input on Orin or IPC, either by local recording
  or TCP trigger, and emits the ros2bag consumed by mapping.

pixmoving-auto/liorf, branch robobus_color_ros2
  Runs RGB pointcloud SLAM/mapping and produces GlobalMap.pcdrgb.
```

`tools/` in `color_pointscloud` converts the complete RGB pointcloud map into tiled map assets; set its `input_pcd_file` to the LIO-RF output:

```text
GlobalMap.pcdrgb
```

Run SLAM/mapping on the reconstruction producer host, not as part of `simctl --execute` stable validation:

```bash
source /opt/ros/humble/setup.bash

export SLAM_WS=/data/pix/slam_ws
mkdir -p "${SLAM_WS}/src"

git clone --branch robobus_color_ros2 \
  https://github.com/pixmoving-auto/liorf.git \
  "${SLAM_WS}/src/liorf"

cd "${SLAM_WS}"
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select liorf --symlink-install
source install/setup.bash
```

If the repo is already cloned, fetch and rebuild instead of recloning.

## Offline SLAM Run

Terminal 1:

```bash
source /opt/ros/humble/setup.bash
source /data/pix/slam_ws/install/setup.bash

ros2 launch liorf run_robobus_mapping.launch.py \
  params_file:=/data/pix/slam_ws/src/liorf/config/lio_sam_robobus_ros2.yaml \
  use_rviz:=false
```

Terminal 2:

```bash
source /opt/ros/humble/setup.bash
ros2 bag play /data/pix/road_tests/qiyu_reconstruction_capture/<run_id>/ros2bag \
  --clock
```

## Validation

Repo-side smoke:

```bash
simctl run \
  --scenario scenarios/l2/reconstruction_fast_lio_slam_pose_prior.yaml \
  --run-root runs \
  --mock-result passed
```

Producer-side acceptance requires real files and metrics for:

- `slam_trajectory_present`
- `slam_map_present`
- `lidar_imu_time_sync_error_ms`
- `trajectory_continuity_ratio`
- `localization_drift_m`
- `lanelet_alignment_rmse_m`
- `pointcloud_coverage_ratio`

The result is usable only after `pose_prior_manifest.json` records source bag path, LIO-RF commit, color_pointscloud commit when used, config file, lidar/IMU/GNSS topics, output SHA256 values, and alignment diagnostics.

## Downstream Use

- `reconstruction_public_road_map_refresh` consumes the registered pointcloud and trajectory to check lanelet/projector alignment.
- `reconstruction_static_public_road_gaussians` consumes the pose prior when camera frames are available.
- `reconstruction_dynamic_public_road_gaussians` still needs static background, actor masks/tracks, and temporal consistency. SLAM alone is not enough.

## Rollback

Remove the SLAM scenario/profile/gate from repo references and switch reconstruction scenarios back to `reconstruction_public_road_map_refresh`. Delete only external generated outputs under `/data/pix/reconstruction/runs/<run_id>/slam/`; do not remove source bags.
