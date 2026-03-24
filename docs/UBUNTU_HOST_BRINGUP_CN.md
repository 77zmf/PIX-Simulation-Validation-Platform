# 公司 Ubuntu 主机环境落地 Runbook

这份文档以你之前服务器上的真实编译结果为基线，不假设环境是空白机器。

对应基线文档：

- `docs/SERVER_COMPILE_BASELINE_CN.md`

当前目标不是一次性把所有算法都跑起来，而是先完成：

- 沿用当前服务器已有的 CARLA UE5 源码线和 Autoware 工作区线
- 修正或识别宿主机 `dpkg` / `DKMS` 问题
- 打通稳定验证主线需要的基础环境
- 完成 `simctl run -> run_result.json -> report -> replay` 的第一条数据闭环

## 1. 当前采用的两条线

### 线 A：CARLA UE5 源码开发线

用途：

- 地图、资产和 UE5 编辑器开发
- CARLA 源码调试
- 后续高保真方向预备

当前目录约定：

- `CARLA_SOURCE_ROOT=~/zmf_ws/projects/carla_source/CarlaUE5`
- `CARLA_UNREAL_ENGINE_PATH=~/zmf_ws/projects/carla_source/UnrealEngine5_carla`

### 线 B：Autoware.Universe 工作区线

用途：

- `autoware_carla_interface`
- `carla_sensor_kit`
- 稳定验证主线

当前目录约定：

- `AUTOWARE_WS=~/zmf_ws/projects/autoware_universe/autoware`

## 2. 四月初硬目标

四月初前必须完成两件事：

1. 公司 Ubuntu 主机环境可重复准备
2. 第一条自动化数据闭环打通

当前阶段不把这些内容当作目标：

- UE5 package 问题彻底修完
- 大规模公开道路场景库
- 直接端到端控制接管
- 邮件提醒和完整 Notion 自动同步

## 3. 先做什么，不先做什么

### 优先做

- 检查服务器现有目录、环境变量和编译基线是否还在
- 检查 `dpkg --audit` 是否干净
- 继续准备 `ROS 2 Humble`、`rosdep`、`colcon`、Autoware 工作区
- 用现有仓库脚本生成 Ubuntu host 版本的 stable plan

### 不优先做

- 重新从零拉一套新的 CARLA UE5 源码目录
- 把 UE5 package 问题当作当前主线阻塞
- 在宿主机包管理异常时强行跑完整 Autoware build

## 4. 第 1 周执行顺序

### Day 1：确认现有服务器基线

目标：

- 确认 SSH 访问正常
- 确认 sudo 权限正常
- 确认现有 CARLA / Unreal / Autoware 目录是否存在
- 确认 GPU、系统和磁盘资源正常

建议命令：

```bash
hostnamectl
cat /etc/os-release
nvidia-smi
df -h
free -h
bash infra/ubuntu/check_host_readiness.sh
```

验收口径：

- 能稳定 SSH 登录
- 能执行 sudo
- 已确认以下目录是否存在：
  - `~/zmf_ws/projects/carla_source/CarlaUE5`
  - `~/zmf_ws/projects/carla_source/UnrealEngine5_carla`
  - `~/zmf_ws/projects/autoware_universe/autoware`

### Day 2：检查宿主机包管理状态

目标：

- 明确 `dpkg` / `DKMS` 是否干净
- 判断 Autoware 原生依赖安装是否可以继续

建议命令：

```bash
sudo dpkg --audit
bash infra/ubuntu/bootstrap_host.sh
```

验收口径：

- 如果 `dpkg --audit` 干净，则可以继续 ROS 2 / rosdep / colcon
- 如果不干净，则先记录阻塞，优先修宿主机包管理问题

说明：

- 你之前的服务器记录里，`agnocast-kmod-v2.3.0` / `DKMS` 冲突是关键阻塞
- 这类问题没有清干净前，不建议强推 `setup-dev-env.sh`

### Day 3：沿用 CARLA UE5 源码线

目标：

- 验证 CARLA 源码线目录和环境变量
- 必要时继续沿用之前的配置和构建方式

建议命令：

```bash
bash infra/ubuntu/prepare_carla_source.sh
export CARLA_UNREAL_ENGINE_PATH=~/zmf_ws/projects/carla_source/UnrealEngine5_carla
cd ~/zmf_ws/projects/carla_source/CarlaUE5
cmake -G Ninja -S . -B Build --toolchain=$PWD/CMake/Toolchain.cmake -DCMAKE_BUILD_TYPE=Release -DENABLE_ROS2=ON
cmake --build Build
cmake --build Build --target carla-python-api-install
cmake --build Build --target launch
```

验收口径：

- `CarlaSetup.sh` 可继续使用
- `CARLA_UNREAL_ENGINE_PATH` 明确可用
- 源码工程可进入编辑器

说明：

- 这条线当前用于源码开发和 UE5 编辑器，不等同于稳定验证 runtime

### Day 4：沿用 Autoware 工作区线

目标：

- 验证工作区目录
- 导入 `.repos`
- 确认 `autoware_carla_interface` 与 `carla_sensor_kit`

建议命令：

```bash
bash infra/ubuntu/prepare_autoware_workspace.sh
cd ~/zmf_ws/projects/autoware_universe/autoware
find src -path '*autoware_carla_interface' | head
find src -path '*carla_sensor_kit_launch' | head
```

验收口径：

- `AUTOWARE_WS` 目录存在
- `.repos` 已导入
- 关键源码路径可找到

说明：

- 如果 `setup-dev-env.sh` 仍被 `dpkg` / `DKMS` 卡住，这一步先停在源码准备完成即可

### Day 5：打通最小控制平面链路

目标：

- 生成 Ubuntu host 版 stable bootstrap plan
- 产出第一份 smoke 级 `run_result.json`
- 产出 `report.md` 和 `report.html`

建议命令：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
simctl bootstrap --stack stable
simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root runs
simctl report --run-root runs
```

验收口径：

- `start_plan.json` 按 Ubuntu host 方案生成
- `run_result.json` 成功生成
- `report.md` 和 `report.html` 成功生成

## 5. 第 2 周目标

第 2 周开始接近真实链路：

- 明确 `autoware_carla_interface` 启动口径
- 明确 CARLA / bridge / Autoware 三个进程的启动顺序
- 形成第一条可回放的 L0 smoke 结果
- 固化四月初验收模板

## 6. 当前仓库里的现成入口

基础准备：

- `infra/ubuntu/bootstrap_host.sh`
- `infra/ubuntu/check_host_readiness.sh`

沿用之前编译基线：

- `infra/ubuntu/prepare_carla_source.sh`
- `infra/ubuntu/prepare_autoware_workspace.sh`
- `docs/SERVER_COMPILE_BASELINE_CN.md`

稳定栈：

- `stack/profiles/stable.yaml`
- `stack/stable/start_carla_host.sh`
- `stack/stable/start_bridge_host.sh`
- `stack/stable/start_autoware_host.sh`
- `stack/stable/stop_stable_stack.sh`

控制平面：

- `simctl bootstrap --stack stable`
- `simctl run --scenario ...`
- `simctl report --run-root ...`
- `simctl replay --run-result ...`

## 7. 阶段验收清单

- 主机访问正常
- `dpkg --audit` 状态已知
- `ROS 2 Humble` 命令可用
- `colcon` / `rosdep` / `vcs` 可用
- CARLA UE5 源码线目录和环境变量已确认
- `AUTOWARE_WS` 目录与源码已确认
- `simctl bootstrap` 输出的是 Ubuntu host 方案
- `run_result.json`、`report.md`、`report.html` 成功产出

## 8. 当前最容易卡住的点

- 公司主机权限不足，无法安装依赖
- `dpkg` / `DKMS` 状态不干净，导致 Autoware 依赖安装失败
- CARLA UE5 源码线可用，但稳定验证线的 0.9.15 runtime 尚未完全补齐
- `AUTOWARE_WS` 已有源码，但首次构建仍可能因系统依赖失败
- 把 UE5 源码开发线和稳定验证线混在一起推进

遇到这些情况时，不要继续扩任务面，先把阻塞项写进 GitHub Task Board 或 digest。
