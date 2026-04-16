# 明天公司电脑环境检查与缺项补齐清单

这份清单是给你明天到公司 Ubuntu 主机后直接照着执行的。目标只有两个：

1. 检查环境是否满足 `Autoware + CARLA 0.9.15 + UE4.26` 主线
2. 如果缺东西，直接给出下一步命令

## 1. 先拉到最新代码

```bash
cd ~/work
git clone https://github.com/pixmoving-moveit/zmf_ws.git
cd zmf_ws
git pull --ff-only
```

如果你已经有仓库：

```bash
cd /path/to/zmf_ws
git pull --ff-only
```

## 2. 跑一键预检

直接执行：

```bash
bash infra/ubuntu/preflight_and_next_steps.sh
```

如果你明天希望把“远程接入 + 仓库 Python 环境 + 预检”一次铺好，可以直接跑：

```bash
bash infra/ubuntu/bootstrap_remote_access_tailscale.sh --execute --tailscale-hostname zmf-company-ubuntu
```

如果你已经提前生成了 Tailscale auth key，也可以用非交互方式：

```bash
TAILSCALE_AUTH_KEY=tskey-xxxxx \
bash infra/ubuntu/bootstrap_remote_access_tailscale.sh --execute --tailscale-hostname zmf-company-ubuntu
```

这个脚本会做：

- 安装并启动 `openssh-server`
- 用 `uv` 准备本仓库 `Python 3.9+` 的 `.venv`
- 安装并启动 `Tailscale`
- 让公司 Ubuntu 主机加入你的 tailnet
- 最后再跑一遍 `infra/ubuntu/preflight_and_next_steps.sh`

如果你想把“建议执行的命令”直接写成一个脚本：

```bash
bash infra/ubuntu/preflight_and_next_steps.sh --write-fix-script ./host_fix_plan.sh
cat ./host_fix_plan.sh
```

这个预检会检查：

- Ubuntu 版本
- `git / python3 / pip3 / ros2 / colcon / rosdep / vcs`
- `dpkg --audit`
- `nvidia-smi`
- `CARLA_0915_ROOT`
- `AUTOWARE_WS`
- `.venv`
- stable 并行默认端口是否被占用

## 3. 按缺项补齐

预检脚本会直接打印下一步命令。通常会落在这几类：

### 缺基础依赖

```bash
bash infra/ubuntu/bootstrap_host.sh --execute
```

### 缺 CUDA / TensorRT

```bash
bash infra/ubuntu/setup_cuda_tensorrt.sh --execute
```

这一步默认按仓库当前版本安装：

- `CUDA 12.8`
- `TensorRT 10.8.0.43-1+cuda12.8`

### 缺 CARLA runtime

```bash
bash infra/ubuntu/prepare_carla_runtime.sh
```

然后把官方 `CARLA 0.9.15` Linux 包解压到：

```bash
$CARLA_0915_ROOT
```

### 缺 Autoware 工作区

```bash
bash infra/ubuntu/prepare_autoware_workspace.sh --execute
```

### 工作区有了但没编译

```bash
cd "$AUTOWARE_WS"
./setup-dev-env.sh
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

### 缺本仓库 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## 4. 跑主线最小验证

### 4.1 先检查基础状态

```bash
bash infra/ubuntu/check_host_readiness.sh
simctl bootstrap --stack stable
```

### 4.2 先做并行假跑

这一步不要求真实拉起 CARLA / Autoware，只验证槽位调度和工件隔离：

```bash
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed
```

你要看：

- `batch_index.json` 正常生成
- 至少使用了 2 个不同 `slot_id`
- 每个 `run_result.json` 里都有：
  - `slot_id`
  - `carla_rpc_port`
  - `traffic_manager_port`
  - `ros_domain_id`

### 4.3 再做真实双槽位启动

```bash
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --execute
```

你要看：

- 两个 run 的 `slot_id` 不同
- 两个 run 的 CARLA 端口不同
- 两个 run 的 `ROS_DOMAIN_ID` 不同
- 至少进入 `launch_submitted`

## 5. 测完后释放槽位

当前真实 `--execute` 是“启动验证”，不是“自动跑完接力释放”。所以测完要手动停：

```bash
simctl down --stack stable --run-dir runs/<run_id_1> --execute
simctl down --stack stable --run-dir runs/<run_id_2> --execute
```

然后确认锁目录：

```bash
ls artifacts/slot_locks/stable
```

## 6. 明天最重要的验收点

只盯这 5 件事：

1. 预检脚本能不能明确指出缺项
2. 缺项补齐命令能不能直接执行
3. `simctl bootstrap --stack stable` 能不能通过
4. `--parallel 2` 能不能真的分到两个槽位
5. 停掉一个 `run_dir` 时，另一个槽位会不会被误杀

如果你当天还要补 CUDA / TensorRT，再额外确认：

```bash
source ~/.profile
nvcc --version
ldconfig -p | egrep 'libnvinfer|libcudart|libcublas'
```

## 7. 如果明天时间不够

最少跑这三步：

```bash
bash infra/ubuntu/preflight_and_next_steps.sh
simctl bootstrap --stack stable
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed
```
