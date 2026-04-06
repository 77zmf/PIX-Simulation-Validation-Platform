#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-cloud_workspace}"

mkdir -p "$TARGET_DIR"/{00_项目管理,01_需求管理,02_方案设计,03_研发实现,04_仿真与验证,05_风险与质量,06_归档}

cp workflow/templates/milestone_plan.csv "$TARGET_DIR/00_项目管理/"
cp workflow/templates/task_board.csv "$TARGET_DIR/03_研发实现/"
cp workflow/templates/risk_register.csv "$TARGET_DIR/05_风险与质量/"
cp workflow/templates/weekly_report.md "$TARGET_DIR/00_项目管理/"
cp workflow/templates/stage_acceptance_checklist.md "$TARGET_DIR/06_归档/"

cat <<MSG
✅ 已初始化超体计划工作流目录: $TARGET_DIR
- 已复制里程碑、任务看板、风险台账、周报、阶段验收模板
- 下一步：打开 workflow/runbook.md 按照“端到端执行步骤”开始执行
MSG
