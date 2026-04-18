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
- 传感器映射：`assets/sensors/carla/robobus117th_sensor_mapping.yaml`
- CARLA bridge 校准：`assets/sensors/carla/robobus117th_prius_fallback_sensor_kit_calibration.yaml`
- Robobus 物理外参保留在：`assets/sensors/carla/robobus117th_sensor_kit_calibration.yaml`

## 4. Scenario assumptions

- Autoware 主栈使用私有 install：`/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware`
- CARLA bridge 使用普通 Autoware install 中带 sensor mapping 的 `autoware_carla_interface`：`/home/pixmoving/zmf_ws/projects/autoware_universe/autoware`
- bridge 启动前会 source 私有 install 作为 underlay，让 `robobus_sensor_kit_description` 包对 ROS 2 可见。
- `start_bridge_host.sh` 会把场景指定的 calibration 文件安装到 sensor kit package 的 `config/sensor_kit_calibration.yaml`。
- 当前 CARLA ego 仍是 `vehicle.toyota.prius` fallback，因此场景使用 CARLA-native 的 `robobus117th_prius_fallback_sensor_kit_calibration.yaml`，避免 117th Robobus 物理外参与 Prius 车体几何不匹配导致相机被车体遮挡。
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

## 7. Success criteria and KPI hooks

启动健康检查现在不仅检查 `/clock` 和 `/tf`，还会检查这些传感器和车辆状态话题：

- `/sensing/lidar/top/pointcloud_before_sync`
- `/sensing/lidar/left/pointcloud_before_sync`
- `/sensing/lidar/right/pointcloud_before_sync`
- `/sensing/imu/tamagawa/imu_raw`
- `/sensing/gnss/pose_with_covariance`
- `/sensing/camera/CAM_FRONT/image_raw`
- `/sensing/camera/CAM_FRONT/camera_info`
- `/localization/kinematic_state`
- `/localization/acceleration`
- `/vehicle/status/control_mode`
- `/vehicle/status/velocity_status`

完整 KPI 仍需要后续接入 initialize pose、route、engage、stop、trajectory/control/collision/TTC 采集。

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
- 当前可执行下一步：运行 L0 bridge smoke，确认 health 中传感器 topic 全部通过。
- 资产下一步：由车辆/仿真资产 owner 提供 CARLA 0.9.15 + UE4.26 可用的 robobus blueprint 或 cooked package。
