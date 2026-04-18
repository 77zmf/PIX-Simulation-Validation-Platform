# Robobus 117th CARLA 蓝图源包

这份目录把 Autoware 私有 `install` 里的 robobus 文件整理成 CARLA 0.9.15 / UE4.26 可导入的蓝图源包。它不是 cooked `.uasset` 蓝图本体；当前 Ubuntu runtime 只发现 CARLA runtime 和 `ImportAssets.sh`，没有发现 `UE4Editor`、`UnrealEditor` 或 `RunUAT.sh`，所以这里先把可自动化的素材收集、路径、规格和验证流程固化下来。

## 1. Case objective

目标是把 `robobus_description` 的车体 mesh、`robobus_sensor_kit_description` 的传感器 xacro、117th 参数集里的车辆/传感器标定，以及本仓库里的 CARLA bridge mapping 收成一个标准导入包，为后续生成 `vehicle.pixmoving.robobus` 做准备。

稳定线运行仍保持：

```yaml
carla_vehicle_type: vehicle.toyota.prius
```

等 cooked 蓝图真实存在后，再切换为：

```yaml
carla_vehicle_type: vehicle.pixmoving.robobus
```

## 2. Related source issue or scenario motivation

当前 `robobus117th_town01_closed_loop` 已经能验证 Autoware + CARLA bridge 的传感器话题，但 CARLA 侧 ego actor 还是 Prius 占位车。这个包解决的是资产链路第一步：把 `install` 里的真实 robobus 可视化/标定输入整理出来，避免后续 UE4 导入靠手工散点文件。

## 3. Asset bundle inputs

- Autoware install：`/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware/install`
- 车体 mesh：`robobus_description/share/robobus_description/mesh/robobus.dae`
- 传感器 xacro：`robobus_sensor_kit_description/share/robobus_sensor_kit_description/urdf`
- 参数集：`/home/pixmoving/pix/parameter`
- CARLA runtime：`/home/pixmoving/CARLA_0.9.15`
- 本仓库规格：`assets/vehicles/robobus117th/blueprint_source_manifest.yaml`
- 本仓库 bridge mapping：`assets/sensors/carla/robobus117th_sensor_mapping.yaml`

从 `install/robobus_description/config/vehicle_info.param.yaml` 抽到的几何参数：

- 轮半径：`0.323 m`
- 轮宽：`0.25 m`
- 轴距：`3.02 m`
- 轮距：`1.61 m`
- 前悬 / 后悬：`0.4 m / 0.4 m`
- 左悬 / 右悬：`0.15 m / 0.15 m`
- 计算车长：`3.82 m`
- 计算车宽：`1.91 m`
- 车高：`2.209 m`
- 最大转角：`0.506 rad`

从 `install/robobus_description/urdf/vehicle.xacro` 抽到的视觉 mesh 位姿：

```xml
<origin xyz="1.46 0.14 -0.4" rpy="0 0 0"/>
<mesh filename="package://robobus_description/mesh/robobus.dae" scale="1.0 1.0 1.0"/>
```

DAE 文件自身声明 `Z_UP`，root node 还有近似 `0.001` 的缩放和轴转换矩阵；UE4.26 导入时需要实测尺寸、朝向、原点，不能只看 DAE 顶层 unit。

## 4. Scenario assumptions

- 目标 runtime 是 CARLA 0.9.15 + UE4.26，不走 UE5。
- `robobus.dae` 先作为视觉 mesh 来源；它是否包含可驾驶车辆所需的 skeletal rig、wheel bone、physics asset，需要在 UE4 导入后确认。
- 如果只有静态 DAE visual mesh，可以先做“外观替换/视觉占位”蓝图；要做 CARLA 可驾驶车辆，需要补齐碰撞、车轮、物理资产和 movement tuning。
- 传感器位姿以 `assets/sensors/carla/robobus117th_sensor_kit_calibration.yaml` 为 bridge 输入，不强绑定在 Unreal 车辆蓝图里，避免重复维护。

## 5. Ego initial condition

沿用 `scenarios/l0/robobus117th_town01_closed_loop.yaml`。蓝图导入成功前，CARLA ego actor 仍用 `vehicle.toyota.prius`；蓝图导入成功后只切换 `carla_vehicle_type`，spawn point 和 sensor bridge 不变。

## 6. Dynamic actor and environment assumptions

本包不新增交通流和行人，仍服务 L0 empty smoke：

- `traffic_profile.mode=empty_smoke`
- `vehicles=0`
- `pedestrians=0`
- `weather_profile=ClearNoon`

## 7. Success criteria and KPI hooks

导入前可验证：

- 源包生成成功，包含 mesh、URDF/xacro、vehicle_info、sensor extrinsics、repo bridge mapping。
- `toolchain_status.txt` 清楚标出当前主机是否有 UE4 Editor/Cook 工具。
- `simctl run` 仍能通过 `planning_control_smoke`，传感器话题健康。

导入后可验证：

- CARLA blueprint library 中能找到 `vehicle.pixmoving.robobus`。
- 运行同一个场景时 ego actor type 从 `vehicle.toyota.prius` 变为 `vehicle.pixmoving.robobus`。
- `/sensing/lidar/*`、`/sensing/camera/*`、`/sensing/imu/*`、`/vehicle/status/*` 仍健康。

## 8. Replay / evaluation method

在 Ubuntu 主机生成源包：

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
bash assets/vehicles/robobus117th/scripts/prepare_source_package.sh
```

查看生成物：

```bash
find artifacts/carla_blueprints/robobus117th_source -maxdepth 4 -type f | sort
```

检查当前还缺什么：

```bash
bash assets/vehicles/robobus117th/scripts/check_blueprint_readiness.sh --strict-source
```

准备 UE4 导入输入。若已安装 Blender 会生成 `robobus.fbx`，若已安装 assimp 会生成 `robobus.obj` 视觉占位：

```bash
bash assets/vehicles/robobus117th/scripts/prepare_unreal_mesh_inputs.sh
```

稳定线 smoke：

```bash
source .venv/bin/activate
simctl run \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-root runs/robobus117th_bridge \
  --slot stable-slot-01 \
  --execute
```

## 9. Unreal / CARLA 导入步骤

1. 先按 `docs/CARLA_SOURCE_TOOLCHAIN_CN.md` 安装 UE4.26 / CARLA 0.9.15 源码工具链。
2. 在有 UE4.26 Editor 和 CARLA 0.9.15 source/toolchain 的机器上打开 `/home/pixmoving/CARLA_0.9.15/CarlaUE4/CarlaUE4.uproject`。
3. 优先导入 `artifacts/carla_blueprints/robobus117th_source/unreal_import/robobus.fbx`，没有 FBX 时再用 OBJ/DAE 视觉占位。
4. 可在 UE4 Editor Python 里运行 `assets/vehicles/robobus117th/unreal/import_robobus_mesh.py` 作为 mesh 导入助手。
5. 在 `/Game/Carla/Blueprints/Vehicles/PixMoving/Robobus117th` 下创建或复制一个车辆蓝图，目标 ID 为 `vehicle.pixmoving.robobus`。
6. 给 mesh 绑定材质、碰撞体、physics asset、wheel blueprint 和 vehicle movement 参数。
7. 如果 DAE 只有静态 visual mesh，先做视觉占位验证；若需要真实可驾驶动力学，补 skeletal mesh 或按 CARLA 车辆资产规范重建 rig。
8. Cook/package 出 Linux 可用资产后部署到 CARLA runtime。
9. 运行：

```bash
bash assets/vehicles/robobus117th/scripts/deploy_cooked_blueprint.sh \
  --package-dir <cooked_asset_package> \
  --update-scenario \
  --execute
python3 assets/vehicles/robobus117th/scripts/verify_carla_blueprint.py \
  --blueprint-id vehicle.pixmoving.robobus
```

10. 把 `scenarios/l0/robobus117th_town01_closed_loop.yaml` 的 `carla_vehicle_type` 改为 `vehicle.pixmoving.robobus`，重新跑 L0 smoke。

## 10. Risks and missing inputs

- 当前 `install` 里可确认的是 Autoware/RViz 视觉 mesh 和 ROS 描述，不等同于 CARLA 可驾驶 vehicle blueprint。
- 当前 Ubuntu runtime 没有 UE4 Editor/Cook 工具，不能直接生成 cooked `.uasset/.uexp/.pak`。
- 若 mesh 尺寸、原点或朝向与 CARLA 坐标不一致，需要在 UE4 导入时做 scale/axis 校正，并回写到本 manifest。
- 若 `vehicle_info.yml` 与 mesh 几何外形不一致，规控 footprint 和 CARLA 碰撞体可能不一致，需要以车辆 owner 确认后的参数为准。

## 11. Owner and next action

- Owner：`zmf`
- 当前可执行：在 Ubuntu 主机运行 `prepare_source_package.sh` 生成源包。
- 阻塞项：需要 UE4.26 Editor/CARLA cook toolchain 或已有 cooked robobus 资产，才能产出真正可被 CARLA spawn 的 `vehicle.pixmoving.robobus`。
