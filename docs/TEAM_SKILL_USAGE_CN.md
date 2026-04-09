# 团队 Skill 使用说明

这份文档说明仓库里已经版本化的 repo-side skills 是什么、谁该优先用哪个、以及它们和 `AGENTS.md`、`ops/subagents/` 的关系。

## 1. 这批 skills 放在哪里

仓库内的 repo-side skill pack 在：

- `ops/skills/`

当前包含 5 个 skills：

- `autoware-bug-report`
- `autoware-release-check`
- `carla-case-builder`
- `simctl-run-analysis`
- `ai-superbody-pmo`

这些 skill 不是自动被仓库执行的代码，而是团队在 Codex 里可复用的任务模板和输出规范。

## 2. 它和 AGENTS / 子agent 的关系

三者分工不同：

- `AGENTS.md`
  - 仓库级默认规则
  - 负责定义默认视角、优先级、沟通方式和边界
- `ops/subagents/`
  - repo 内可版本化的子 agent 规格
  - 负责“把某类问题分给哪个 explorer”
- `ops/skills/`
  - repo 内可版本化的 skill 包
  - 负责“某类任务输出应该长什么样、关注哪些检查点”

一句话区分：

- `AGENTS.md` 决定默认做事方式
- `subagents` 决定把问题交给谁看
- `skills` 决定看完后输出什么结构

## 3. 当前 5 个 skills 的作用

### autoware-bug-report

适用：

- 路测异常
- 现场问题
- rosbag / log / 时间点 / 版本号整理
- GitHub issue 草稿

输出重点：

- 现象
- 期望 vs 实际
- 复现条件
- 软件版本
- 证据
- 可交接的 owner / next action

### autoware-release-check

适用：

- 准备交付
- 做 release readiness 判断
- 做基线比较
- 做工作区状态快照

输出重点：

- Release verdict
- workspace snapshot
- risks
- recommended actions
- rollback / handoff clarity

### carla-case-builder

适用：

- 把公开道路问题转成场景
- 新建 replay / regression case
- 标准化 asset bundle 输入

输出重点：

- case objective
- source issue
- asset bundle inputs
- ego / actor / environment assumptions
- success criteria
- replay / evaluation method

### simctl-run-analysis

适用：

- `run_result.json`
- batch 回归结果
- KPI gate 失败
- report / replay 总结

输出重点：

- run identity
- scenario/profile summary
- KPI summary
- failure taxonomy
- replay anchors
- next owner / next action

### ai-superbody-pmo

适用：

- 周会准备
- blocker 清理
- milestone digest
- owner next action 收敛

输出重点：

- milestone status
- completed
- blockers
- risks / escalations
- owner next actions

## 4. 团队成员推荐 skill

### 朱民峰

优先：

- `simctl-run-analysis`
- `autoware-release-check`
- `ai-superbody-pmo`

因为你当前要抓：

- stable 主线
- 运行链验收
- 节奏和交付

### 罗顺雄 / lsx

优先：

- `carla-case-builder`
- `autoware-bug-report`

因为你当前更偏：

- 公开道路资产
- corner case
- 现场问题转场景

### 杨志朋 / Zhipeng Yang

优先：

- `simctl-run-analysis`
- `carla-case-builder`

因为你当前更偏：

- `BEVFusion`
- shadow E2E
- public-road 研究场景

### Codex PMO 支持位

优先：

- `ai-superbody-pmo`
- `simctl-run-analysis`

因为当前更偏：

- digest
- issue / board / weekly review
- 结果和 owner 行动收敛

## 5. 建议使用顺序

推荐顺序不是“先 skill 再看仓库”，而是：

1. 先看 `README.md`
2. 再看 `AGENTS.md`
3. 再看 `docs/TEAM_AGENT_USAGE_CN.md`
4. 再根据任务选 skill
5. 最后才输出 issue / digest / case / release note

## 6. 当前结论

结论很简单：

- 你的 repo 现在不仅有子 agent，也有 repo-side skills
- 这 5 个 skills 已经可以作为团队协同的固定模板
- 后续再扩技能时，优先把 skill 和说明一起版本化进仓库
