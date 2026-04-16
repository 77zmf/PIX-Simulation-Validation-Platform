# Codex App / CLI 可直接复用的自动化提示词

这些提示词可以直接在 Codex App、CLI 或 IDE 中使用。

## 1. PR 审查

```text
Use the `repo-verification` skill.
Review the current branch diff for regression risk.
Focus on exact files, missing verification, and whether the diff weakens or strengthens:
assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest
Return: verdict, major findings, validation gaps, suggested commands, merge conditions.
```

## 2. 每日 Digest 梳理

```text
Use the `project-digest-triage` skill.
Build or read the current digest from ops/project_automation.yaml.
Summarize top blockers, due-soon work, owner next actions, latest validation signal, and top 3 moves for the next session.
```

## 3. 闭环差距审计

```text
Use the `runtime-closure-audit` skill.
Audit the latest local or stub-safe run artifacts.
Tell me which links are present or missing in:
assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest
Then tell me the single next step that most improves closure.
```

## 4. Codex App 自动化建议

建议在 Codex App 里设置两类自动化：

### 工作日早晨 digest 自动化
提示词：
```text
$project-digest-triage
Read the latest digest and produce blockers, due-soon items, owner next actions, and the top 3 moves for today.
```

### 每周一次 runtime closure 自动化
提示词：
```text
$runtime-closure-audit
Audit whether the repo is showing a real closed loop or only a launch/report loop. Use exact artifacts and say the next code/config step.
```

说明：
- 技能负责“方法”，自动化负责“调度”
- 真正上 schedule 前，先在普通线程手工跑一遍，确认输出稳定
