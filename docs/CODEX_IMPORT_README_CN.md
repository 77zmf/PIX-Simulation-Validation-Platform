# CODEX_IMPORT_README_CN.md

## 1. 这包文件是做什么的

这是一套给 Codex 用的**项目上下文 + 任务方案包**，目标是：

- 不改变你仓库的技术主线
- 让 Codex 一进仓库就知道当前主线、边界、任务路由和 done definition
- 把“仿真系统建议”转成可被 Codex 消费的 Markdown / JSON / TOML
- 在仓库已有 overlay 习惯的基础上，补一层更原生的 Codex 项目配置

## 2. 这包方案包含两种接入方式

### 方式 A：沿用当前仓库的 overlay 习惯
使用这些文件：
- `AGENTS.override.md`
- `codex_import_manifest.json`
- `docs/CODEX_PROJECT_SNAPSHOT_CN.md`
- `docs/CODEX_TASK_ROUTING_CN.md`
- `docs/PROJECT_PLAN_CODEX_READY_CN.md`
- `tasks/codex_backlog.json`

适合：
- 低风险接入
- 直接复用当前 repo 的阅读习惯
- 先让 Codex 理解项目，不急着做更大迁移

### 方式 B：使用更原生的 Codex 项目配置
额外合并这些文件：
- `.codex/config.toml`
- `.codex/agents/*.toml`

适合：
- 希望把 repo 内部 subagent 约定进一步迁到 Codex 项目级 custom agents
- 希望在 Codex 中更稳定地复用固定角色

## 3. 推荐放置方式

把本包内容复制到仓库根目录，保持相对路径不变。

建议目录结构如下：

```text
/
├─ AGENTS.override.md
├─ codex_import_manifest.json
├─ .codex/
│  ├─ config.toml
│  └─ agents/
├─ docs/
│  ├─ CODEX_PROJECT_SNAPSHOT_CN.md
│  ├─ CODEX_TASK_ROUTING_CN.md
│  ├─ PROJECT_PLAN_CODEX_READY_CN.md
│  └─ CODEX_IMPORT_README_CN.md
└─ tasks/
   └─ codex_backlog.json
```

如果仓库里已有同名文件，建议先人工 diff，再决定覆盖还是合并。

## 4. 导入后如何验证

把仓库根目录直接在 Codex App / CLI / IDE 中打开，然后发以下校验 prompt：

```text
Summarize the current repository instructions, the stable-line quarter priorities, and the top 3 blockers to turn launch_submitted into a final passed/failed validation result.
```

如果 Codex 的回答能稳定提到这些点，说明导入成功：
- company Ubuntu 22.04 runtime host
- stable closed loop first
- launch_submitted is not final
- public-road asset promotion
- shadow research must not block stable acceptance
- prefer extending simctl over one-off scripts

## 5. 推荐第一轮 prompt

### 面向稳定主线
```text
Read README.md, AGENTS.md, AGENTS.override.md, docs/CODEX_PROJECT_SNAPSHOT_CN.md, docs/CODEX_TASK_ROUTING_CN.md, docs/PROJECT_PLAN_CODEX_READY_CN.md, and tasks/codex_backlog.json.
Tell me the top 3 engineering blockers that prevent this repo from closing the real stable validation loop.
```

### 面向 finalize / evidence
```text
Focus on STABLE-001 and STABLE-002.
Read src/simctl/, evaluation/, infra/ubuntu/, and tests/.
Propose the smallest safe code change set to add finalize, runtime evidence, and host BOM persistence.
```

### 面向公开道路 case
```text
Focus on ASSET-001 and SCENARIO-001.
Read assets/manifests/, scenarios/, adapters/profiles/, evaluation/kpi_gates/, and relevant tools/.
Propose how to promote site_gy_qyhx_gsh20260310 into the first reusable public-road validation case.
```

### 面向报告与周会
```text
Read report/digest related code and docs.
Show how to split stable acceptance from shadow comparison, and align project status with validation status.
```

## 6. 本包的定位

这包内容适合：
- 让 Codex 快速理解项目
- 做工程收口
- 固化任务路由
- 固化 done definition
- 帮助你做 repo-side 的最小安全改造

这包内容不适合：
- 代替真实 Ubuntu 主机上的运行验证
- 代替真实日志和 artifacts
- 代替实时控制链
- 代替完整项目文档体系

## 7. 维护建议

每次主线目标变化时，优先更新：
- `AGENTS.override.md`
- `docs/CODEX_PROJECT_SNAPSHOT_CN.md`
- `tasks/codex_backlog.json`

每次任务路由变化时，更新：
- `docs/CODEX_TASK_ROUTING_CN.md`

每次阶段计划或 done definition 变化时，更新：
- `docs/PROJECT_PLAN_CODEX_READY_CN.md`
