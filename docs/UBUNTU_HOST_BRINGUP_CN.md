# 公司 Ubuntu 主机环境落地 Runbook

当前对外展示名统一为 `PIX Simulation Validation Platform`。  
当前可用 GitHub 仓库路径仍然是 `pixmoving-moveit/zmf_ws`，不影响当前运行和交付。

这份文档描述当前正式执行路径：在公司 `Ubuntu 22.04` 主机上完成：

- `ROS 2 Humble`
- `Autoware Universe`
- `CARLA 0.9.15`
- `UE4.26`

当前仓库不再保留第二套仿真 runtime。所有稳定闭环、自动化验证和并行回归都基于这一套环境。

如果你需要一份“明天到公司后直接照着执行”的版本，先看：

- `docs/TOMORROW_COMPANY_HOST_CHECKLIST_CN.md`
- `infra/ubuntu/preflight_and_next_steps.sh`

## 1. 当前硬目标

四月初前必须完成两件事：

1. 公司 Ubuntu 主机环境可重复准备
2. 第一条自动化数据闭环打通

对应的验收结果是：

- `simctl bootstrap --stack stable`
- `simctl run`
- `run_result.json`
- `report.md / report.html`
- `simctl replay`

## 2. Day 1：确认主机基线

目标：

- SSH 正常
- `sudo` 正常
- GPU、磁盘、内存、网络正常
- 工作目录可用

建议命令：

```bash
hostnamectl
cat /etc/os-release
nvidia-smi
df -h
free -h
bash infra/ubuntu/preflight_and_next_steps.sh
bash infra/ubuntu/check_host_readiness.sh
```

## 3. Day 2：清理系统依赖状态

目标：

- `dpkg --audit` 干净
- 可以继续安装 `ROS 2 / colcon / rosdep / vcs`

建议命令：

```bash
sudo dpkg --audit
bash infra/ubuntu/bootstrap_host.sh
```

## 4. Day 3：准备 CARLA 0.9.15 runtime

目标：

- `CARLA_0915_ROOT` 可用
- `CarlaUE4.sh` 可执行
- Town01 可启动

建议命令：

```bash
bash infra/ubuntu/prepare_carla_runtime.sh
bash "$CARLA_0915_ROOT/CarlaUE4.sh" -RenderOffScreen -carla-rpc-port=2000
```

如果需要 NoMachine 里看 CARLA / RViz 画面，先补桌面辅助工具：

```bash
bash infra/ubuntu/bootstrap_host.sh --with-visual-tools --execute
bash infra/ubuntu/check_host_readiness.sh --visual
```

从 Mac SSH 进公司机时，NoMachine 桌面的 `DISPLAY` 通常不会自动带进 shell。当前主机可先用：

```bash
export DISPLAY=:0
export XAUTHORITY=/run/user/$(id -u)/gdm/Xauthority
```

可视化 CARLA 启动示例：

```bash
bash stack/stable/start_carla_host.sh \
  --carla-map Town01 \
  --render-mode visual \
  --res-x 1280 \
  --res-y 720 \
  --quality-level Low \
  --display :0 \
  --xauthority "/run/user/$(id -u)/gdm/Xauthority" \
  --execute
```

## 5. Day 4：准备 Autoware 工作区

目标：

- 工作区存在
- `.repos` 已导入
- `autoware_carla_interface` 可找到

建议命令：

```bash
bash infra/ubuntu/prepare_autoware_workspace.sh
cd "$AUTOWARE_WS"
find src -path '*autoware_carla_interface' | head
find src -path '*carla_sensor_kit_launch' | head
```

## 6. Day 5：打通最小控制平面链路

目标：

- 生成稳定栈 bootstrap plan
- 生成第一份 `run_result.json`
- 生成 `report.md` 和 `report.html`

建议命令：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
simctl bootstrap --stack stable
simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root runs
simctl report --run-root runs
```

当前 `PixRover1.2-1.5/117th` 私有 install 的 L0 闭环 smoke 场景已经版本化在：

```bash
scenarios/l0/robobus117th_town01_closed_loop.yaml
```

该场景会把稳定栈参数渲染为：

```bash
AUTOWARE_WS=/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware
map_path=/home/pixmoving/autoware_map/Town01
vehicle_model=robobus
sensor_model=robobus_sensor_kit
LIDAR_TYPE=robosense
CARLA map=Town01
```

先只渲染启动计划：

```bash
simctl up --stack stable \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-dir runs/manual_robobus117th_town01 \
  --slot stable-slot-01
```

如果这次需要通过 `simctl up` 直接开 NoMachine 可视化窗口，不改场景文件也可以显式覆盖：

```bash
SIMCTL_CARLA_RENDER_MODE=visual \
SIMCTL_CARLA_DISPLAY=:0 \
SIMCTL_CARLA_XAUTHORITY="/run/user/$(id -u)/gdm/Xauthority" \
simctl up --stack stable \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-dir runs/manual_robobus117th_town01_visual \
  --slot stable-slot-01 \
  --execute
```

真实执行前确认当前 shell 已经能访问对应 install、map 和 NoMachine 桌面。回滚方式很简单：换回 `scenarios/l0/smoke_stub.yaml`，或者把该场景的 `execution.stable_runtime` 改回默认 sample profile。

## 7. 并行执行准备

当前仓库已经支持 `stable` 栈的单机多槽位并行模型：

- 槽位配置：`stack/slots/stable_slots.yaml`
- 默认运行建议：`--parallel 2`
- 4 槽位配置已准备好，但需要主机压测后再常态开启

并行回归命令示例：

```bash
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed
```

真实执行时需要注意：

- 每个槽位占用独立的 `CARLA RPC` 端口和 `ROS_DOMAIN_ID`
- 长运行场景需要显式 `down --run-dir <run_dir> --execute` 才会释放槽位
- 先完成 2 槽位稳定性验证，再做 4 槽位压测

## 8. 当前仓库里的可用入口

- `infra/ubuntu/bootstrap_host.sh`
- `infra/ubuntu/check_host_readiness.sh`
- `infra/ubuntu/prepare_carla_runtime.sh`
- `infra/ubuntu/prepare_autoware_workspace.sh`
- `stack/profiles/stable.yaml`
- `stack/slots/stable_slots.yaml`
- `stack/stable/start_carla_host.sh`
- `stack/stable/start_bridge_host.sh`
- `stack/stable/start_autoware_host.sh`
- `stack/stable/stop_stable_stack.sh`

## 9. 最容易卡住的点

- 主机权限不足，无法安装依赖
- `dpkg` / `DKMS` 状态不干净
- `CARLA_0915_ROOT` 不存在或安装不完整
- `AUTOWARE_WS` 依赖解析失败
- 把研究线问题和主线 bring-up 混在一起推进
- 直接上 4 槽位并行，导致 CPU、显存或磁盘写入先失稳
