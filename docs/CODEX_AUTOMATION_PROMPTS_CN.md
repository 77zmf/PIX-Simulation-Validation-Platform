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

## 4. CI 失败分诊

```text
Use the `pix-run-result-triage`, `pix-host-readiness`, and `repo-verification` skills as relevant.
Read the failed workflow logs and summarize: failure summary, evidence, likely root cause, impact, owner next action, and verification.
Separate repo-code failures from runner, token, secret, dependency, or external-service failures.
Do not imply real Ubuntu runtime-host validation failed when the evidence is only stub CI.
```

## 5. Digest 二次叙事

```text
Use the `pix-project-digest` skill.
Read the latest project digest and produce an operator-facing summary: blockers, owner next actions, validation signal, and the top 3 moves for the next work session.
Label each item as stable validation, public-road asset/scenario work, shadow/research, or reconstruction support.
```

## 6. 公路案例构建

```text
Use the `pix-public-road-case-builder` skill.
Turn this field finding or asset bundle into a traceable scenario draft with source assets, owner, route/site section, assumptions, KPI hook, replay/report plan, missing inputs, and rollback/exclusion impact.
```

## 7. Ubuntu host readiness

```text
Use the `pix-host-readiness` skill.
Check whether the company Ubuntu 22.04 runtime host is ready for stable Autoware + CARLA validation.
Return readiness verdict, evidence found, blocking gaps, exact commands to run next, validation scenario, expected observable, rollback note, and owner action.
```

## 8. Codex App 自动化建议

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

### 每周 review prep 自动化
提示词：
```text
$pix-project-digest
Read the latest digest and prepare a weekly review inbox item with milestone status, blockers, stable/shadow/reconstruction labels, owner next actions, decisions needed, and the top 3 next-week moves.
```

说明：
- 技能负责“方法”，自动化负责“调度”
- 真正上 schedule 前，先在普通线程手工跑一遍，确认输出稳定
