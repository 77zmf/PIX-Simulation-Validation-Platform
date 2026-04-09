# 子agent上手、阅读顺序与协同约定

{{COORDINATOR_MENTION}} {{LSX_MENTION}} {{YANG_MENTION}}

这条 issue 用来统一团队对仓库内子agent体系的使用方式，避免每个人各自维护一套临时 prompt。  
现在需要同时把仓库级 `AGENTS.md` 和 repo-side skills 一起纳入阅读顺序。

## 目标

- 让团队成员在同一仓库版本上复用同一套 agent 规格
- 让每个人知道先看什么、再用什么 agent、最后怎么回报
- 把 agent 使用从“聊天技巧”变成“仓库内固定入口”

## 先看这些内容

- `AGENTS.md`
- `docs/TEAM_AGENT_USAGE_CN.md`
- `docs/TEAM_SKILL_USAGE_CN.md`
- `docs/SUBAGENT_CATALOG.md`
- `docs/MAC_CODEX_WORKFLOW_CN.md`
- `docs/PROJECT_OPERATING_TEAM_CN.md`
- `docs/GIT_COLLABORATION_STANDARD_CN.md`
- `ops/subagents/`
- `ops/skills/`

## 最小命令

```bash
python -m simctl subagent-spec --list
python -m simctl subagent-spec --name execution_runtime_explorer
python -m simctl subagent-spec --name execution_runtime_explorer --format spawn_json
```

## 两位同学的起手阅读顺序

### `{{LSX_MENTION}}`

1. `README.md`
2. `docs/PROJECT_OPERATING_TEAM_CN.md`
3. `docs/FUTURE_EXECUTION_ROADMAP_CN.md`
4. `docs/TEAM_AGENT_USAGE_CN.md`
5. `docs/SUBAGENT_CATALOG.md`
6. `assets/manifests/` 和 `scenarios/`

### `{{YANG_MENTION}}`

1. `README.md`
2. `docs/ALGORITHM_RESEARCH_ROADMAP_CN.md`
3. `docs/PAPER_READING_MAP_CN.md`
4. `docs/PAPER_LANDSCAPE_CN.md`
5. `docs/TEAM_AGENT_USAGE_CN.md`
6. `docs/SUBAGENT_CATALOG.md`

## 两位同学的推荐子agent

### `{{LSX_MENTION}}`

- 公开道路资产 / replay 模板：`execution_runtime_explorer`
- 重建输入 / map refresh / Gaussian：`gaussian_reconstruction_explorer`

### `{{YANG_MENTION}}`

- `BEVFusion` / shadow planner：`public_road_e2e_shadow_explorer`
- 研究对照 / 指标：`algorithm_research_explorer`

## 建议的使用节奏

1. 先看 `AGENTS.md`，统一默认边界和优先级
2. 再 `--list` 看可用 agent，不要直接手写 prompt
3. 再看对应 agent 的 `spawn_json`
4. 如果任务需要结构化输出，再选对应 skill
5. 先按 issue 范围提单一问题，不要一次混多个方向
6. agent / skill 的输出回填到对应 issue，而不是只停在本地终端

## 常用命令

```bash
python -m simctl subagent-spec --name execution_runtime_explorer
python -m simctl subagent-spec --name execution_runtime_explorer --format spawn_json
python -m simctl subagent-spec --name gaussian_reconstruction_explorer
python -m simctl subagent-spec --name public_road_e2e_shadow_explorer
python -m simctl subagent-spec --name algorithm_research_explorer
```

## 路由建议

- 主机 / bring-up：`stable_stack_host_readiness_explorer`
- 执行链 / run_result / report：`execution_runtime_explorer`
- 公开道路 E2E / shadow：`public_road_e2e_shadow_explorer`
- 重建 / map refresh / Gaussian：`gaussian_reconstruction_explorer`
- 多研究线总览：`algorithm_research_explorer`
- 看板 / digest / 同步：`project_automation_explorer`

## 配套 skills

- 现场 bug / engineer handoff：`autoware-bug-report`
- release readiness：`autoware-release-check`
- CARLA case / replay case：`carla-case-builder`
- `run_result` / KPI gate / report：`simctl-run-analysis`
- 周会 / blocker / PMO digest：`ai-superbody-pmo`

## 协同约定

- agent 规格只从 `ops/subagents/` 读，不在群聊里临时漂移
- 研究、资产、主线 bring-up 都回到对应 issue 更新
- blocker 不只说“卡住了”，要带：
  - 当前现象
  - 已验证过什么
  - 下一步建议
- 每次只让一个 subagent 解决一个明确问题，避免一次提问把资产、研究、主线混在一起

## 验收

- 每位成员都能列出可用 subagent
- 每位成员都能渲染至少一个 `spawn_json`
- 每位成员都知道需要配合哪个 repo-side skill
- 每位成员都能在对应 issue 用统一格式回报 blocker / next action
