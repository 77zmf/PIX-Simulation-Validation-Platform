# 当前服务器编译基线

这份文档把你之前已经跑过的服务器编译过程固化成项目基线，后续环境搭建、runbook 和推进节奏都以这份基线为准，而不是完全从空白环境重来。

## 1. 当前服务器已确认的信息

### 系统

- Ubuntu 22.04.5 LTS

### GPU

- 2 × NVIDIA RTX5880-Ada-48Q（48GB）
- Driver: 570.172.18
- CUDA: 12.8

### 结论

- 这台服务器足够承担 CARLA 源码编译和后续 Autoware / CARLA 相关流程
- 需要把“源码开发线”和“稳定验证线”分开管理，避免互相混淆

## 2. 现有两条线

### CARLA UE5 源码开发线

用途：

- 地图、资产和源码开发
- UE5 编辑器验证
- 后续 UE5 方向实验的开发底座

当前已知目录：

- `~/zmf_ws/projects/carla_source/CarlaUE5`
- `~/zmf_ws/projects/carla_source/UnrealEngine5_carla`

当前状态：

- `ue5-dev` 源码已拉取
- `CarlaSetup.sh --interactive` 已跑过
- `CARLA_UNREAL_ENGINE_PATH` 已确认需要显式设置
- CMake 配置通过
- 主编译通过
- Python API 已安装成功
- 编辑器 `launch` 成功
- `package` / `package-development` 仍不稳定

当前结论：

- UE5 源码线可继续作为开发环境使用
- 不应把它误当成已经稳定可交付的 packaged runtime

### Autoware.Universe 工作区线

用途：

- 后续接入 `autoware_carla_interface`
- 打通稳定闭环验证主线

当前已知目录：

- `~/zmf_ws/projects/autoware_universe/autoware`

当前状态：

- 主仓库已克隆
- `.repos` 已导入
- `autoware_carla_interface` 已确认存在
- `carla_sensor_kit` 已确认存在
- 默认 host / port / sync 参数已确认

当前阻塞：

- `setup-dev-env.sh` 在当前宿主机上会受到 `agnocast` / `DKMS` / `dpkg` 冲突影响
- 原生 apt 依赖安装不干净时，不适合强行继续 build

## 3. 这对当前项目意味着什么

当前项目应按下面的逻辑推进：

1. 保留现有 CARLA UE5 源码线，不重建、不混用、不误判为稳定 runtime
2. 稳定验证主线继续按 `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` 推进
3. 所有 Ubuntu host runbook 都必须先检查 `dpkg` / `DKMS` 状态
4. 所有 Autoware 相关脚本都要默认沿用现有目录规划，而不是随意新建别的路径

## 4. 当前推荐沿用的目录

- `CARLA_SOURCE_ROOT=~/zmf_ws/projects/carla_source/CarlaUE5`
- `CARLA_UNREAL_ENGINE_PATH=~/zmf_ws/projects/carla_source/UnrealEngine5_carla`
- `AUTOWARE_WS=~/zmf_ws/projects/autoware_universe/autoware`

## 5. 当前推荐沿用的执行顺序

### 对 UE5 源码线

- 先验证现有目录和环境变量
- 再做 `cmake` / `carla-python-api-install` / `launch`
- 不把 package 失败和源码环境是否可用混为一谈

### 对稳定验证线

- 先检查 `dpkg --audit`
- 再准备 ROS 2 / rosdep / colcon
- 再确认 Autoware 工作区和 `autoware_carla_interface`
- 最后再推进稳定闭环

## 6. 当前仓库里的对应入口

- Ubuntu 主机 runbook：`docs/UBUNTU_HOST_BRINGUP_CN.md`
- Ubuntu 主机基础准备：`infra/ubuntu/bootstrap_host.sh`
- Ubuntu 主机自检：`infra/ubuntu/check_host_readiness.sh`
- CARLA 源码线准备：`infra/ubuntu/prepare_carla_source.sh`
- Autoware 工作区准备：`infra/ubuntu/prepare_autoware_workspace.sh`

## 7. 关键提醒

- 现有服务器不是“从零开始”，而是“已有编译基线，需要沿用和清理”
- 当前最容易浪费时间的错误，是把 UE5 源码线、稳定 0.9.15 验证线、Autoware build 阻塞这三件事混在一起推进
