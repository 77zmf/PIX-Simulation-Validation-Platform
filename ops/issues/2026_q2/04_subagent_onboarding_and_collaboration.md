# 子agent上手、阅读顺序与协同约定

{{COORDINATOR_MENTION}} {{LSX_MENTION}} {{YANG_MENTION}}

这条 issue 用来统一团队对仓库内子agent体系的使用方式，避免每个人各自维护一套临时 prompt。

## 目标

- 让团队成员在同一仓库版本上复用同一套 agent 规格
- 让每个人知道先看什么、再用什么 agent、最后怎么回报
- 把 agent 使用从“聊天技巧”变成“仓库内固定入口”

## 先看这些内容

- `docs/TEAM_AGENT_USAGE_CN.md`
- `docs/SUBAGENT_CATALOG.md`
- `docs/MAC_CODEX_WORKFLOW_CN.md`
- `docs/PROJECT_OPERATING_TEAM_CN.md`
- `docs/GIT_COLLABORATION_STANDARD_CN.md`
- `ops/subagents/`

## 最小命令

```bash
python -m simctl subagent-spec --list
python -m simctl subagent-spec --name execution_runtime_explorer
python -m simctl subagent-spec --name execution_runtime_explorer --format spawn_json
```

## 路由建议

- 主机 / bring-up：`stable_stack_host_readiness_explorer`
- 执行链 / run_result / report：`execution_runtime_explorer`
- 公开道路 E2E / shadow：`public_road_e2e_shadow_explorer`
- 重建 / map refresh / Gaussian：`gaussian_reconstruction_explorer`
- 多研究线总览：`algorithm_research_explorer`
- 看板 / digest / 同步：`project_automation_explorer`

## 协同约定

- agent 规格只从 `ops/subagents/` 读，不在群聊里临时漂移
- 研究、资产、主线 bring-up 都回到对应 issue 更新
- blocker 不只说“卡住了”，要带：
  - 当前现象
  - 已验证过什么
  - 下一步建议

## 验收

- 每位成员都能列出可用 subagent
- 每位成员都能渲染至少一个 `spawn_json`
- 每位成员都能在对应 issue 用统一格式回报 blocker / next action

