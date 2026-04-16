# 如何把这套文档导入 Codex

## 1. 这包文件是做什么的
这是一套给 Codex 用的“项目上下文覆盖层”，目标是：
- 不改动你现有项目逻辑
- 让 Codex 一进仓库就理解当前季度主线、边界、任务路由和验收口径
- 让 Word 版项目计划变成 Codex 更容易消费的 Markdown 结构

## 2. 推荐放置方式
如果你的仓库已经有根目录 `AGENTS.md`，**优先使用本包里的 `AGENTS.override.md`**。  
这样可以在不删现有 `AGENTS.md` 的前提下，让 Codex 在同一目录优先读取覆盖规则。

建议目录结构：

```text
<repo-root>/
  AGENTS.md                # 仓库已有
  AGENTS.override.md       # 使用本包
  docs/
    CODEX_PROJECT_SNAPSHOT_CN.md
    PROJECT_PLAN_CODEX_READY_CN.md
    CODEX_TASK_ROUTING_CN.md
    CODEX_IMPORT_README_CN.md
  codex_import_manifest.json
```

## 3. 导入步骤
1. 备份现有仓库工作区。
2. 把本包内文件复制到仓库根目录。
3. 确认 `AGENTS.override.md` 位于 repo root。
4. 在 Codex App / CLI / IDE 中直接打开该仓库根目录。
5. 启动后先发一条校验 prompt：

```text
Summarize the current repository instructions and quarter priorities.
```

如果返回里能提到：
- company Ubuntu 22.04 runtime host
- stable closed loop first
- simctl workflow
- public-road asset reuse
- shadow research must not block mainline

说明导入成功。

## 4. 推荐第一轮 prompt
### 面向项目总览
```text
Read README.md, AGENTS.md, AGENTS.override.md, docs/CODEX_PROJECT_SNAPSHOT_CN.md, and docs/CODEX_TASK_ROUTING_CN.md. Then tell me the top 3 blockers to close the stable validation loop.
```

### 面向主机 bring-up
```text
Read docs/TOMORROW_COMPANY_HOST_CHECKLIST_CN.md, infra/ubuntu/, and stack/profiles/stable.yaml. Give me a host-readiness checklist and the smallest safe validation plan.
```

### 面向 run_result/report
```text
Read src/simctl/, evaluation/kpi_gates/, and the latest run_result/report artifacts. Explain why the run is not yet a true closed loop and what finalize/collect step is missing.
```

### 面向项目管理
```text
Read docs/PROJECT_MANAGEMENT_OVERVIEW_CN.md and ops/project_automation.yaml. Summarize current digest automation assumptions and tell me which board fields are critical.
```

## 5. 这套文档适合什么，不适合什么
适合：
- 让 Codex 快速理解项目
- 让 Word 项目计划变成 repo-friendly 的 Markdown
- 让任务路由、边界和 done definition 更稳定

不适合：
- 代替真实运行日志和工件
- 代替 Ubuntu 主机上的正式验证
- 代替原仓库完整文档体系

## 6. 后续维护建议
- 每次季度目标变化时，只更新 `AGENTS.override.md` 和 `docs/CODEX_PROJECT_SNAPSHOT_CN.md`
- 每次任务路由变化时，更新 `docs/CODEX_TASK_ROUTING_CN.md`
- 需要保留计划书细节时，更新 `docs/PROJECT_PLAN_CODEX_READY_CN.md`
