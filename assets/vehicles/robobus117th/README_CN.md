# Robobus 117th CARLA 蓝图源包

这份目录把 Autoware 私有 `install` 里的 robobus 文件整理成 CARLA 0.9.15 / UE4.26 可导入和可验证的蓝图源包。当前公司 Ubuntu 主机已经具备 CARLA 0.9.15 + UE4.26 源码工具链，并已完成 `vehicle.pixmoving.robobus` 的单 CARLA actor 运行验证。

## 1. Case objective

目标是把 `robobus_description` 的车体 mesh、`robobus_sensor_kit_description` 的传感器 xacro、117th 参数集里的车辆/传感器标定，以及本仓库里的 CARLA bridge mapping 收成一个标准导入和验证包，服务 `vehicle.pixmoving.robobus` 在 CARLA 中作为真实 ego actor 运行。

稳定线可按场景需要从 Prius fallback 切换到：

```yaml
carla_vehicle_type: vehicle.pixmoving.robobus
```

Prius 仍作为回滚 actor，不再是唯一可运行路径。

## 2. Related source issue or scenario motivation

当前 `robobus117th_town01_closed_loop` 已经能验证 Autoware + CARLA bridge 的传感器话题；CARLA 侧 `vehicle.pixmoving.robobus` 已可被 blueprint library 发现、spawn，并通过 CARLA `VehicleControl` 加速和左右转向。这个包继续承担资产链路标准化职责，避免 UE4 导入、cook、部署和验证靠手工散点文件。

## 2.1 当前运行状态

截至 2026-04-19，公司 Ubuntu 主机上的可运行状态如下：

- actor id：`vehicle.pixmoving.robobus`
- runtime：`/home/pixmoving/CARLA_0.9.15`
- source toolchain：`/home/pixmoving/zmf_ws/source_toolchain/carla-0.9.15` + UE4.26
- authoring method：Fuso 稳定车辆蓝图作为单 actor 物理 carrier，在同一蓝图内通过 UE4 commandlet 添加 PIX 视觉 mesh 子组件，不使用外部跟随车或外部 overlay actor
- 验证 run：`/home/pixmoving/PIX-Simulation-Validation-Platform/runs/robobus_single_actor_visual_20260419T080120Z/direct_single_actor_visual_validation_20260419T081239Z`
- 结果：`passed=true`，`distance_m=29.318075`，`max_speed_mps=5.150921`，`max_abs_pitch_deg=0.119542`，`max_abs_roll_deg=0.810883`
- 证据：`pix_robobus_direct_start.png`、`pix_robobus_direct_after_drive.png`、`vehicle_pixmoving_robobus_direct_drive.mp4`、`direct_pix_actor_summary.json`

当前方案的边界也要明确：这是“单 CARLA actor + PIX 视觉 + 稳定车辆物理”的可测试路径，已经不是外部跟随体；但 collision/PhysicsAsset 仍沿用稳定 carrier。若验收要求完全原生 PIX collision、wheel bone、PhAT 和可视化轮胎动画，需要继续做 UE4 PhAT/C++ 资产 authoring。

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

L0 fallback 仍沿用 `scenarios/l0/robobus117th_town01_closed_loop.yaml`。源码包蓝图通过 spawn 验证后，`scenarios/l2/planning_control_multi_actor_cut_in_lead_brake.yaml` 已切到 `vehicle.pixmoving.robobus`，并使用确定性 CARLA spawn point `229.7817,2.0201,-0.5,0,0,0`；CARLA bridge 会在 z 方向自动加 2m，因此实际 spawn 高度约为 1.5m。

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

- 当前 `install` 里可确认的是 Autoware/RViz 视觉 mesh 和 ROS 描述，不天然等同于 CARLA 原生可驾驶 vehicle blueprint。
- 公司 Ubuntu 主机已经可以 cook 和部署 cooked `.uasset/.uexp`，但完整 LinuxNoEditor package 仍应在发布前单独归档。
- 当前可运行路径使用稳定 carrier 物理，适合推动 CARLA/Autoware 闭环和视觉验证；若后续 KPI 依赖精确碰撞体、轮胎动画或真实二轮/四轮转向模型，需要升级为原生 PIX PhysicsAsset 和 movement tuning。
- 若 mesh 尺寸、原点或朝向与 CARLA 坐标不一致，需要在 UE4 导入时做 scale/axis 校正，并回写到本 manifest。
- 若 `vehicle_info.yml` 与 mesh 几何外形不一致，规控 footprint 和 CARLA 碰撞体可能不一致，需要以车辆 owner 确认后的参数为准。

## 11. Owner and next action

- Owner：`zmf`
- 当前可执行：在 Ubuntu 主机启动 CARLA 后运行 `validate_carla_direct_pix_actor.py` 验证 `vehicle.pixmoving.robobus` spawn、行驶、截图和视频。
- 下一步：把当前 UE4 commandlet authoring 过程固化为 repo 脚本/补丁包，并补原生 PIX collision、wheel/steering 可视化、二轮/四轮模式切换验证。
