# 2026-04-07 公司主机进展快照

这份快照记录 2026-04-07 在公司 Ubuntu 主机上已经完成的环境补齐、当前状态，以及下一步建议命令。

## 1. 今天已经完成的内容

- 仓库已通过 SSH 拉到公司主机。
- 本地 Clash 代理已接入，后续外网下载可复用。
- 用户态工具已补齐：`git`、`pip3`、`rosdep`、`vcs`、`uv`、`pipx`、`ansible-playbook`。
- 已建立仓库 Python 3.11 虚拟环境，并完成 `simctl` 最小控制面验证。
- Autoware 工作区已准备到 `~/zmf_ws/projects/autoware_universe/autoware`，`autoware.repos` 已同步。
- CARLA 目录已预留到 `~/CARLA_0.9.15`，但官方运行时二进制还需要你手动落包。
- 已整理 `Autoware + CARLA` 的 first-light 编译边界，并收敛出一条较小的 `colcon build` 方案。
- 已新增仓库内 `CUDA + TensorRT` 安装脚本：
  - `infra/ubuntu/setup_cuda_tensorrt.sh`

## 2. 当前主机状态

- 操作系统：`Ubuntu 22.04.5`
- GPU：`RTX 4090`
- 当前驱动：`550.107.02`
- `nvidia-smi` 正常
- 当前还没有 `nvcc`
- 当前还没有 TensorRT 动态库注册到系统

## 3. 下一步建议

### 3.1 先补 CUDA / TensorRT

```bash
bash infra/ubuntu/setup_cuda_tensorrt.sh --execute
source ~/.profile
nvcc --version
ldconfig -p | egrep 'libnvinfer|libcudart|libcublas'
```

注意：

- 仓库当前默认版本是 `CUDA 12.8`
- TensorRT 默认版本是 `10.8.0.43-1+cuda12.8`
- 这台主机当前驱动是 `550.107.02`
- 如果安装后出现 driver mismatch，再单独评估是否升到 `570+`

### 3.2 再决定是否编译

如果继续只保留 `Autoware + CARLA` 联合仿真链路，可以优先用当前收敛过的最小编译入口，而不是直接全量编译整个工作区。

## 4. 这次提交的目的

这次不是上传主机上的个人 dotfiles，而是把今天已经验证过的流程沉淀回仓库，方便：

- 明天继续在同一台公司主机上接着做
- 其他同事复用同一套 Ubuntu bring-up 路线
- 预检脚本直接提示 CUDA / TensorRT 缺项
