# 2026-04-16 公司主机自动化验证快照

这份快照记录 2026-04-16 在公司 Ubuntu 22.04 主机上完成的稳定线环境补齐、`simctl` 自动化流程测试、117th 私有 install 启动验证，以及后续继续推进的边界。

## 1. 今天完成的内容

- 公司主机已完成 CARLA 0.9.15 + Autoware 私有 install 的自动化启动健康检查。
- 117th 参数集已经对齐到稳定验证场景：
  - `vehicle_model=robobus`
  - `sensor_model=robobus_sensor_kit`
  - `LIDAR_TYPE=robosense`
  - `map_path=/home/pixmoving/autoware_map/Town01`
- CARLA bridge 已显式接入 117th sensor mapping：
  - bridge workspace 使用 `/home/pixmoving/zmf_ws/projects/autoware_universe/autoware`
  - private install 作为 underlay 暴露 `robobus_sensor_kit_description`
  - sensor mapping / calibration 位于 `assets/sensors/carla/`
  - 117th 场景显式使用 `rmw_cyclonedds_cpp`，避免 FastDDS shared-memory lock 干扰 CLI topic 验证。
- 新增 L0 场景：
  - `scenarios/l0/robobus117th_town01_closed_loop.yaml`
- `simctl up/run/down/report` 已经能渲染并执行 117th 稳定线参数。
- CARLA 启动脚本支持 `offscreen` / `visual` 两种模式，NoMachine 可视化可以通过 `SIMCTL_CARLA_RENDER_MODE=visual` 临时打开。
- Ubuntu 预检脚本已经覆盖 visual 工具链：
  - `ffmpeg`
  - `xwd`
  - `xprop`
  - `xwininfo`
  - `wmctrl`
  - `xdotool`
  - `gnome-screenshot`
  - `scrot`
  - `ImageMagick import`
  - `glxinfo`
- 修复了 `simctl down` 清理不彻底的问题：
  - 后台进程现在独立 session 启动。
  - stop 脚本会清理 process group、进程树和 CARLA RPC 端口监听残留。
  - 最终验证中 `down` 后进程、端口、slot lock 均为空。

## 2. 自动化流程测试结果

最终干净验证目录：

```bash
/home/pixmoving/PIX-Simulation-Validation-Platform/runs/automation_flow_clean_20260416T112350Z
```

最终真实启动 run：

```bash
/home/pixmoving/PIX-Simulation-Validation-Platform/runs/automation_flow_clean_20260416T112350Z/20260416T112350824885Z__robobus117th_town01_closed_loop
```

最终报告：

```bash
/home/pixmoving/PIX-Simulation-Validation-Platform/runs/automation_flow_clean_20260416T112350Z/final_report/report.md
/home/pixmoving/PIX-Simulation-Validation-Platform/runs/automation_flow_clean_20260416T112350Z/final_report/report.html
/home/pixmoving/PIX-Simulation-Validation-Platform/runs/automation_flow_clean_20260416T112350Z/final_report/summary.json
```

最终汇总：

- `total_runs=3`
- `passed=2`
- `launch_submitted=1`
- `runtime_health.passed=true`
- `failed_checks=[]`
- CARLA RPC 端口 `2000` 第 6 次探测成功。
- ROS graph 第 1 次探测成功。
- `simctl down` 后：
  - `PROCESSES_LEFT=` 空
  - `PORTS_LEFT=` 空
  - `LOCKS_LEFT=` 空

## 3. 当前可复现命令

先做预检：

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
bash infra/ubuntu/preflight_and_next_steps.sh
bash infra/ubuntu/check_host_readiness.sh --visual
```

跑 mock 自动化链路：

```bash
source .venv/bin/activate
simctl batch \
  scenarios/l0/smoke_stub.yaml \
  scenarios/l1/regression_follow_lane.yaml \
  --run-root runs/automation_flow_manual \
  --parallel 2 \
  --mock-result passed
```

跑 117th 真实启动健康检查：

```bash
simctl run \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-root runs/automation_flow_manual \
  --slot stable-slot-01 \
  --execute
```

停止并释放端口：

```bash
simctl down \
  --stack stable \
  --run-dir <run_dir_from_run_result> \
  --execute
```

生成报告：

```bash
simctl report \
  --run-root runs/automation_flow_manual \
  --output-dir runs/automation_flow_manual/report
```

NoMachine 可视化启动方式：

```bash
SIMCTL_CARLA_RENDER_MODE=visual \
SIMCTL_CARLA_DISPLAY=:0 \
SIMCTL_CARLA_XAUTHORITY="/run/user/$(id -u)/gdm/Xauthority" \
simctl up \
  --stack stable \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-dir runs/manual_robobus117th_town01_visual \
  --slot stable-slot-01 \
  --execute
```

## 4. 当前边界

今天完成的是稳定栈自动化启动与健康验证，不是完整规控闭环 KPI 结论。

车辆模型边界：

- Autoware 侧已经使用 `vehicle_model=robobus`。
- CARLA runtime 当前没有可驾驶的 robobus blueprint，因此 CARLA ego actor 暂时使用 `vehicle.toyota.prius` 占位。
- 真正导入 robobus 到 CARLA 需要 UE4.26/CARLA 0.9.15 可用的 vehicle blueprint 或 cooked asset package；仅有 `robobus.dae` 不能直接完成可驾驶车辆导入。

当前真实 run 的状态是：

- `launch_submitted`
- `runtime_health.passed=true`
- gate 仍为 `awaiting_runtime_results`

原因是还没有把以下动作正式接入 `simctl`：

- initialize pose
- set route
- engage autonomous
- stop / disengage
- 轨迹、控制、速度、里程、碰撞和 TTC 指标采集

## 5. 下一步建议

优先继续稳定线，不展开研究线：

1. 在 `simctl` 中增加闭环 smoke 执行 hook，自动完成 initialize / route / engage / stop。
2. 把 `route_completion`、`trajectory_count`、`control_count`、`max_velocity_mps` 等 observable 写入 `run_result.json`。
3. 接入 `collision_count` 和 `min_ttc_sec` 的真实采集，消除 KPI gate 的 partial 状态。
4. 再跑一轮 117th Town01 L0 闭环 smoke，目标状态从 `launch_submitted` 推进到可判定的 KPI result。

## 6. 这次提交的目的

这次提交不是上传运行日志大文件，而是把今天已经验证过的稳定线控制面能力沉淀回仓库，方便：

- 公司主机下次继续从相同脚本入口启动。
- Mac / NoMachine / SSH 三种接管方式复用同一套命令。
- 两位同伴可以直接拉取场景、脚本和 runbook。
- 后续在同一条 `simctl -> run_result -> report -> down` 主线上继续补完整闭环 KPI。
