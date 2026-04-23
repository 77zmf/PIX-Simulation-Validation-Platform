# 远端 GPU 资源清单与 UE4 阻塞说明

对应 issue：

- [#26 输出远端 GPU 资源清单与 UE4 阻塞说明](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/26)
- [#25 明确远端 GPU 节点规格与访问方案](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/25)

这份文档只服务一件事：在当前拿不到新主机回执的情况下，把仓库里已经确认的远端 GPU / UE4 相关资源、仍未确认的项、以及当前 blocker 先收口成一份可执行说明。

## 1. 当前信息来源

当前结论只基于仓库内已经沉淀的资料：

- [docs/COMPANY_HOST_SESSION_2026_04_07_CN.md](./COMPANY_HOST_SESSION_2026_04_07_CN.md)
- [docs/SERVER_COMPILE_BASELINE_CN.md](./SERVER_COMPILE_BASELINE_CN.md)
- [docs/UBUNTU_HOST_BRINGUP_CN.md](./UBUNTU_HOST_BRINGUP_CN.md)
- [docs/TOMORROW_COMPANY_HOST_CHECKLIST_CN.md](./TOMORROW_COMPANY_HOST_CHECKLIST_CN.md)
- [infra/ubuntu/check_host_readiness.sh](../infra/ubuntu/check_host_readiness.sh)
- [infra/ubuntu/bootstrap_remote_access_tailscale.sh](../infra/ubuntu/bootstrap_remote_access_tailscale.sh)
- [infra/ubuntu/setup_cuda_tensorrt.sh](../infra/ubuntu/setup_cuda_tensorrt.sh)

说明：

- 这份资源清单不是“今天实时探测结果”。
- 截至 `2026-04-15`，当前还没有新的公司主机回执，所以这里记录的是仓库内最近一次可核对快照。

## 2. 已确认的远端资源

### 主机与 GPU

| 项目 | 当前状态 | 依据 |
| --- | --- | --- |
| 操作系统 | `Ubuntu 22.04.5` | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| GPU 型号 | `RTX 4090` | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| 驱动版本 | `550.107.02` | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| `nvidia-smi` | 已确认正常 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| UE runtime 目标口径 | `CARLA 0.9.15 / UE4.26` | `SERVER_COMPILE_BASELINE_CN.md` |

### 访问与基础工具

| 项目 | 当前状态 | 依据 |
| --- | --- | --- |
| 仓库 SSH 拉取 | 已完成 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| 代理 | 已接入本地 Clash 代理 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| `git` | 已补齐 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| `pip3` | 已补齐 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| `rosdep` | 已补齐 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| `vcs` | 已补齐 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| `uv` / `pipx` / `ansible-playbook` | 已补齐 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| 仓库 Python venv | 已建立并验证最小 `simctl` 控制面 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |

### 工作区与目录

| 项目 | 当前状态 | 依据 |
| --- | --- | --- |
| `AUTOWARE_WS` | `~/zmf_ws/projects/autoware_universe/autoware` 已准备 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| `autoware.repos` | 已同步 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| `CARLA_0915_ROOT` | `~/CARLA_0.9.15` 目录已预留 | `COMPANY_HOST_SESSION_2026_04_07_CN.md` |
| `CUDA + TensorRT` 安装脚本 | 仓库内已有 | `infra/ubuntu/setup_cuda_tensorrt.sh` |

## 3. 当前仍未确认的资源项

这些项目对 issue `#26` 很重要，但仓库内还没有新的主机回执能把它们打实：

| 项目 | 当前状态 | 备注 |
| --- | --- | --- |
| GPU 显存总量 | 未在仓库快照里直接记录 | 由 `RTX 4090` 可推测常见为 `24 GB`，但这只是推断，必须以 `nvidia-smi --query-gpu=memory.total` 复核 |
| 当前磁盘剩余空间 | 未确认 | 需要 `df -h` |
| 当前内存余量 | 未确认 | 需要 `free -h` |
| 当前 SSH / Tailscale 可达性 | 未拿到新回执 | 访问方案脚本已存在，但还缺这几天的可达性确认 |
| 自托管 runner 是否已落地 | 未确认 | issue `#25` 更偏向这一块 |
| `CarlaUE4.sh` 当前是否已存在 | 未确认 | 目录预留已确认，但运行时包是否已落下还没有新回执 |
| `AUTOWARE_WS/install/setup.bash` 是否已生成 | 未确认 | 需要重新确认编译结果 |

## 4. 当前 UE4 / GPU 主 blocker

### Blocker 1. CARLA / UE4 运行时还没有完成落包确认

当前仓库已经确认：

- `CARLA_0915_ROOT=~/CARLA_0.9.15` 目录已预留

当前仓库还没有确认：

- 官方 `CARLA 0.9.15` 运行时二进制是否已真正落到该目录
- `CarlaUE4.sh` 是否已经存在并可执行

这意味着：

- 还不能把 UE4 runtime 看成已就绪
- `CARLA 0.9.15 / UE4.26` 这条线当前仍然卡在“目录准备完成，但运行时未确认”

### Blocker 2. CUDA / TensorRT 还没完成系统注册

当前已经确认：

- `nvidia-smi` 正常
- 当前还没有 `nvcc`
- 当前还没有 TensorRT 动态库注册到系统

这意味着：

- GPU 驱动层正常，不等于 Autoware 推理链已可用
- `CUDA 12.8 + TensorRT 10.8.0.43-1+cuda12.8` 仍需执行仓库内脚本继续补齐

### Blocker 3. 编译基线还没有拿到“可重用 install”确认

当前仓库里有：

- Autoware 工作区位置
- 收敛过的 first-light 编译边界

当前仓库里还没有：

- `AUTOWARE_WS/install/setup.bash` 已生成的最新确认

这意味着：

- 当前只能说“编译路径已整理”，不能说“编译基线已完全 ready”

### Blocker 4. 当前缺少新的主机回执

这是今天最实际的 blocker：

- 截至 `2026-04-15`，当前没有新的公司主机回执
- 所以 issue `#26` 现在能做的是“把已知资源和 blocker 写清楚”，还不能做“把实时状态补齐”

## 5. 当前可执行的下一步依赖

### 依赖 1. 重新拿到主机访问或至少拿到新的主机回执

最少需要以下任一形式：

- 你本人重新连上主机
- 同事提供一轮最新终端输出
- 或者至少提供最新 `nvidia-smi / df -h / free -h / ls $CARLA_0915_ROOT` 回执

### 依赖 2. 确认 CARLA 0.9.15 运行时包是否已落下

目标不是再讨论路线，而是确认下面这件事：

- `~/CARLA_0.9.15/CarlaUE4.sh` 是否存在

如果不存在，UE4 相关 blocker 就不能关闭。

### 依赖 3. 确认 CUDA / TensorRT 是否已按仓库脚本补齐

建议执行：

```bash
bash infra/ubuntu/setup_cuda_tensorrt.sh --execute
source ~/.profile
nvcc --version
ldconfig -p | egrep 'libnvinfer|libcudart|libcublas'
```

### 依赖 4. 重新确认编译与运行边界

建议重新确认：

- `AUTOWARE_WS/src` 是否完整
- `AUTOWARE_WS/install/setup.bash` 是否存在
- 当前是否还需要最小编译，而不是全量编译

## 6. 拿到主机后优先执行的复核命令

```bash
hostnamectl
cat /etc/os-release
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
df -h
free -h
echo "$AUTOWARE_WS"
echo "$CARLA_0915_ROOT"
ls -lah "$CARLA_0915_ROOT"
test -x "$CARLA_0915_ROOT/CarlaUE4.sh" && echo CARLA_OK || echo CARLA_MISSING
nvcc --version
ldconfig -p | egrep 'libnvinfer|libcudart|libcublas'
bash infra/ubuntu/check_host_readiness.sh
```

## 7. 对 issue #26 的当前结论

在没有新主机回执的前提下，当前已经能明确的结论是：

- 远端 GPU 主机不是完全未知，仓库里已经有一轮可核对快照
- 已知主机基线是 `Ubuntu 22.04.5 + RTX 4090 + driver 550.107.02`
- 当前真正卡住 UE4 / GPU 路径的不是“完全没信息”，而是：
  - CARLA 运行时是否已真正落包还没确认
  - CUDA / TensorRT 还没确认完成注册
  - 编译 install 基线还没重新确认
  - 最新主机回执缺失

因此，issue `#26` 当前可以先视为：

- repo-side 资源清单与 blocker 说明已形成第一版
- 真正关闭 blocker 仍然依赖新的主机回执
