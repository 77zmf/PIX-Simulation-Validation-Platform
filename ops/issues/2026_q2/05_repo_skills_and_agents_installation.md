# 仓库级 AGENTS 与 repo-side skills 安装入口

{{COORDINATOR_MENTION}} {{LSX_MENTION}} {{YANG_MENTION}}

这条 issue 用来统一团队对仓库级 `AGENTS.md` 与 repo-side skill pack 的安装、阅读和复用方式。

## 目标

- 让不同电脑都能同步同一套 repo 默认规则
- 让不同电脑都能复用同一批 repo-side skills
- 把“本地装过什么”变成“仓库里可追溯、可同步的资产”

## 当前入口

- `AGENTS.md`
- `docs/TEAM_AGENT_USAGE_CN.md`
- `docs/TEAM_SKILL_USAGE_CN.md`
- `docs/MAC_CODEX_WORKFLOW_CN.md`
- `ops/subagents/`
- `ops/skills/`

## 当前 skills

- `autoware-bug-report`
- `autoware-release-check`
- `carla-case-builder`
- `simctl-run-analysis`
- `ai-superbody-pmo`

## 当前约定

- `AGENTS.md` 负责仓库默认边界、优先级和输出风格
- `ops/subagents/` 负责可复用子agent规格
- `ops/skills/` 负责 repo-side 输出模板与工作套路
- 新电脑先拉仓库，再同步本地 Codex 安装，不要只从聊天里复制 prompt

## 建议阅读顺序

1. `README.md`
2. `AGENTS.md`
3. `docs/TEAM_AGENT_USAGE_CN.md`
4. `docs/TEAM_SKILL_USAGE_CN.md`
5. `docs/MAC_CODEX_WORKFLOW_CN.md`
6. `ops/subagents/`
7. `ops/skills/`

## 本地安装建议

如果已经有本地 Codex：

- 先备份 `~/.codex/AGENTS.md`
- 再把仓库内的 `AGENTS.md` 与 `ops/skills/` 作为同步源
- 让不同电脑都回到同一套 repo-side 规则

## 对两位同学的最小要求

### `{{LSX_MENTION}}`

- 至少知道 `carla-case-builder` 和 `autoware-bug-report` 在哪里
- 至少知道 `gaussian_reconstruction_explorer` 和 `execution_runtime_explorer` 的入口

### `{{YANG_MENTION}}`

- 至少知道 `simctl-run-analysis` 和 `carla-case-builder` 在哪里
- 至少知道 `public_road_e2e_shadow_explorer` 和 `algorithm_research_explorer` 的入口

## 当前验收

- 仓库里能看到 `AGENTS.md`
- 仓库里能看到 `ops/skills/`
- 仓库里能看到 `ops/subagents/`
- 团队成员能按仓库入口复用，而不是只靠本地聊天记录
