# 远端 GPU 节点规格与访问方案

对应 issue：

- [#25 明确远端 GPU 节点规格与访问方案](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/25)

这份文档的目标不是宣布“主机已经 ready”，而是在当前还没有新主机回执时，先把远端 GPU 节点的推荐访问路径、runner 策略、以及还缺哪些确认项写清楚。

## 1. 当前结论先说清楚

截至 `2026-04-15`，当前最推荐的远端访问方案是：

- 网络入口：`Tailscale`
- 交互登录：`OpenSSH`
- 主机初始化入口：`infra/ubuntu/bootstrap_remote_access_tailscale.sh`
- 主机可用性确认：`infra/ubuntu/check_host_readiness.sh`
- runner 策略：当前先不依赖自托管 runner 做主线执行，先把 `SSH + Tailscale + host readiness` 路径跑稳

也就是说：

- 当前最先要稳定的是“人能进主机、仓库能拉、预检能跑”
- 不是先把 GitHub Actions self-hosted runner 硬上到主机

## 2. 当前已知的节点规格

基于仓库内 `2026-04-07` 快照，当前已知的远端 GPU 节点信息是：

| 项目 | 当前已知状态 | 备注 |
| --- | --- | --- |
| 操作系统 | `Ubuntu 22.04.5` | 已有快照 |
| GPU 型号 | `RTX 4090` | 已有快照 |
| GPU 驱动 | `550.107.02` | 已有快照 |
| `nvidia-smi` | 正常 | 已有快照 |
| UE 运行时目标 | `CARLA 0.9.15 / UE4.26` | 仓库正式基线 |
| `AUTOWARE_WS` | `~/zmf_ws/projects/autoware_universe/autoware` | 已有快照 |
| `CARLA_0915_ROOT` | `~/CARLA_0.9.15` | 目录已预留 |

当前还没有新回执确认的项目：

| 项目 | 当前状态 | 需要什么确认 |
| --- | --- | --- |
| GPU 显存 | 未确认 | `nvidia-smi --query-gpu=memory.total` |
| 磁盘剩余空间 | 未确认 | `df -h` |
| 内存余量 | 未确认 | `free -h` |
| 当前 SSH 可达性 | 未确认 | `systemctl status ssh` 与实际登录 |
| 当前 Tailscale 可达性 | 未确认 | `tailscale status` / `tailscale ip -4` |
| 自托管 runner 是否已注册 | 未确认 | GitHub runner 页面或 `svc.sh status` |

## 3. 推荐访问路径

### Phase 1. 当前默认方案

当前默认方案应该是：

1. 在 Ubuntu 主机上执行：

```bash
bash infra/ubuntu/bootstrap_remote_access_tailscale.sh --execute --tailscale-hostname zmf-company-ubuntu
```

如果已经有 auth key，可以用：

```bash
TAILSCALE_AUTH_KEY=tskey-xxxxx \
bash infra/ubuntu/bootstrap_remote_access_tailscale.sh --execute --tailscale-hostname zmf-company-ubuntu
```

2. 这个脚本会统一做：

- 安装并启动 `openssh-server`
- 安装并启动 `Tailscale`
- 准备仓库 `.venv`
- 让主机加入 tailnet
- 最后执行 repo preflight

3. 然后从外部机器通过 Tailscale IPv4 登录：

```bash
ssh <user>@<tailscale-ip>
```

### 为什么优先选这条路

- 不需要直接暴露公网 SSH 入口
- 不需要先申请固定公网 IP 才能继续
- 仓库已经有现成脚本，不需要先写新工具
- 对当前阶段的目标最合适：先拿到主机、先跑预检、先补环境

## 4. 不推荐的访问方式

当前不推荐作为主路径的方式：

- 直接暴露公网 SSH 端口
- 在没有 Tailscale / SSH 稳定前先上自托管 runner
- 把“远端访问问题”和“CARLA / UE4 runtime 问题”混成一个步骤排查

原因很简单：

- 问题会耦合
- 出了故障很难判断是网络、权限、runner 还是 runtime
- 不利于后续同事复用同一路线

## 5. 自托管 runner 方案建议

### 当前建议

当前建议把 runner 分成两个阶段看：

#### 阶段 A. 现在

- 不把 self-hosted runner 当作当前阶段的硬前置
- 仍然以 `SSH + Tailscale + 手工预检` 为主
- 仓库现有 GitHub Actions 继续跑在 GitHub-hosted runner 上

也就是说：

- `project management / issue plan / digest` 这些自动化，不需要依赖远端 GPU 主机
- 远端 GPU 主机当前优先服务环境确认，不优先服务 Actions 自动执行

#### 阶段 B. 主机访问稳定之后

如果后续要上 self-hosted runner，建议方案是：

- 只在公司 Ubuntu GPU 主机上注册 1 个 runner
- 仅用于：
  - 主机资源回执采集
  - readiness / preflight / inventory 类脚本
  - 轻量文档或状态同步任务
- 暂时不要用于：
  - 长时间 CARLA 仿真
  - 大规模 Autoware 全量编译
  - 多槽位并行 execute

### 推荐 runner 标签

如果后续注册，建议最少带这些标签：

- `self-hosted`
- `linux`
- `x64`
- `gpu`
- `ue4-lab`
- `ubuntu22`

### runner 使用边界

- 只给当前仓库使用，不要先开放成组织级通用 runner
- 只在 SSH / Tailscale 路径稳定后再注册
- 只保留 GitHub 到 runner 的出站连接，不额外暴露新的公网入口
- 长运行仿真仍然优先人工触发与观察，不交给 runner 长时间托管

## 6. 当前 still-blocked 的点

`#25` 当前仍然 blocked，但 blocker 已经比较清楚：

1. 没有新的主机回执
2. 没法确认当前 `SSH / Tailscale` 是否真的可用
3. 没法确认 `CarlaUE4.sh` 是否已经落包
4. 没法确认 runner 是否已经注册或是否值得现在注册

所以这条 issue 当前真正能完成的是：

- 先把访问方案定下来
- 先把推荐路径和 runner 边界定下来

而不是：

- 假装已经确认了实时网络和 runner 状态

## 7. 拿到主机后优先执行的确认命令

```bash
hostnamectl
cat /etc/os-release
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
df -h
free -h
sudo systemctl --no-pager --full status ssh | sed -n '1,12p'
tailscale status || true
tailscale ip -4 || true
echo "$CARLA_0915_ROOT"
ls -lah "$CARLA_0915_ROOT"
test -x "$CARLA_0915_ROOT/CarlaUE4.sh" && echo CARLA_OK || echo CARLA_MISSING
bash infra/ubuntu/check_host_readiness.sh
```

如果要继续确认 runner：

```bash
ls -lah ~/actions-runner || true
./svc.sh status || true
```

## 8. 对 issue #25 的当前结论

在没有新主机回执的前提下，这条 issue 当前已经能明确的结论是：

- 推荐访问路径已经明确：`Tailscale + OpenSSH`
- 推荐初始化入口已经明确：`infra/ubuntu/bootstrap_remote_access_tailscale.sh`
- runner 当前不是硬前置，只是后续可选增强
- 现在最缺的不是“方案”，而是“新的主机回执”

所以 `#25` 当前可以先视为：

- repo-side 访问方案已经形成第一版
- 正式确认仍然依赖新的主机访问或新的终端输出
