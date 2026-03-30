# 服务器编译与运行基线

## 当前正式基线

当前仓库的正式基线只关注：

- `Ubuntu 22.04`
- `ROS 2 Humble`
- `Autoware Universe`
- `CARLA 0.9.15`
- `UE4.26`

本仓库不再把第二套独立开发线写入当前主路线。

## 必须确认的目录

- `AUTOWARE_WS=~/zmf_ws/projects/autoware_universe/autoware`
- `CARLA_0915_ROOT=~/CARLA_0.9.15`

## 必须确认的命令

- `ros2`
- `colcon`
- `rosdep`
- `vcs`
- `nvidia-smi`

## 当前最重要的基线检查

1. `dpkg --audit` 是否干净
2. `CARLA_0915_ROOT/CarlaUE4.sh` 是否存在
3. `AUTOWARE_WS/src` 是否存在
4. `AUTOWARE_WS/install/setup.bash` 是否已经生成

## 当前仓库里的辅助脚本

- 主机准备：`infra/ubuntu/bootstrap_host.sh`
- 主机自检：`infra/ubuntu/check_host_readiness.sh`
- CARLA runtime 准备：`infra/ubuntu/prepare_carla_runtime.sh`
- Autoware 工作区准备：`infra/ubuntu/prepare_autoware_workspace.sh`

## 风险提示

- 不要把 CARLA runtime 安装问题和研究线实验问题混在一起
- 不要在 `dpkg` 状态异常时强推 Autoware 依赖安装
- 不要把 `CARLA 0.9.15 / UE4.26` 和任何额外 runtime 基线混用
