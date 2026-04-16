# Codex 自动化架构（仓库导入版）

这套自动化不是把 Codex 放进实时仿真闭环，而是把 Codex 放在**仓库自动化层**，负责三类工作：

1. PR 代码评审
2. GitHub Project digest 梳理
3. 闭环状态审计（stub-safe）

## 1. 仓库内固定入口

- `AGENTS.override.md`：仓库级行为覆盖规则
- `.codex/config.toml`：Codex 项目配置
- `.agents/skills/`：可复用技能包
- `.github/codex/prompts/`：非交互式 prompt 模板
- `.github/workflows/`：GitHub Actions 自动化入口

## 2. 三条自动化链

### A. PR Review 链
`pull_request` -> `openai/codex-action@v1` -> `.github/codex/prompts/pr_review.md` -> PR 评论 + artifact

### B. Digest Triage 链
`schedule / workflow_dispatch` -> `simctl digest` -> `openai/codex-action@v1` -> blocker / owner next actions -> step summary + artifact

### C. Runtime Closure Audit 链
`workflow_dispatch` -> stub-safe `simctl run/report` -> `tools/codex/summarize_run_artifacts.py` -> `openai/codex-action@v1` -> 闭环缺口分析

## 3. 为什么这样设计

- 与当前仓库已有 `simctl`、`checks.yml`、`project_management.yml` 保持一致
- 不引入额外外部数据库
- 不把 AI 放进实时控制路径
- 让 Codex 只处理“代码、文档、验证、运营”这四类高价值重复工作

## 4. 与项目计划的对齐

这套自动化对齐当前项目计划的边界：
- 稳定闭环优先
- GitHub-only 项目运营
- AI 用于 digest、归因、文档、代码辅助
- 不做直接端到端控制接管
