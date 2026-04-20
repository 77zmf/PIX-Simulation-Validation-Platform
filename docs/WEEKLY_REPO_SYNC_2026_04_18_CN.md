# 2026-04-18 本周仓库同步整理

这份记录用于把本周个人仓库、本地工作区、同事推送和公司仓库同步范围放到同一条主线上。同步优先级仍然是稳定验证线，不把 shadow / research 工作混入稳定闭环结论。

## 1. Objective

- 将本地 `main` 上本周已经形成的控制面改动整理成可推送提交。
- 将同事分支 `personal/sync/lsx-public-road-asset-check-replay` 中的资产检查和 replay 修复并入主线。
- 将 Autoware + CARLA 的最新稳定线进展沉淀到代码、场景、资产清单和 runbook。
- 保持同步顺序：先个人仓库，再公司仓库。

## 2. Scope and assumptions

- 当前机器角色：Mac development terminal，仅用于代码同步、文档、轻量 `simctl` 检查和仓库维护。
- 正式 runtime 仍然只认公司 Ubuntu 22.04 主机。
- 本次整理不上传运行日志、大型压缩包或临时输出目录。
- `launch_submitted` 仍然不是完整闭环 KPI 结论；它只表示启动和 runtime health 已经进入可观察状态。

## 3. Evidence

本周主线提交范围：

- `31d154f` / `460b129` / `1d959b0`：Codex automation overlay、Python 3.9 兼容和导入 bundle。
- `9f7e10e`：117th Robobus Autoware + CARLA bridge、localization bridge、截图证据、CARLA source toolchain 和 robobus 蓝图源包整理。
- `1094408`：同事提交，新增 `simctl asset-check`，补齐公开道路资产 metadata 检查，并修复 replay plan 渲染。

关键文件：

- `scenarios/l0/robobus117th_town01_closed_loop.yaml`
- `stack/profiles/stable.yaml`
- `stack/stable/start_bridge_host.sh`
- `stack/stable/start_autoware_host.sh`
- `stack/stable/start_carla_localization_bridge_host.sh`
- `stack/stable/carla_localization_bridge.py`
- `stack/stable/capture_visual_screenshot_host.sh`
- `stack/stable/stop_stable_stack.sh`
- `assets/sensors/carla/`
- `assets/vehicles/robobus117th/`
- `docs/CARLA_ROBOBUS_BRIDGE_CN.md`
- `docs/CARLA_SOURCE_TOOLCHAIN_CN.md`
- `docs/COMPANY_HOST_SESSION_2026_04_16_CN.md`

## 4. Stable-line progress

Autoware:

- 117th 场景已显式使用私有 Autoware install：`/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware`。
- 参数集对齐到 `vehicle_model=robobus`、`sensor_model=robobus_sensor_kit`、`LIDAR_TYPE=robosense`。
- 场景增加 `ros_rmw_implementation=rmw_cyclonedds_cpp`，用于避开 FastDDS shared-memory lock 对 CLI topic 验证的干扰。
- runtime health 支持按场景检查传感器、车辆状态和 localization topics。

CARLA:

- 当前 runtime 仍是 CARLA `0.9.15` + UE `4.26` 稳定基线。
- CARLA bridge 支持传入 vehicle type、sensor mapping、sensor kit calibration、objects definition、traffic manager 和 timeout。
- 当前 CARLA ego actor 仍使用 `vehicle.toyota.prius` fallback；Autoware 侧使用 robobus 参数。
- 新增 `carla_localization_bridge`，把 CARLA GNSS / velocity 转成 Autoware 期望的 `/localization/kinematic_state`、`/localization/acceleration` 和 `map -> base_link` TF。
- 可视化模式支持自动截图，便于 NoMachine/RViz/CARLA 窗口证据回收。
- `simctl down` 现在会清理进程树、端口、ROS 2 daemon 和 FastDDS shared-memory 残留。

资产和 replay:

- 同事提交已并入 `simctl asset-check --bundle site_gy_qyhx_gsh20260302`。
- 公开道路 bundle 增加 `pointcloud_map_metadata.yaml` 检查，能够比对 manifest、metadata 和实际 `.pcd` tile 数量。
- replay plan 渲染会从 `run_result.json` 补齐 asset、sensor profile 和 algorithm profile 上下文，避免模板占位符泄漏。

## 5. Validation steps

Mac / 本地轻量验证：

```bash
python -m unittest discover -s tests -v
bash .agents/skills/repo-verification/scripts/run_checks.sh
```

公司 Ubuntu 主机真实验证：

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
bash infra/ubuntu/preflight_and_next_steps.sh
bash infra/ubuntu/check_host_readiness.sh --visual
simctl run \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-root runs/robobus117th_bridge \
  --slot stable-slot-01 \
  --execute
simctl down \
  --stack stable \
  --run-dir <run_dir_from_run_result> \
  --execute
simctl report \
  --run-root runs/robobus117th_bridge \
  --output-dir runs/robobus117th_bridge/report
```

期望 observable：

- CARLA RPC 可达。
- ROS graph 至少包含 `/clock`、`/tf`、117th lidar/camera/IMU/GNSS topics、vehicle status topics 和 localization topics。
- `runtime_health.passed=true`。
- `run_result.json` 能被 report/replay 读取。
- `down` 后无残留进程、端口和 slot lock。

## 6. Risks and rollback

- 当前仍未完成 initialize pose、set route、engage、stop、trajectory/control/collision/TTC 采集，所以 KPI gate 仍可能是 partial 或 awaiting runtime results。
- CARLA 侧 robobus 可驾驶蓝图尚未完成，`vehicle.toyota.prius` fallback 不能代表真实 robobus 几何和动力学。
- UE4.26/CARLA source toolchain 需要 Epic/GitHub 授权、大 swap 和足够磁盘，不能在 Mac 上替代公司 Ubuntu runtime。
- 回滚方式：将 117th 场景切回 stub 或禁用该场景；将 `carla_vehicle_type` 保持为 Prius fallback；必要时从 `stack/profiles/stable.yaml` 移除 localization bridge / screenshot steps。

## 7. Next owner / next action

- `zmf`：完成本地验证、推送个人仓库，再同步公司仓库。
- `zmf`：在公司 Ubuntu 主机跑 117th L0 bridge smoke，确认 health topic 全部通过。
- 车辆/仿真资产 owner：提供 CARLA 0.9.15 + UE4.26 可用的 `vehicle.pixmoving.robobus` blueprint 或 cooked package。
- 同事资产线：继续用 `simctl asset-check` 维护公开道路 bundle 的 manifest、metadata 和本地实际资产一致性。
