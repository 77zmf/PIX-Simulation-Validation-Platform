# Codex 自动化架构（仓库导入版）

这套自动化不是把 Codex 放进实时仿真闭环，而是把 Codex 放在**仓库自动化层**，负责五类工作：

1. PR 代码评审
2. GitHub Project digest 梳理
3. 闭环状态审计（stub-safe）
4. CI 失败分诊
5. digest 二次叙事和 weekly-review 摘要

## 1. 仓库内固定入口

- `AGENTS.override.md`：仓库级行为覆盖规则
- `.codex/config.toml`：Codex 项目配置
- `.agents/skills/`：可复用技能包
- `.github/codex/prompts/`：非交互式 prompt 模板
- `.github/workflows/`：GitHub Actions 自动化入口

## 2. Repo-local skills

基础三件套：

- `repo-verification`
- `project-digest-triage`
- `runtime-closure-audit`

PIX 命名映射层：

- `pix-run-result-triage`
- `pix-host-readiness`
- `pix-project-digest`
- `pix-public-road-case-builder`

映射层的作用是把当前项目语言直接暴露给 Codex：run 结果、Ubuntu host、项目 digest、公路资产/场景构建。

## 3. 五条自动化链

### A. PR Review 链
`pull_request` -> `openai/codex-action@v1` -> `.github/codex/prompts/pr_review.md` -> PR 评论 + artifact

### B. Digest Triage 链
`schedule / workflow_dispatch` -> `simctl digest` -> `openai/codex-action@v1` -> blocker / owner next actions -> step summary + artifact

### C. Runtime Closure Audit 链
`workflow_dispatch` -> stub-safe `simctl run/report` -> `tools/codex/summarize_run_artifacts.py` -> `openai/codex-action@v1` -> 闭环缺口分析

### D. CI Failure Triage 链
`workflow_run failure / workflow_dispatch` -> `gh run view --log-failed` -> `openai/codex-action@v1` -> root cause / owner / smallest next action

### E. Digest Narration 链
`workflow_dispatch` -> digest artifact -> `openai/codex-action@v1` -> 面向 operator / weekly-review 的短摘要

## 4. 为什么这样设计

- 与当前仓库已有 `simctl`、`checks.yml`、`project_management.yml` 保持一致
- 不引入额外外部数据库
- 不把 AI 放进实时控制路径
- 让 Codex 只处理“代码、文档、验证、运营”这四类高价值重复工作
- 新增 CI triage 只读失败日志，不自动改代码、不自动开 issue，避免噪声
- 新增 digest narration 默认手动触发，先避免和现有 weekday digest 重复消耗

## 5. 与项目计划的对齐

这套自动化对齐当前项目计划的边界：
- 稳定闭环优先
- GitHub-only 项目运营
- AI 用于 digest、归因、文档、代码辅助
- 不做直接端到端控制接管
