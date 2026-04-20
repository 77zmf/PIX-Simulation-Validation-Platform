# 117th Robobus Autoware + CARLA Bridge Runbook

这份文档记录当前稳定线里 `robobus117th_town01_closed_loop` 的 CARLA bridge、车辆模型、传感器配置和可验证边界。

## 1. Case objective

目标是先把 Autoware 私有 `robobus` install 和 CARLA 0.9.15 打通，用 `simctl` 可重复启动：

- CARLA `Town01`
- Autoware `planning_simulator`
- `autoware_carla_interface`
- `carla_localization_bridge`
- 117th robobus 车辆参数、地图、传感器话题

## 2. Related source issue or scenario motivation

当前要解决的是稳定线 L0 smoke：让公司 Ubuntu 主机能够稳定启动 CARLA + Autoware，并在 ROS graph 中看到规控链路所需的基础传感器和车辆状态话题。

## 3. Asset bundle inputs

- 场景：`scenarios/l0/robobus117th_town01_closed_loop.yaml`
- 地图：`/home/pixmoving/autoware_map/Town01`
- 参数：`github.com/pixmoving-moveit/parameter:PixRover1.2-1.5/117th`
- CARLA runtime：`/home/pixmoving/CARLA_0.9.15`
- 应用拓扑图：`assets/vehicles/robobus117th/topology/robobus_application_topology_v4.3.0_pixrover1.4.pdf`
- 传感器 catalog：`assets/sensors/robobus_pixrover14_application_topology.yaml`
- 传感器映射：`assets/sensors/carla/robobus117th_sensor_mapping.yaml`
- CARLA bridge 校准：`assets/sensors/carla/robobus117th_prius_fallback_sensor_kit_calibration.yaml`
- Robobus 物理外参保留在：`assets/sensors/carla/robobus117th_sensor_kit_calibration.yaml`

## 4. Scenario assumptions

- Autoware 主栈使用私有 install：`/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware`
- CARLA bridge 使用普通 Autoware install 中带 sensor mapping 的 `autoware_carla_interface`：`/home/pixmoving/zmf_ws/projects/autoware_universe/autoware`
- bridge 启动前会 source 私有 install 作为 underlay，让 `robobus_sensor_kit_description` 包对 ROS 2 可见。
- `start_bridge_host.sh` 会把场景指定的 calibration 文件安装到 sensor kit package 的 `config/sensor_kit_calibration.yaml`。
- L0 fallback 场景仍可使用 `vehicle.toyota.prius` 和 `robobus117th_prius_fallback_sensor_kit_calibration.yaml` 作为回滚路径；多车 cut-in 回归场景已经切到稳定 runtime 中部署的 `vehicle.pixmoving.robobus`，并使用真实 `robobus117th_sensor_kit_calibration.yaml`。
- 真实车传感器基线以 `Bus产品化应用拓扑图V4.3.0 / PixRover1.4` 为准：自动驾驶链路 6 个森云周视相机，其中 camera0 是 `08bc`，camera1-5 是 `SG2-AR0233C-5200-G2A-H120UA`；另有 2 个 `SG2-AR0233C-5200-G2A-H190XA` 远驾补盲相机，当前 L0 CARLA mapping 不启用。
- 激光雷达以拓扑图为准：2 个速腾/RoboSense `M1Plus`、2 个 `Airy`、1 个 `E1R`。当前 mapping 把 `lidar_ft_base_link` 作为 front-top M1Plus，`lidar_rt_base_link` 作为 rear-top M1Plus，`lidar_fl_base_link` / `lidar_fr_base_link` 作为左右 Airy，`lidar_rear_base_link` 作为 E1R 的 rear/supplemental frame；E1R 的实际安装位仍建议现场复核。
- `start_carla_localization_bridge_host.sh` 会等待 CARLA GNSS/velocity topic，并在启动后持续清理一段时间的 `autoware_simple_planning_simulator`，避免它晚启动后重新发布虚拟车辆状态。清理完成后由 CARLA 数据发布 `/localization/kinematic_state`、`/localization/acceleration` 和 `map -> base_link` TF。
- 该场景显式使用 `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`，避开 FastDDS shared-memory lock 对 CLI 订阅和健康检查的影响。
- `start_bridge_host.sh` 默认把 CARLA bridge `timeout` 设为 90 秒；如公司主机切图慢，可用 `SIMCTL_CARLA_BRIDGE_TIMEOUT=120` 临时覆盖。回滚方式是把该环境变量清空，或显式传回 `20`。

## 5. Ego initial condition

当前 `carla_spawn_point` 留空，CARLA bridge 采用随机可用 spawn point，避免 Town01 上手工坐标导致车辆生成失败。后续闭环路线固定后，再把 `ego_init.pose` 转为确定性 `x,y,z,roll,pitch,yaw`。

## 6. Dynamic actor and environment assumptions

L0 smoke 不生成背景车和行人：

- `traffic_profile.mode=empty_smoke`
- `vehicles=0`
- `pedestrians=0`
- `weather_profile=ClearNoon`

L1/L2 动态参与者验证使用可选的 CARLA actor object bridge：

- 默认值：`carla_actor_object_bridge_enabled=false`，L0 `empty_smoke` 不启用，避免把无关 actor 写入空场景 KPI。
- 启用方式：在场景 `execution.stable_runtime` 中设置 `carla_actor_object_bridge_enabled: "true"`，或临时设置 `SIMCTL_CARLA_ACTOR_OBJECT_BRIDGE_ENABLED=true`。
- bridge 入口：`stack/stable/start_carla_actor_object_bridge_host.sh`，实际发布逻辑在 `stack/stable/carla_actor_object_bridge.py`。
- 输入：当前 CARLA world 中非 ego 的 `vehicle.*`，默认也包含 `walker.pedestrian.*`。
- 输出：`/simulation/dummy_perception_publisher/object_info`，由现有 Autoware dummy perception pipeline 转成 `/perception/object_recognition/objects`。
- 验证路径：`ops/runtime_probes/carla_dynamic_actor_probe.py --perception-source actor_bridge --kind l2_close_cut_in --no-rosbag`。
- 已验证 observable：CARLA 目标车切入后 Autoware object pipeline 非空，ego 减速，无碰撞，TTC 保持安全。
- 回滚方式：关闭 `carla_actor_object_bridge_enabled` 或清空 `SIMCTL_CARLA_ACTOR_OBJECT_BRIDGE_ENABLED`；关闭后 L0 smoke 回到仅传感器/定位/规控闭环，不注入动态 object。
- 风险边界：这是 CARLA ground-truth actor 到 Autoware object 的稳定线适配，不等同于真实 BEVFusion/感知模型输出。感知模型验证仍属于 shadow line 或后续 L2/L3 任务。

## 7. Success criteria and KPI hooks

启动健康检查现在不仅检查 `/clock` 和 `/tf`，还会检查这些传感器和车辆状态话题：

- `/sensing/lidar/top/pointcloud_before_sync`
- `/sensing/lidar/rear_top/pointcloud_before_sync`
- `/sensing/lidar/rear/pointcloud_before_sync`
- `/sensing/lidar/left/pointcloud_before_sync`
- `/sensing/lidar/right/pointcloud_before_sync`
- `/sensing/imu/tamagawa/imu_raw`
- `/sensing/gnss/pose_with_covariance`
- `/sensing/camera/CAM_FRONT/image_raw`
- `/sensing/camera/CAM_FRONT/camera_info`
- `/sensing/camera/CAM_BACK/image_raw`
- `/sensing/camera/CAM_BACK/camera_info`
- `/sensing/camera/CAM_FRONT_LEFT/image_raw`
- `/sensing/camera/CAM_FRONT_LEFT/camera_info`
- `/sensing/camera/CAM_FRONT_RIGHT/image_raw`
- `/sensing/camera/CAM_FRONT_RIGHT/camera_info`
- `/sensing/camera/CAM_BACK_LEFT/image_raw`
- `/sensing/camera/CAM_BACK_LEFT/camera_info`
- `/sensing/camera/CAM_BACK_RIGHT/image_raw`
- `/sensing/camera/CAM_BACK_RIGHT/camera_info`
- `/localization/kinematic_state`
- `/localization/acceleration`
- `/vehicle/status/control_mode`
- `/vehicle/status/velocity_status`

`simctl validate` 会先运行 `ops/runtime_probes/carla_sensor_topic_probe.py`，对 6 路相机、5 路激光、IMU、GNSS、定位、车辆状态和 object pipeline 做 ROS topic presence + sample 抽样。结果写入 `<run_dir>/runtime_verification/sensor_topics_*/`，`simctl finalize` 会把它折回 `run_result.json.runtime_evidence`，并额外输出：

- `sensor_topic_coverage`：必需 topic 的通过比例。
- `sensor_sample_coverage`：要求样本的 topic 中成功收到样本的比例。

闭环完成后，用 `simctl finalize` 把 `runtime_verification/closed_loop*.json`、传感器 topic 探针证据和 L1/L2 动态探针证据写回 `run_result.json`：

- `route_completion`：来自 CARLA ego 采样，要求有效 route attempt 到达目标附近。
- `collision_count`：L0 `empty_smoke` 按空场景推断为 0；L1/L2 有交通参与者时来自 `carla_dynamic_actor_probe.py` 的真实探针结果。
- `min_ttc_sec`：L0 `empty_smoke` 按空场景推断为 999 秒；L1/L2 有交通参与者时来自动态探针采样。
- `dynamic_actor_response`：动态探针成功比例，写入 `kpis` 并由 `robobus117th_sensor_actor_bridge` gate 作为硬门槛检查。

`finalize` 会按场景 `traffic_profile.mode` 过滤动态探针，避免 L0 空场景被历史 L1/L2 实验污染。`carla_actor_bridge_close_cut_in` 场景只接收 `l2_close_cut_in + actor_bridge` 探针结果。

## 8. Replay / evaluation method

推荐命令：

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
source .venv/bin/activate
simctl run \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-root runs/robobus117th_bridge \
  --slot stable-slot-01 \
  --execute
```

执行 initialize / route / engage 并采集到 `runtime_verification/closed_loop*.json` 后，关闭报告链路：

```bash
simctl finalize \
  --run-dir <run_dir_from_run_result>

simctl report \
  --run-root runs/robobus117th_bridge
```

L2 actor bridge close cut-in 推荐补充：

```bash
simctl run \
  --scenario scenarios/l2/robobus117th_town01_close_cut_in_actor_bridge.yaml \
  --run-root runs/robobus117th_l2_actor_bridge \
  --slot stable-slot-01 \
  --execute

simctl validate \
  --run-dir <run_dir_from_run_result> \
  --execute \
  --finalize \
  --report
```

自动化活动入口：

```bash
simctl campaign \
  --config ops/test_campaigns/stable_perception_control.yaml \
  --run-root runs/campaign_stable_perception_control_$(date +%Y%m%dT%H%M%S) \
  --slot stable-slot-01 \
  --execute
```

如果已经有一条手动启动的 runtime 线，需要先由自动化关闭再重新跑：

```bash
simctl campaign \
  --config ops/test_campaigns/stable_perception_control.yaml \
  --pre-down-run-dir <existing_run_dir> \
  --run-root runs/campaign_stable_perception_control_$(date +%Y%m%dT%H%M%S) \
  --slot stable-slot-01 \
  --execute
```

批量入口也支持闭环验证，适合后续多个 L2/L3 场景补齐 `metadata.validation_command` 后统一跑：

```bash
simctl batch \
  scenarios/l2/robobus117th_town01_close_cut_in_actor_bridge.yaml \
  --run-root runs/perception_control_auto \
  --parallel 1 \
  --execute \
  --validate \
  --finalize \
  --report \
  --down-on-complete \
  --require-validation
```

`simctl validate` 会读取场景 `metadata.validation_command`，自动替换 `<run_dir>`，并按 `execution.stable_runtime` source ROS 2、Autoware install 和 CARLA PythonAPI。该命令会把探针日志写入 `<run_dir>/validation_logs/`，`--finalize` 会把动态探针证据折回 `run_result.json`，`--report` 会刷新 run-root 报告。

期望 observable：

- `run_result.json.status=passed`
- `gate.passed=true`
- `kpis.route_completion>=0.95`
- L2 actor bridge 场景还应看到 `kpis.collision_count=0`、`kpis.min_ttc_sec>=1.5`、`runtime_evidence.dynamic_probe_attempt_count>=1`
- L2 actor bridge 场景还应看到 `runtime_evidence.sensor_probe_attempt_count>=1`、`kpis.sensor_topic_coverage=1.0`、`kpis.sensor_sample_coverage=1.0`
- `artifacts.runtime_evidence_summary` 指向真实存在的 `runtime_evidence_summary.json`
- report Evidence 包含 `runtime_health`、`runtime_evidence`、`health_report`

如果 rosbag2 或 CARLA recorder 没有实际生成，`finalize` 会从 evidence 中移除它们，并写入 `missing_artifacts`，避免 report 虚报。

NoMachine 可视化：

```bash
SIMCTL_CARLA_RENDER_MODE=visual \
SIMCTL_CARLA_DISPLAY=:0 \
SIMCTL_CARLA_XAUTHORITY="/run/user/$(id -u)/gdm/Xauthority" \
simctl up \
  --stack stable \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-dir runs/manual_robobus117th_bridge_visual \
  --slot stable-slot-01 \
  --execute
```

每次启动可视化时，stable start plan 会自动截图验证：

- 触发条件：`SIMCTL_CARLA_RENDER_MODE=visual`，或场景/环境里 `autoware_rviz=true`
- 默认截图：`<run_dir>/screenshots/visual_startup.png`
- 元数据：`<run_dir>/screenshots/visual_startup.json`
- 等待窗口出现的时间：默认 8 秒，可用 `SIMCTL_VISUAL_SCREENSHOT_WAIT_SEC=12` 临时覆盖
- 回滚方式：不使用 visual/RViz，或把截图步骤从 `stack/profiles/stable.yaml` 的 stable start plan 移除

停止：

```bash
simctl down \
  --stack stable \
  --run-dir <run_dir_from_run_result> \
  --execute
```

## 9. Risks and missing inputs

当前 CARLA runtime 里没有 `vehicle.pixmoving.robobus` 或类似 robobus 蓝图。Autoware 已经使用 `vehicle_model=robobus`，但 CARLA 侧 ego actor 仍使用可执行占位：

```yaml
carla_vehicle_type: vehicle.toyota.prius
```

真正把 robobus 车辆模型导入 CARLA，需要提供 CARLA/UE4.26 可用的 cooked vehicle blueprint，或提供完整 Unreal 车辆资产管线生成 `.uasset/.uexp/.pak`。当前只找到 Autoware 可视化网格 `robobus.dae`，它不能直接作为 CARLA 可驾驶车辆蓝图使用。

当前已补一个可执行的蓝图源包整理入口：

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
bash assets/vehicles/robobus117th/scripts/prepare_source_package.sh
```

默认生成：

```text
artifacts/carla_blueprints/robobus117th_source
```

这个源包会收集 `install` 里的 `robobus.dae`、URDF/xacro、117th 参数集、sensor extrinsics，以及本仓库的 CARLA bridge mapping。它用于 UE4.26/CARLA authoring，不代表已经生成 cooked CARLA 蓝图。详细说明见：

- `assets/vehicles/robobus117th/README_CN.md`
- `assets/vehicles/robobus117th/blueprint_source_manifest.yaml`
- `assets/vehicles/robobus117th/blueprint_authoring_requirements.yaml`

源码工具链安装见：

- `docs/CARLA_SOURCE_TOOLCHAIN_CN.md`

等蓝图存在后，只需要把场景改成：

```yaml
carla_vehicle_type: vehicle.pixmoving.robobus
```

## 10. Owner and next action

- Owner：`zmf`
- 当前可执行下一步：运行 L0 bridge smoke，确认 health 中传感器 topic 全部通过，再用 `simctl finalize` 关闭 `run_result -> KPI gate -> report` 链路。
- 资产下一步：由车辆/仿真资产 owner 提供 CARLA 0.9.15 + UE4.26 可用的 robobus blueprint 或 cooked package。
