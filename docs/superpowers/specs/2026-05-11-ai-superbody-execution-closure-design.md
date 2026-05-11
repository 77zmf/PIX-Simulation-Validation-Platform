# AI 超体执行闭环优化设计

日期：2026-05-11

适用仓库：`77zmf/PIX-Simulation-Validation-Platform`

目标：把超体计划从多线并行探索，收敛为一套可重复执行、可定位问题、可交付 bugpack 的 stable 验证闭环。

## 1. 结论

采用“执行闭环优先”方案。

本阶段不以继续扩展 agent 数量、场景数量或展示效果作为主目标。所有工作优先服务下面这条证据链：

```text
scenario -> simctl --execute -> runtime evidence -> final KPI -> report/replay -> bugpack/digest
```

只有当一项工作能让场景从 `launch_submitted` 进入最终 `passed` 或 `failed`，或者能让失败变成可复现 bugpack，才进入 P0。

当前阶段的关键边界：

- 公司 Ubuntu 22.04 主机仍是唯一正式 stable runtime 主机。
- Mac 只做代码同步、控制面验证、文档和轻量检查。
- 不使用 NoMachine 作为自动化依赖，远程控制和状态采集默认只走 SSH/Tailscale。
- `launch_submitted` 不是完成态，只表示启动健康检查已经提交或部分通过。
- BEVFusion、SUMO、重建和 shadow 研究都必须挂回 stable 证据链，不得替代 stable acceptance。

## 2. 七天主门槛

未来一周只设一个主门槛：

> 形成一轮可重复的 stable 规控常态化测试流程，能够自动跑场景、归档 runtime evidence、生成 final KPI、输出 report/replay，并把失败整理成研发可处理的 bugpack。

最小验收结果：

- 至少 1 条 stable L0/L1/L2 场景产生最终 `passed` 或 `failed`。
- 至少 1 个 planning/control 问题被沉淀为 bugpack，包含场景、命令、run artifact、关键日志、KPI 失败原因和 owner next action。
- BEVFusion 当前阻塞必须被清楚标记为 `fixed`、`failed with evidence` 或 `blocked by host access`，不能停留在口头状态。
- SUMO dense traffic 只作为 traffic pressure 场景参与规控验证，不把 SUMO 自身当成独立 runtime。
- 每轮结束后必须执行 cleanup，确认 CARLA、ROS、SUMO、TraCI 端口和 slot lock 没有残留。

## 3. 工作分层

### P0：执行闭环

P0 工作只包含能直接影响最终证据链的内容：

- 恢复和稳定 SSH/Tailscale 远程控制。
- 修复 BEVFusion runtime 依赖、参数和 topic 输出，使感知链路能被 probe 验证。
- 跑 stable follow-lane、SUMO dense traffic、robobus117th acceptance、planning failcase surrogate。
- 对每个 run 执行 `validate --finalize --report`。
- 对失败 run 生成 bugpack，而不是直接修改研发代码。
- 清理进程、端口、slot lock 和临时运行状态。

### P1：场景和数据

P1 工作服务 P0，不单独抢占主线：

- 从 `zmf_test-data` 的 planning bag、视频和测试记录中抽取可仿真的 failcase。
- 把真实场景转成可复用 scenario YAML、asset manifest 和 KPI gate。
- 补齐道路、route、初始 pose、目标行为、NPC/SUMO traffic 和评价指标。
- 维持“标定场景”和“测试场景”分离。

### P2：PMO 和研究线

P2 工作用于周会和路线判断：

- 更新 digest、GitHub Project、owner next action。
- 将 stable acceptance 与 shadow comparison 分栏。
- 整理 BEVFusion、UniAD-style、VADv2 的研究状态，但不影响 stable 主线结论。
- 输出阶段汇报和风险清单。

## 4. Agent 和 Skill 路由

默认由主控 agent 保留最终路由和结论，不把工作拆成过多自由 agent。

推荐角色：

| 角色 | 责任 | 输出 |
| --- | --- | --- |
| Supervisor | 判断当前任务属于 stable、asset/scenario、shadow、host readiness 还是 PMO | route reason、优先级、stop condition |
| Host Readiness | 检查 Ubuntu 主机、SSH/Tailscale、资源、端口、依赖 | readiness verdict、阻塞项、下一条命令 |
| Runtime Closure | 判断 run 是否真正从 `launch_submitted` 进入 final | missing links、finalize/report 缺口 |
| Run Triage | 阅读 run_result、health、KPI、report、日志 | passed/failed/blocked verdict |
| Case Builder | 从真实数据和问题记录沉淀 scenario 与 KPI | scenario draft、asset manifest、validation method |
| PMO Reporter | 整理 owner、blocker、周节奏和汇报材料 | milestone status、owner next actions |

技能使用规则：

- 主机和依赖问题：使用 `pix-host-readiness`。
- run_result、KPI、report/replay 判断：使用 `pix-run-result-triage`。
- 是否闭环完成：使用 `runtime-closure-audit`。
- 公开道路和真实场景沉淀：使用 `pix-public-road-case-builder` 或 `carla-case-builder`。
- 代码或配置改动后验证：使用 `repo-verification`。
- 周会、阶段门、owner：使用 `ai-superbody-pmo`。
- 出现异常行为或失败：使用 `systematic-debugging`，先定位根因再修。

## 5. 每轮自动化测试流程

每轮测试统一按下面顺序执行。

```text
1. host preflight
2. slot cleanup
3. simctl run --execute
4. runtime probe
5. simctl validate --execute --finalize --report
6. bugpack if failed
7. visual evidence if available
8. simctl down --execute
9. port/process/slot verification
10. digest update
```

推荐命令模板：

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

python3 -m simctl.cli run \
  --scenario <scenario_yaml> \
  --run-root /data/pix/sim_runs/<campaign_id> \
  --slot stable-slot-01 \
  --execute

python3 -m simctl.cli validate \
  --run-dir <run_dir> \
  --execute \
  --finalize \
  --report

python3 -m simctl.cli down \
  --stack stable \
  --run-dir <run_dir> \
  --execute
```

每轮必须保存：

- `run_result.json`
- `health.json`
- `start_plan.json`
- `runtime_verification/`
- `validation_logs/`
- `report/report.md`
- `report/report.html`
- `report/summary.json`
- `bugpack/`，仅失败时需要
- 视觉截图或视频，只有在显示环境可用时作为补充证据

## 6. 场景优先级

本阶段优先跑能暴露规控问题的场景，不追求一次覆盖所有模块。

### 第一批

| 优先级 | 场景 | 目的 | 验收 |
| --- | --- | --- | --- |
| P0 | stable follow-lane | 验证直行、速度、转角、控制稳定性 | route/control/final KPI |
| P0 | planning failcase surrogate | 从真实 planning bag 和记录复刻问题 | bugpack |
| P0 | SUMO dense traffic | 检查多 NPC 压力下规控响应 | object stream、ego control、collision/TTC |
| P0 | robobus117th acceptance | 验证 PIX 车辆模型、动力学、刹车、转向 | vehicle probe、visual evidence |
| P1 | BEVFusion public-road occlusion | 验证感知输出和 planner interface | BEV topic、metrics、object stream |

### 第二批

- 强制变道。
- 静态障碍绕行。
- 慢车跟随和超车。
- 红灯停车。
- 路线更新中断恢复。
- 密集交通路口。
- 真实视频风格还原场景。

第二批只有在第一批能稳定产生 final result 后再进入常态化批量。

## 7. Bugpack 输出契约

研发同事需要的是规控问题证据，不是泛泛描述。

每个 bugpack 至少包含：

```text
Issue title:
Track: planning/control | perception | vehicle model | simulator infra
Scenario:
Run dir:
Command:
Final status:
KPI violation:
Observed behavior:
Expected behavior:
Evidence:
Likely owner:
Repro steps:
Non-goals:
```

分类原则：

- 车辆飞起、轮胎不转、油门/刹车异常：先归 `vehicle model` 或 `simulator infra`，不交给规控。
- 感知 topic 缺失、BEV 失败、目标物空：先归 `perception`。
- ego 明明有有效目标和对象流，但规划/控制行为错误：归 `planning/control`。
- CARLA、SUMO、桥接、SSH、磁盘、进程残留：归 `simulator infra`。

## 8. 主机和资源策略

不再把可视化桌面作为自动化前置条件。默认远程路径：

```text
Mac Codex -> SSH/Tailscale -> company Ubuntu host -> simctl
```

安全阈值：

- `/data/pix` 可用空间小于 80 GiB：停止新增大 run，先归档或清理非验证数据。
- 可用内存小于 2 GiB：停止启动新场景。
- swap 可用小于 8 GiB：停止启动新场景。
- 端口 2000、8000、9000 被占用：先确认是否同事在用，再决定清理。
- SSH banner 超时：不继续叠加重试，不启动新 run，保留当前状态并要求本地恢复 SSH 服务。

## 9. 成功指标

一周后用下面指标判断超体计划是否真正优化：

| 指标 | 目标 |
| --- | --- |
| final run result | 至少 1 个真实 `passed` 或 `failed` |
| bugpack | 至少 1 个可交付研发 |
| cleanup | 每轮结束端口和进程清理可验证 |
| BEV status | fixed、failed with evidence 或 blocked 三选一 |
| scenario reuse | 至少 1 个真实 planning failcase 被转成 scenario draft |
| report | 每轮有 report/replay 入口 |
| PMO | owner next action 与 run evidence 对齐 |

## 10. 回滚和风险

回滚策略：

- 所有场景和 profile 改动必须能通过 git diff 明确识别。
- 若新场景导致 stable 栈不稳定，回到 `scenarios/l0/smoke_stub.yaml` 或上一条已知稳定 L1 场景。
- 若 BEVFusion runtime 继续失败，不阻塞 planning/control 主线，改为记录 BEV blocker 并继续 actor bridge/SUMO 规控验证。
- 若 SUMO 协同不稳定，关闭 `sumo_enabled`，回到 CARLA actor bridge 动态参与者。
- 若主机不可达，只做 Mac repo-local 验证和文档整理，不声明 Ubuntu acceptance。

主要风险：

- 当前工作区已有大量未提交改动，必须避免把无关线混入同一个交付。
- BEVFusion 依赖 TensorRT engine 和自定义插件，首次生成 engine 可能导致主机负载高和 SSH 响应慢。
- 真实场景复刻如果缺 route、地图或标定，很容易变成不可复现 demo。
- 如果每次失败都直接改代码而不沉淀 bugpack，会丢失给研发定位的证据链。

## 11. 下一步

设计确认后，进入实现计划阶段，按下面顺序拆任务：

1. 恢复远端 SSH/Tailscale 状态检查和当前 BEV run cleanup。
2. 完成 BEVFusion 插件、engine、topic 输出验证。
3. 选定第一轮 planning/control 场景并运行 `validate --finalize --report`。
4. 对失败结果生成 bugpack。
5. 将真实 planning 数据中的一个问题沉淀为 scenario draft。
6. 更新 digest 和 owner next action。

