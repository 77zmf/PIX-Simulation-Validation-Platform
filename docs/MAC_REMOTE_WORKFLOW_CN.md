# Mac 远程接管工作流

这份说明对应已经接入 `Tailscale` 的公司 Ubuntu 主机，目标是让后续主要工作直接从 Mac 远程继续。

## 当前可用入口

优先使用 `Tailscale`：

```bash
ssh pixmoving@100.112.150.90
```

或者使用 `MagicDNS`：

```bash
ssh pixmoving@pixmoving-system-product-name.taild98089.ts.net
```

## 远程登录后的主工作目录

后续主工作目录统一使用个人仓库：

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
```

公司原始工作区仍在：

```bash
cd /home/pixmoving/zmf
```

但后续开发建议优先在个人仓库继续，再确认后同步到公司仓库。

## 仓库远端约定

个人仓库当前已经配置好两个远端：

```bash
git remote -v
```

预期结果：

- `origin` -> `git@github.com:77zmf/PIX-Simulation-Validation-Platform.git`
- `company` -> `git@github.com:pixmoving-moveit/zmf_ws.git`

推荐推送顺序：

```bash
git push origin main
git push company main
```

## 环境检查

先跑主机预检：

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
bash infra/ubuntu/check_host_readiness.sh
bash infra/ubuntu/preflight_and_next_steps.sh
```

如果需要补 CARLA 运行时：

```bash
bash infra/ubuntu/prepare_carla_runtime.sh --execute
```

如果需要补 Tailscale 远程接入：

```bash
bash infra/ubuntu/bootstrap_remote_access_tailscale.sh --execute --tailscale-hostname zmf-company-ubuntu
```

## Autoware / CARLA 常用核对

```bash
ls -l /home/pixmoving/CARLA_0.9.15/CarlaUE4.sh
source /opt/ros/humble/setup.bash
source /home/pixmoving/zmf_ws/projects/autoware_universe/autoware/install/setup.bash
ros2 pkg prefix autoware_launch
ros2 pkg prefix autoware_carla_interface
```

## 继续编译时建议

先看之前的编译日志：

```bash
tail -n 200 /home/pixmoving/.cache/zmf/build_logs/autoware_normal_startup_build.log
```

进入工作区：

```bash
cd /home/pixmoving/zmf_ws/projects/autoware_universe/autoware
source /opt/ros/humble/setup.bash
source install/setup.bash
```

## 说明

- 仓库里不会同步本机密钥、登录态、运行日志和下载产物。
- 已同步的是远程继续工作真正需要的脚本修正、路径口径和接管说明。
