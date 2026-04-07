# 主线仓库整理与执行口径收口

{{COORDINATOR_MENTION}} {{LSX_MENTION}} {{YANG_MENTION}}

这条 issue 作为当前季度的总入口，用来收口仓库结构、执行口径、周节奏和 issue 闭环方式。

## 目标

- 保持仓库主线聚焦在 `Autoware + CARLA 0.9.15 + UE4.26`
- 让 Ubuntu 主机 bring-up、`simctl` 控制面、公开道路资产、shadow 研究都能回到同一条执行主线
- 把“文档说明”与“owner 任务推进”分开：
  - 文档负责稳定说明
  - issue 负责持续更新 blocker / next action / 交付日期

## 仓库整理边界

- `infra/ubuntu/` 只放主机环境和 bring-up 入口
- `docs/` 只放长期可复用说明，不承载短期 owner 日报
- `ops/subagents/` 只放可复用的 agent 规格
- 大体量地图、点云、模型不直接进 Git 历史，统一走 manifest / 外部资产目录
- 研究线继续保留，但不能破坏 stable 主线

## 本周要看

- `README.md`
- `docs/UBUNTU_HOST_BRINGUP_CN.md`
- `docs/PROJECT_OPERATING_TEAM_CN.md`
- `docs/FUTURE_EXECUTION_ROADMAP_CN.md`
- `docs/PROJECT_AUTOMATION.md`
- `docs/TEAM_AGENT_USAGE_CN.md`
- `docs/SUBAGENT_CATALOG.md`

## 推荐子agent

- 主机 / bring-up / 环境缺项：`stable_stack_host_readiness_explorer`
- 执行链 / run_result / report / replay：`execution_runtime_explorer`
- 看板 / digest / 协同节奏：`project_automation_explorer`

## 当前拆分

- 资产 / corner case / 重建输入：见配套 issue `02`
- `BEVFusion` / Shadow E2E：见配套 issue `03`
- 团队 agent 使用和阅读顺序：见配套 issue `04`

## 每周回报格式

请直接在本 issue 或子 issue 下按下面格式回报：

```text
本周完成：
- ...

当前 blocker：
- ...

下一个动作：
- ...

需要谁配合：
- ...
```

## 验收

- 关键 owner 都有独立 issue，不再把推进动作埋在聊天里
- 主线文档与 owner issue 的职责边界清晰
- 每周 blocker、next action、交付日期都能在 issue 中找到

