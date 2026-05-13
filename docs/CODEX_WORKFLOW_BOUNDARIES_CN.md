# Codex 工作流边界

本文件把仓库级 Codex 工作边界收敛到 PIX Simulation Validation Platform 的稳定交付目标。它补充 `AGENTS.md` 和 `AGENTS.override.md`，不替代它们。

## 总原则

```text
GitHub 证明工程事实
Obsidian 沉淀长期知识和 evidence
Notion 展示当前状态和 next action
Codex 在明确边界内执行代码、文档、测试和 PR-ready 输出
```

## 最高优先级

stable validation evidence chain 永远优先：

```text
assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest
```

没有最终 artifact chain 时，不要把任务说成 stable `passed`。

## Stable / Shadow / Reconstruction 边界

### Stable line

- Ubuntu 22.04 formal runtime host
- ROS 2 Humble
- Autoware Universe
- CARLA 0.9.15
- UE4.26
- `simctl bootstrap / up / run / batch / replay / report / digest`
- KPI-gated regression

只有具备 runtime artifacts、KPI gate、report/replay 的内容，才能作为 formal stable evidence。

### Shadow line

- BEVFusion
- UniAD-style shadow
- VADv2 comparison
- E2E / world-model / embodied-intelligence comparison

Shadow 输出只能作为 hypothesis、comparison 或 risk analysis，不能替代 stable acceptance。

### Reconstruction line

- PCD / Lanelet2 / pose prior
- mesh / PLY / OpenDRIVE / collision proxy
- 3DGS / 4DGS / NuRec / 3DGUT exploration

Reconstruction 支持 stable assets，但不能阻塞本季度 stable delivery。

## Codex Task 标准边界

对 runtime、vehicle、sync、repo cleanup、workflow 或 prompt 变更，任务开始前应明确：

```md
## Goal

## Context

## Allowed Files

## Forbidden Files

## Verification

## Expected Output

## No-Go Rules

## Risk
```

## 完成输出

Codex 完成任务后优先使用：

```md
## Summary

## Files Changed

## Verification

## Evidence

## Blockers

## Next Action

## Risk
```

分析-only 时必须写：

```text
No files changed. Analysis only.
```

## 禁止事项

- 不要把 plan 当 done。
- 不要把 Notion status 当 evidence。
- 不要把 Mac stub 当 formal runtime evidence。
- 不要把 `launch_submitted` 当 final acceptance。
- 不要混淆 stable / shadow / reconstruction 结论。
- 不要把大地图、点云、checkpoint、raw logs、generated artifacts 放入 Git。
- 不要执行 reset、clean、force push、删除、sudo，除非用户明确要求。

## 推荐入口

- Dirty worktree / PR split：`.codex/prompts/repo_triage.md`
- 执行安全检查：`.codex/checklists/safety_checklist.md`
- Stable validation 验收：`.codex/checklists/stable_validation_checklist.md`
- PR review：`.github/codex/prompts/pr_review.md`
- Runtime closure：`.github/codex/prompts/runtime_closure_audit.md`
