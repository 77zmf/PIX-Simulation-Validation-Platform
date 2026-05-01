# AI 超体工作流优化方案

> 用途：把超体计划从“方向和材料”收敛成每天可执行、可复盘、可交接的工作流。
> 说明：已通过屏幕点击方式读取外部分享页内容，并结合仓库现有超体计划、digest、backlog 和自动化文档整理。

## 1. 总原则

当前工作流只围绕一个主问题组织：

`assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest`

每天的工作不要先问“今天能做什么”，而是先问：

- 哪一环最缺证据？
- 哪个 blocker 正在阻止这条链进入最终 `passed/failed`？
- 今天能否产出一个可追溯工件？

如果一个动作不能推动这条链，默认放到 P1/P2，除非它解除 P0 blocker。

## 2. 每日启动流程

每天开始固定 20 分钟，只做状态归一化。

```bash
git status --short --branch
git pull --ff-only
python -m unittest discover -s tests -v
simctl digest
```

读输出时只提取 5 个信号：

- stable 主线是否有新的真实或 stub-safe 运行证据
- 是否存在 `launch_submitted` 但没有 final status 的 run
- GitHub Project 是否有 P0 逾期项
- blocker 是否缺 owner 或日期
- 今天最小可交付工件是什么

当天工作只允许选 1 个 P0 主任务，加最多 2 个支撑任务。支撑任务必须服务 P0 主任务。

## 3. 当天任务选择规则

优先级按下面顺序决策。

1. `STABLE-001`：finalize / collect / final status
2. `STABLE-002`：host BOM / preflight evidence
3. `STABLE-003`：slot lease / cleanup
4. `ASSET-001`：public-road semantic asset check
5. `SCENARIO-001`：public-road reusable case
6. `REPORT-001`：stable acceptance 与 shadow comparison 分流
7. `PMO-001`：digest 状态和 blocker 语义对齐

研究线任务只有在满足下面条件时才进入当天主任务：

- stable 主线没有更紧急的闭环 blocker
- 研究输出能回指到同一套 `CARLA 0.9.15 / UE4.26` 场景
- 输出能写成 shadow comparison，而不是 stable acceptance

## 4. Codex 会话工作流

每次打开 Codex，先用一个短提示把任务约束住。

```text
Use the repo instructions and keep stable delivery first.
Goal: improve one link in assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest.
Before editing, identify the exact link, owner, affected files, validation command, and host-only gap.
```

如果任务是主线运行闭环：

```text
Use the runtime-closure-audit and repo-verification skills.
Audit the latest run artifacts and tell me the smallest code/config/doc change that moves launch_submitted toward passed/failed.
Then implement it if it is repo-local and verify with the smallest relevant test.
```

如果任务是周会或 blocker 清理：

```text
Use the ai-superbody-pmo skill.
Read the latest digest and backlog. Produce milestone status, current blockers, owner next actions, decisions needed, and the top 3 moves for this week.
Label every item as stable mainline, public-road asset/scenario, shadow comparison, reconstruction support, or PMO.
```

## 5. Agent 协作规则

分享页里的核心判断适合直接落到本项目：多 agent 不是越多越好，第一版控制在 3-5 个职责清晰的角色，并让主 agent 保留最终路由和汇总权。

推荐组合：

- `Supervisor`：任务拆解、路由、预算、最终汇总
- `Research/Data Agent`：读取文档、digest、run artifact、资产和场景信息
- `Execution/Tool Agent`：执行 repo-local 命令、生成工件、整理 patch
- `Verifier/Safety Agent`：检查结果链、风险、host-only 缺口和验收条件
- `Report Agent`：输出周会、digest、issue、验收报告

本项目暂时不要把 agent 继续细拆到“人格”层。只有当 trace 反复显示某一类失败，例如路由错误、工具误选、上下文过大、验证遗漏，才新增专门 agent。

## 6. Handoff 契约

每次 agent 交接都必须能写成结构化契约，而不是传完整聊天记录。

```json
{
  "task_id": "stable-001-finalize",
  "sender": "supervisor",
  "receiver": "verifier",
  "goal": "verify whether the run can move from launch_submitted to passed or failed",
  "track": "stable mainline",
  "inputs": [
    {"artifact": "runs/<run_id>/run_result.json", "type": "run_result"},
    {"artifact": "evaluation/kpi_gates/<gate>.yaml", "type": "kpi_gate"}
  ],
  "constraints": {
    "do_not_claim_ubuntu_acceptance_from_mac": true,
    "max_next_actions": 3
  },
  "expected_output": {
    "verdict": "passed | failed | blocked",
    "missing_links": ["runtime_evidence", "report", "replay"],
    "owner_next_action": "string"
  },
  "handoff_reason": "independent verification required before reporting"
}
```

最小必填字段：

- goal
- receiver
- track
- input artifacts
- expected output
- handoff reason
- stop condition

## 7. 上下文与工件

Agent 之间默认只传三类上下文：

- Global context：季度目标、稳定主线优先、Ubuntu 主机边界、安全边界
- Task context：当前 scenario、run artifact、KPI gate、owner、验收标准
- Artifact context：具体文件路径、命令输出摘要、报告入口、issue 链接

不要把完整聊天、长日志、无关搜索结果传给下游 agent。对自动驾驶/仿真任务，优先传结构化 artifact：

- `scenario_id`
- `run_id`
- `bag_id`
- `time_range`
- `ego_state_summary`
- `object_tracks`
- `failure_metric`
- `risk_level`
- `host_bom`
- `preflight_report`

这条规则直接服务本仓库的主链：`runtime evidence` 和 `run_result` 要成为 agent 之间的事实来源。

## 8. 路由与验证

Supervisor 不应完全依赖自由推理做路由。先用确定规则：

- 涉及 `simctl run/batch/finalize`：stable runtime 路线
- 涉及 `host_bom/preflight/CUDA/CARLA/Autoware`：host readiness 路线
- 涉及 `assets/manifests/scenarios`：public-road case 路线
- 涉及 `BEVFusion/UniAD/VADv2`：shadow comparison 路线
- 涉及 `digest/GitHub Project/owner`：PMO 路线

只有语义模糊或跨路线任务才让 LLM router 判断。每次路由要留下：

- route reason
- confidence
- alternative route
- expected artifact

Verifier 只在关键节点介入：

- 结论会进入周会或 digest
- 代码或配置会影响 stable 主线
- 输出可能被误读为 Ubuntu-host acceptance
- shadow 结果可能污染 stable acceptance

## 9. Tracing / Eval 指标

每周复盘不要只看任务数量，要看 agent 工作流是否更稳定。

建议记录：

- 路由是否正确
- handoff 是否带完整 artifact
- 是否重复读取同一上下文
- 是否把 Mac 验证误写成 Ubuntu acceptance
- 是否存在 `launch_submitted` 被当成最终结果
- 平均交接次数
- 最终是否产出 artifact
- verifier 是否发现遗漏

如果连续两次出现同类失败，再修改提示词、契约或 agent 角色。

## 10. Owner 更新格式

每个 owner 的日报只保留 5 行，避免状态噪声。

```text
Owner:
Track: stable mainline / asset-scenario / shadow comparison / reconstruction / PMO
Today artifact:
Blocker:
Next action + date:
```

示例：

```text
Owner: Zhu Minfeng
Track: stable mainline
Today artifact: runs/<run_id>/run_result.json + runtime_evidence.json
Blocker: KPI gate still sees launch_submitted as intermediate status
Next action + date: wire finalize output into report/replay by 2026-04-26
```

## 11. 周节奏

### 周一：冻结本周唯一主门槛

输出：

- 本周主门槛
- 3 个必须完成的工件
- 需要公司 Ubuntu 主机的命令
- 如果主机不可用的 repo-local 替代动作

### 周三：blocker 清理

只看三类 blocker：

- `needs_host`：必须上公司 Ubuntu 主机
- `needs_assets`：缺地图、点云、rosbag、route、标定或场景输入
- `needs_contract`：缺 schema、状态语义、KPI gate、报告契约

### 周五：证据复盘

只接受工件证据：

- run artifact
- KPI gate output
- report/replay entry
- digest issue
- merged PR 或明确的未合并 diff

## 12. 看板字段要求

GitHub Project 每个活跃任务必须有：

- owner
- priority
- track
- due date
- status
- blocker reason
- next action

建议把 blocker reason 统一成：

- `needs_host`
- `needs_assets`
- `needs_runtime_evidence`
- `needs_kpi_gate`
- `needs_report_replay`
- `needs_decision`

这样 digest 才能反映真实工程阻塞，而不是只显示 `Todo / In Progress`。

## 13. Mac / Ubuntu 分工

Mac 每天负责：

- 代码和文档修改
- 单元测试
- mock batch
- digest / report
- prompt / automation / issue material

公司 Ubuntu 主机负责：

- `simctl up/run/batch --execute`
- Autoware + CARLA bring-up
- runtime evidence 采集
- 并行 slot 压测
- stable acceptance 证据

Mac 上的通过结论只能写作 repo-local validation，不能写作 stable closed-loop acceptance。

## 14. 完成定义

一个当天任务只有满足下面条件，才算完成：

- 有具体文件、命令或工件路径
- 有 `passed / failed / blocked` 判断
- blocker 有 owner 和下一步日期
- 如果依赖 Ubuntu 主机，明确写出 host-only 命令
- rollback 或排除影响清楚

## 15. 近期建议执行顺序

未来 7 天建议按下面顺序走：

1. 关闭 `launch_submitted` 到 final status 的状态缺口
2. 把 host BOM / preflight 写入正式 run artifact
3. 给 stale slot 和异常退出补回收路径
4. 把 `site_gy_qyhx_gsh20260310` 晋升成第一个可复用 case
5. 把 stable acceptance 和 shadow comparison 从报告层分开

这一顺序的原因是：先让主线能形成可信结果，再扩展资产和研究线，否则报告会堆积信息但不能回答“是否通过”。
