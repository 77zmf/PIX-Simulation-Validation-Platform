# 超体计划完整工作流程 Runbook

## 1) 角色与职责（RACI 简版）
| 活动 | 项目负责人 | PM | 技术负责人 | 模块TL | 验证负责人 |
|---|---|---|---|---|---|
| 云端初始化 | A | R | C | C | I |
| 范围冻结 | A | R | C | C | C |
| 里程碑验收口径 | A | C | R | C | C |
| 任务拆解与分派 | C | A | C | R | C |
| 周节奏推进 | C | A | C | R | R |
| 风险治理 | A | R | C | C | C |
| 阶段验收归档 | A | C | R | C | C |

> A=Accountable，R=Responsible，C=Consulted，I=Informed

## 2) 端到端执行步骤
1. **启动（D+0）**：执行 `scripts/bootstrap_workflow.sh` 初始化本地工作流目录并生成模板。
2. **对齐（D+1~D+2）**：使用 `workflow/templates/milestone_plan.csv` 完成里程碑与验收口径。
3. **拆解（D+2~D+3）**：在 `workflow/templates/task_board.csv` 建立任务卡并指定 DRI。
4. **运行（每周）**：按周一/周三/周五节奏更新任务与验证结论。
5. **治理（每周）**：更新 `workflow/templates/risk_register.csv` 并输出 `weekly_report.md`。
6. **验收（阶段末）**：使用 `workflow/templates/stage_acceptance_checklist.md` 完成阶段验收并归档。

## 3) 每周操作 SOP
### 周一（计划）
- 锁定本周目标（最多 3 个）
- 从看板拉取任务并确认依赖
- 输出：本周任务列表

### 周三（中检）
- 检查偏差（进度、质量、风险）
- 识别阻塞并指定清障责任人
- 输出：中检记录（问题/措施/负责人/截止时间）

### 周五（复盘）
- 汇总交付物、缺陷、验证结果
- 更新风险台账与下周优先事项
- 输出：周报与复盘结论

## 4) 交付件最小集合（必须有）
- 里程碑计划（milestone_plan.csv）
- 任务看板（task_board.csv）
- 风险台账（risk_register.csv）
- 周报（weekly_report.md）
- 阶段验收清单（stage_acceptance_checklist.md）

## 5) 完成定义（DoD）
满足以下条件即判定流程落地：
- 所有进行中任务具备 DRI、截止时间、验收标准。
- 本周验证结论可追溯到任务与版本。
- 风险台账当周已更新并标注负责人。
- 阶段验收清单全部勾选通过。
