# 钉钉代码更新到仿真验证流程

这份 runbook 面向 `超体-仿真` 群里的日常协作：同事更新代码后，Mac 先拉取和做轻量验证，再把正式 stable runtime 验证放到公司 Ubuntu 22.04 主机执行，最后输出可追溯测试结果。

稳定线仍然以公司 Ubuntu 22.04 主机为准。Mac 只负责代码同步、Codex 协作、单元测试、stub/dry-run 验证和结果整理。

## 1. 群里代码更新信息格式

同事在 `超体-仿真` 群里发更新时，建议固定包含：

```text
仓库：pixmoving-moveit/zmf_ws
分支/PR/tag：
commit：
变更范围：
建议验证场景：
期望通过的 KPI 或 observable：
负责人：
回滚方式：
```

最少也要有：

- 分支、PR、tag 或 commit
- 需要验证的场景
- 变更负责人
- 失败后回滚到哪个 commit 或分支

## 2. Mac 侧拉取和轻量验证

先确认本地没有会被覆盖的改动：

```bash
cd /Users/cyber/Documents/zmf_ws
git status --short
```

如果同事给的是分支：

```bash
git fetch origin
git switch <branch>
git pull --ff-only origin <branch>
```

如果同事给的是 commit：

```bash
git fetch origin
git switch -c validation/<short-name> <commit>
```

Mac 侧先跑控制平面验证：

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed
simctl report --run-root runs
```

Mac 侧验证目标：

- 测试用例通过
- `batch_index.json` 正常生成
- 每个 `run_result.json` 能被 `simctl report` 汇总
- 槽位、端口和 `ROS_DOMAIN_ID` 隔离信息存在

这一步不代表真实 closed-loop 通过，只代表仓库控制平面和报告链路没有明显破坏。

## 3. 公司 Ubuntu 主机真实仿真验证

通过 Tailscale 或公司网络 SSH 到正式 runtime 主机后：

```bash
ssh <ubuntu-user>@<tailscale-ip-or-hostname>
cd ~/work/zmf_ws
git fetch origin
git switch <branch>
git pull --ff-only origin <branch>
source .venv/bin/activate
```

先做主机状态确认：

```bash
bash infra/ubuntu/preflight_and_next_steps.sh
bash infra/ubuntu/check_host_readiness.sh
simctl bootstrap --stack stable
```

真实 stable 线建议先跑 L0，再跑 L1：

```bash
simctl run \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-root runs \
  --execute

simctl batch \
  --scenario-dir scenarios/l1 \
  --run-root runs \
  --parallel 2 \
  --execute
```

如果这次只验证控制平面，不拉起真实 CARLA / Autoware，把 `--execute` 去掉或使用：

```bash
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed
```

真实运行结束后生成报告：

```bash
simctl report --run-root runs
```

如需关闭长运行 stable 槽位：

```bash
simctl down --stack stable --run-dir runs/<run_id> --execute
```

## 4. 输出测试结果

结果输出要锚定文件，而不是只写“已验证”。

```text
验证对象：
- 分支/PR/tag：
- commit：
- 负责人：

执行环境：
- Mac 轻量验证：通过 / 失败 / 未跑
- Ubuntu stable runtime：通过 / 失败 / 未跑
- 主机：

执行命令：
- python -m unittest discover -s tests -v
- simctl batch ...
- simctl report ...

结果文件：
- batch_index.json：
- run_result.json：
- report.md：
- report.html：
- replay 命令或入口：

KPI / observable：
- runtime_health：
- gate：
- route_completion：
- control_count：
- trajectory_count：
- max_velocity_mps：

结论：
- passed / failed / blocked

失败或阻塞：
- 现象：
- 证据：
- 初步归因：
- 下一 owner：
- 回滚建议：
```

## 5. 钉钉回填模板

可以直接回到 `超体-仿真` 群里发：

```text
【仿真验证结果】
对象：<branch/pr/tag/commit>
场景：<scenario 或 scenario-dir>
环境：Mac 控制平面 <passed/failed>；Ubuntu stable runtime <passed/failed/blocked>
结果：<passed/failed/blocked>
证据：
- run_result: <path>
- report: <path>
- replay: <command/path>
关键 observable：<runtime_health/gate/route_completion/control_count 等>
阻塞/失败原因：<没有则写 无>
下一步 owner：<name>
回滚建议：<commit/branch 或 无需回滚>
```

## 6. 钉钉机器人发送结果

建议在 `超体-仿真` 群里添加一个自定义机器人，只用于发送验证请求模板和仿真结果。机器人 webhook 和加签 secret 是持久凭证，不要写进 Git。

### 6.1 推荐机器人安全设置

优先使用“加签”安全方式。如果同时配置关键词，建议关键词包含：

```text
仿真验证
```

本仓库默认消息标题是：

```text
PIX 仿真验证结果
```

### 6.2 本机环境变量

在 Mac 或公司 Ubuntu 主机的 shell 中设置：

```bash
export DINGTALK_WEBHOOK='https://oapi.dingtalk.com/robot/send?access_token=...'
export DINGTALK_SECRET='SEC...'
```

如果只启用关键词安全，不启用加签，可以不设置 `DINGTALK_SECRET`。

### 6.3 先 dry-run

默认不发送，只打印将要发送的 payload：

```bash
simctl ding-notify \
  --title "PIX 仿真验证结果" \
  --markdown "## PIX 仿真验证结果

- status: passed
- scenario: l0 smoke"
```

从 `run_result.json` 自动生成摘要：

```bash
simctl ding-notify \
  --run-result runs/<run_id>/run_result.json
```

### 6.4 确认后再发送

只有加 `--execute` 才会真正调用钉钉 webhook：

```bash
simctl ding-notify \
  --run-result runs/<run_id>/run_result.json \
  --execute
```

如果需要提醒某个手机号：

```bash
simctl ding-notify \
  --run-result runs/<run_id>/run_result.json \
  --at-mobile <mobile> \
  --execute
```

发送结果仍然要以 `run_result.json`、`report.md`、`report.html` 和 replay 命令为证据锚点。

## 7. 边界

- 不把 Mac 作为正式 stable runtime 主机。
- 不把 `launch_submitted` 当作 closed-loop 通过。
- 不只看截图或口头反馈，必须保留 `run_result -> KPI gate -> report -> replay` 链路。
- 不为单次验证新增一次性脚本；优先复用 `simctl run / batch / report / replay / digest`。
