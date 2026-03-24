# 公司 Ubuntu 主机环境落地 Runbook

这份文档是四月初目标的第一阶段执行清单，目标不是一次性把所有算法都跑起来，而是先完成：

- 公司 Ubuntu 主机环境准备
- `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` 的稳定栈基础搭建
- `simctl run -> run_result.json -> report -> replay` 的第一条数据闭环

## 1. 执行目标

四月初前必须完成两件事：

1. 公司 Ubuntu 主机环境可重复准备
2. 第一条自动化数据闭环打通

当前阶段不把这些内容当作目标：

- UE5 高保真远端实验
- 大规模公开道路场景库
- 直接端到端控制接管
- 邮件提醒和完整 Notion 自动同步

## 2. 责任边界

- `朱民峰`：主机环境、CARLA、Autoware、bridge、主链路验收
- `罗顺雄 / lsx`：首批资产束和场景输入协助准备
- `杨志朋 / Zhipeng Yang`：`BEVFusion` 和 shadow 输入契约，不阻塞第一阶段主线
- `Codex PMO`：清单、节奏、digest、阻塞项显式化

## 3. 第 1 周执行顺序

### Day 1：确认主机访问与基础能力

目标：

- 确认 SSH 访问正常
- 确认 sudo 权限正常
- 确认主机系统版本、磁盘空间、GPU 驱动、网络访问条件

建议命令：

```bash
hostnamectl
cat /etc/os-release
nvidia-smi
df -h
free -h
```

验收口径：

- 能稳定 SSH 登录
- 能执行 sudo
- 明确 GPU 型号、显存、磁盘剩余空间

### Day 2：准备 ROS 2 / Colcon / Rosdep 基础环境

目标：

- 安装基础依赖
- 安装 `ROS 2 Humble`
- 安装 `colcon`、`rosdep`

建议命令：

```bash
bash infra/ubuntu/bootstrap_host.sh
bash infra/ubuntu/check_host_readiness.sh
```

验收口径：

- `ros2`、`colcon`、`rosdep` 命令可用
- 主机自检脚本没有硬失败

### Day 3：准备 CARLA 0.9.15

目标：

- 明确 `CARLA_0915_ROOT`
- 在主机上验证 `CarlaUE4.sh`
- 跑通离屏启动路径

建议命令：

```bash
export CARLA_0915_ROOT=/path/to/CARLA_0.9.15
bash stack/stable/start_carla_host.sh --run-dir /tmp/carla_smoke --asset-root "$PWD/artifacts/assets"
```

验收口径：

- `CarlaUE4.sh` 可执行
- CARLA 可以以 `-RenderOffScreen` 方式启动

### Day 4：准备 Autoware 工作区

目标：

- 创建 `AUTOWARE_WS`
- 拉取 `Autoware Universe`
- 跑 `rosdep install`
- 完成首次 `colcon build`

建议口径：

```bash
export AUTOWARE_WS=$HOME/autoware_ws
mkdir -p "$AUTOWARE_WS/src"
cd "$AUTOWARE_WS/src"
# 按团队固定版本拉取 Autoware Universe
cd "$AUTOWARE_WS"
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

验收口径：

- `install/setup.bash` 存在
- `AUTOWARE_WS` 可被脚本识别

### Day 5：打通最小控制平面链路

目标：

- 用仓库侧命令生成 stable bootstrap plan
- 生成一条 smoke 级运行结果
- 产出第一份 `run_result.json`

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

- `start_plan.json` 能按 Ubuntu host 方案生成
- `run_result.json` 生成成功
- `report.md` 和 `report.html` 生成成功

## 4. 第 2 周目标

第 2 周不再停留在“环境可安装”，而是开始接近真实链路：

- 明确 `autoware_carla_interface` 启动口径
- 明确 CARLA / bridge / Autoware 三个进程的启动顺序
- 形成第一条可回放的 L0 smoke 结果
- 固化四月初验收模板

## 5. 当前仓库里的现成入口

基础准备：

- `infra/ubuntu/bootstrap_host.sh`
- `infra/ubuntu/check_host_readiness.sh`

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

## 6. 阶段验收清单

- 主机访问正常
- `ROS 2 Humble` 命令可用
- `colcon` / `rosdep` 可用
- `CARLA 0.9.15` 可启动
- `AUTOWARE_WS/install/setup.bash` 存在
- `simctl bootstrap` 输出的是 Ubuntu host 方案
- `run_result.json`、`report.md`、`report.html` 成功产出

## 7. 当前最容易卡住的点

- 公司主机权限不足，无法安装依赖
- ROS 2 安装源或网络访问受限
- CARLA 0.9.15 路径不明确
- `AUTOWARE_WS` 初始化后依赖过多，首次构建失败
- `autoware_carla_interface` 的运行时配置不完整

遇到这些情况时，不要继续扩任务面，先把阻塞项写进 GitHub Task Board 或 digest。
