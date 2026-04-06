# PIX-Simulation-Validation-Platform

## 超体计划完整工作流程（云端执行版）

你要的不只是说明文档，这里已提供 **可直接执行的完整工作流程包**：

1. **流程引擎定义（机器可读）**：`workflow/process.yaml`
2. **人工执行手册（Runbook）**：`workflow/runbook.md`
3. **可直接落地模板**：`workflow/templates/*`
4. **一键初始化脚本**：`scripts/bootstrap_workflow.sh`

---

## 快速开始（3 步）

### 步骤 1：初始化云端工作目录
```bash
./scripts/bootstrap_workflow.sh
```

默认会生成 `cloud_workspace/` 目录，包含：
- `00_项目管理`、`01_需求管理`、`02_方案设计`、`03_研发实现`、`04_仿真与验证`、`05_风险与质量`、`06_归档`

### 步骤 2：按流程推进
- 按 `workflow/process.yaml` 的阶段门禁（S0~S4）执行
- 按 `workflow/runbook.md` 的周节奏（周一计划、周三中检、周五复盘）运行

### 步骤 3：用模板驱动执行
- 里程碑计划：`workflow/templates/milestone_plan.csv`
- 任务看板：`workflow/templates/task_board.csv`
- 风险台账：`workflow/templates/risk_register.csv`
- 周报模板：`workflow/templates/weekly_report.md`
- 阶段验收清单：`workflow/templates/stage_acceptance_checklist.md`

---

## 交付成果定义（DoD）

当以下 5 项全部满足，视为“超体计划工作流程落地完成”：
- 进行中任务具备 DRI、截止时间、验收标准。
- 验证结论可追溯到任务卡与版本。
- 风险台账每周更新且有责任人。
- 周报连续输出并可回溯。
- 阶段验收清单全部通过并归档。
