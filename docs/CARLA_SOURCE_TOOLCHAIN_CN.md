# CARLA 0.9.15 + UE4.26 源码工具链安装

这份文档用于在公司 Ubuntu 22.04 主机上补齐 CARLA 车辆蓝图所需的源码工具链。当前稳定 runtime 已经能跑 CARLA 0.9.15，但缺 UE4.26 Editor / Cook / UnrealPak，所以只能运行已有资产，不能制作 `vehicle.pixmoving.robobus` cooked 蓝图。

## 1. Case objective

目标是安装可制作和 cook CARLA 0.9.15 车辆蓝图的源码工具链：

- CARLA Unreal Engine 4.26 fork / UE4Editor
- CARLA 0.9.15 source
- Blender / assimp mesh 转换工具
- 低内存构建配置和 memory log

## 2. Related source issue or scenario motivation

`assets/vehicles/robobus117th` 已经能从私有 `install` 生成蓝图源包，但当前主机没有 UE4.26 authoring/cook 工具。要把 `robobus.dae` 做成可被 CARLA spawn 的 `vehicle.pixmoving.robobus`，需要源码工具链。

## 3. Asset bundle inputs

- 蓝图源包：`artifacts/carla_blueprints/robobus117th_source`
- 车辆规格：`assets/vehicles/robobus117th/blueprint_authoring_requirements.yaml`
- 源码安装脚本：`infra/ubuntu/prepare_carla_source_toolchain.sh`
- UE4 mesh 导入助手：`assets/vehicles/robobus117th/unreal/import_robobus_mesh.py`

## 4. Scenario assumptions

- 目标版本固定为 CARLA `0.9.15` + UE `4.26`，不切 UE5。
- UE 源码必须使用 `CarlaUnreal/UnrealEngine.git` 的 `carla` 分支；Epic 原版 `4.26` 缺 CARLA 需要的 Renderer/Foliage 头文件。
- Ubuntu 主机当前约 `15 GiB` RAM、`16` 线程、磁盘可用需按实际 `df -h` 复核。
- 当前 swap 只有 `2 GiB`，并且已满；源码编译前必须扩 swap。
- 低内存构建默认使用 `4` 并发，不按 `16` 线程满负载编译。

## 5. Ego initial condition

源码工具链安装不改变稳定场景。`scenarios/l0/robobus117th_town01_closed_loop.yaml` 继续保留 `vehicle.toyota.prius` fallback，直到 runtime blueprint gate 通过后再切到 `vehicle.pixmoving.robobus`。

## 6. Dynamic actor and environment assumptions

源码安装不新增动态 actor；它只服务资产制作和后续 L0 smoke。验证仍沿用 empty smoke 场景。

## 7. Success criteria and KPI hooks

安装 gate：

- `free -h` 显示额外 source-build swap 已启用。
- `UE4Editor` 或 `Engine/Build/BatchFiles/Linux/Build.sh` 可用。
- CARLA source 能完成 `make PythonAPI`、`make LibCarla`、`make CarlaUE4Editor`。
- `assets/vehicles/robobus117th/scripts/check_blueprint_readiness.sh --strict-source` 通过。

蓝图 gate：

- `python3 assets/vehicles/robobus117th/scripts/verify_carla_blueprint.py --blueprint-id vehicle.pixmoving.robobus` 返回 `ok=true`。
- L0 smoke 仍通过 `planning_control_smoke`。

## 8. Replay / evaluation method

先做 dry-run preflight：

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
bash infra/ubuntu/prepare_carla_source_toolchain.sh --phase preflight
```

扩 swap，推荐 `32 GiB`：

```bash
bash infra/ubuntu/prepare_carla_source_toolchain.sh --execute --phase swap --swap-size-gb 32
```

安装依赖和 mesh 工具：

```bash
bash infra/ubuntu/prepare_carla_source_toolchain.sh --execute --phase deps
```

拉源码：

```bash
bash infra/ubuntu/prepare_carla_source_toolchain.sh --execute --phase clone
```

构建 UE4Editor，低内存并发：

```bash
bash infra/ubuntu/prepare_carla_source_toolchain.sh --execute --phase ue-setup --jobs 4
bash infra/ubuntu/prepare_carla_source_toolchain.sh --execute --phase ue-build --jobs 4
```

构建 CARLA source：

```bash
bash infra/ubuntu/prepare_carla_source_toolchain.sh --execute --phase carla-setup --jobs 4
bash infra/ubuntu/prepare_carla_source_toolchain.sh --execute --phase carla-build --jobs 4
```

生成 robobus UE4 导入输入：

```bash
bash assets/vehicles/robobus117th/scripts/prepare_unreal_mesh_inputs.sh
```

## 9. Risks and missing inputs

- UnrealEngine source 需要 GitHub 账号具备 Epic/CARLA fork 访问权限，否则 `git clone git@github.com:CarlaUnreal/UnrealEngine.git` 会失败。
- 当前内存只有约 `15 GiB`，UE4 全量构建必须低并发并启用大 swap；如果经常 swap，构建会很慢，但比 OOM 稳。
- 源码和中间产物会占大量磁盘，建议保留至少 `250 GiB` 空间。
- `sudo` 权限用于 apt 依赖和 swap；没有 sudo 无法完成系统准备。
- 即使源码工具链安装成功，`robobus.dae` 仍可能只是静态视觉 mesh；可驾驶车辆还需要 UE4 里补 wheel blueprint、collision、physics asset 和 movement tuning。

## 10. Owner and next action

- Owner：`zmf`
- 当前下一步：同步脚本到 Ubuntu，先执行 `swap` 和 `deps` 阶段。
- 如果 UE4 clone 失败：先完成 Epic/GitHub 授权，再重跑 `clone` 阶段。
