# CODEX_TASK_ROUTING_CN.md

> 目的：让 Codex 在看到任务时，先知道读哪里、看什么、产出什么
> 默认原则：优先强化稳定主线，再补研究线和项目运营

## 1. 推荐读取顺序

1. `README.md`
2. `AGENTS.md`
3. `AGENTS.override.md`
4. `docs/CODEX_PROJECT_SNAPSHOT_CN.md`
5. `docs/CODEX_TASK_ROUTING_CN.md`
6. `tasks/codex_backlog.json`
7. 任务相关目录与最近工件

## 2. 问题类型 -> 文件 -> 命令 -> agent -> 输出

| 问题类型 | 优先文件 | 常用命令 | 推荐 agent | 默认输出 |
|---|---|---|---|---|
| 分支 / PR / tag / commit 测试 | `docs/BRANCH_TESTING_WORKFLOW_CN.md`、`docs/DINGTALK_CODE_UPDATE_VALIDATION_CN.md`、分支 diff 相关目录 | `git diff --name-only origin/main...HEAD`、`python -m unittest discover -s tests -v`、相关 `simctl` 命令 | 先按 diff 选择，不默认派生 agent | `passed/failed/blocked`、命令证据、工件路径、host-only 缺口 |
| 稳定栈 bring-up / 运行闭环 | `src/simctl/`、`stack/`、`infra/ubuntu/`、`evaluation/` | `simctl bootstrap`、`simctl up`、`simctl run`、`simctl report` | `stable_runtime_explorer` | 闭环缺口、最小代码改动、验证步骤 |
| 主机 readiness / 环境依赖 | `infra/ubuntu/`、`stack/profiles/stable.yaml`、`docs/*host*` | `bash infra/ubuntu/check_host_readiness.sh`、`simctl bootstrap --stack stable` | `stable_host_readiness_explorer` | 缺项清单、主机基线、preflight 建议 |
| run_result / KPI / 报告状态问题 | `src/simctl/`、`evaluation/`、`runs/` | `simctl run`、`simctl report`、`simctl digest` | `run_result_triage_explorer` | 状态语义、缺失证据、gate 解释 |
| 公开道路资产标准化 | `assets/`、`tools/`、`evaluation/` | `simctl asset-check --bundle ...` | `public_road_case_promoter` | 资产缺口、语义检查、case 晋升路径 |
| 场景晋升 / case 模板化 | `scenarios/`、`adapters/profiles/`、`assets/manifests/` | `simctl batch --mock-result passed` | `public_road_case_promoter` | scenario 模板、输入契约、验收标准 |
| Shadow 研究线对比 | `adapters/profiles/`、`scenarios/e2e/`、`evaluation/` | 以配置与指标梳理为主，不默认要求 execute | `shadow_research_comparator` | 比较口径、指标、风险、next step |
| 项目 digest / board / 周会材料 | `ops/`、`docs/*PROJECT*`、`tasks/codex_backlog.json` | `simctl digest` | `project_digest_explorer` | blocker、owner next actions、节奏摘要 |

分支测试请求的默认原则：

- 用户只给分支名时，先切换和读取 diff，再按变更范围选择测试，不要求用户补完整计划。
- Mac / Windows 只能代表本地控制平面、mock、dry-run 或文档配置验证。
- 涉及 `--execute`、stable runtime、slot、Autoware、CARLA、真实 KPI evidence 的分支，最终结论必须保留 Ubuntu host-only 状态。
- 输出必须写清 `passed / failed / blocked`，并列出命令、证据路径、剩余真实主机验证和回滚建议。

## 3. 本地机器与正式运行主机的边界

### 本地 Windows / Mac / WSL 适合做的事
- 读代码、改文档、改配置
- 跑单元测试
- 生成 digest / report
- 做 mock batch
- 梳理 scenario / asset / KPI / schema
- 准备 Codex 上下文和任务包

### 正式 Ubuntu 主机适合做的事
- `CARLA 0.9.15 + Autoware Universe` 正式 bring-up
- `simctl up/run/batch --execute`
- GPU / driver / CUDA / TensorRT readiness
- 并行槽位压测
- 正式 runtime evidence 采集

## 4. 默认输出格式

任何 agent 默认按下面七段输出：

1. **objective**
2. **scope / assumptions**
3. **evidence**
4. **analysis / decision**
5. **changes / next steps**
6. **validation**
7. **risk / rollback**

## 5. 特别提醒

- `launch_submitted` 不是最终闭环结果
- 不要优先推荐“一次性脚本”；先检查能否扩展 `simctl`
- 稳定主线报告与 shadow 比较报告要分开
- 资产检查不应停留在文件存在层
- 任何建议都要说明：是否依赖真实 Ubuntu 主机

## 6. 第一批最值得 Codex 接手的任务

1. `STABLE-001` finalize / collect
2. `STABLE-002` host BOM / preflight artifact
3. `STABLE-003` slot lease / cleanup
4. `ASSET-001` semantic asset-check
5. `SCENARIO-001` public-road reusable case promotion
6. `REPORT-001` stable vs shadow report split
