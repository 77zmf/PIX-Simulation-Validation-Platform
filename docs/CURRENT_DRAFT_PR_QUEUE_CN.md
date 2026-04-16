# 当前 Draft PR 队列与合并建议

对应 issue：

- `#8 [Q2] 主线仓库整理与执行口径收口`

本文档不是新的研究结论，也不是新的 runtime 方案。它只回答一个更实际的问题：

- 当前 `77zmf/PIX-Simulation-Validation-Platform` 里的 `draft PR #28 ~ #35` 分别在做什么
- 哪些 PR 可以直接开始 review
- 哪些 PR 虽然 repo-side 已经完成，但正式验收仍然受 Ubuntu 主机回执阻塞
- 如果维护者现在只想尽快降低 open draft 数量，先看哪几条最省成本

更新时间：

- `2026-04-16`

## 1. 当前队列

| PR | 对应 issue | 范围 | 类型 | 当前状态 | Ubuntu 主机依赖 | reviewer 先看什么 |
| --- | --- | --- | --- | --- | --- | --- |
| `#28` | `#5`, `#10` | `BEVFusion / shadow` 契约、指标、report、runbook | repo-side 功能 + 文档 | repo-side 已完成，仍缺正式 execute 回填 | `是` | 配置契约、shared metrics、`simctl report` 输出、runbook 是否清晰 |
| `#29` | `#26` | 远端 GPU 资源清单、UE4 blocker 说明 | 文档 | 可直接 review | `否` | 当前资源信息、缺项说明、blocker 是否准确 |
| `#30` | `#25` | 远端 GPU 访问方案 | 文档 | 可直接 review | `否` | `Tailscale + OpenSSH` 路径是否清楚，边界是否写明 |
| `#31` | `#7` | 杨志朋阅读纪要 | 文档 | 可直接 review | `否` | 论文整理是否贴当前主线，是否把结论落回 repo 语境 |
| `#32` | `#10` | `BEVFusion / shadow` 研究状态快照 | 文档 | 可直接 review | `否` | 当前主线、blocker、后续里程碑是否讲清楚 |
| `#33` | `#10` | `BEVFusion / shadow` PR review guide | 文档 | 可直接 review | `否` | review 顺序和重点是否有助于收口 |
| `#34` | `#12` | Windows 侧 Codex 工作流与同步入口 | 文档 + 脚本 | 可直接 review | `否` | Windows 协作边界是否清楚，同步脚本是否保守安全 |
| `#35` | `#11` | 子 agent onboarding profile 与起手入口 | repo-side 小功能 + 文档 | 可直接 review | `否` | `simctl subagent-spec --list-onboarding/--onboarding` 是否直观、profile 是否可复用 |

## 2. 建议不要混在一起看的点

这些 PR 不是同一类东西，建议按下面的边界区分：

- `#28`
  - 是当前队列里最像“功能交付”的一条，不只是补文档。
  - 它决定了 `BEVFusion -> shadow` 这条 repo-side 路线是否算真正冻结下来。
- `#29`, `#30`
  - 是主机 / 远端访问说明，不解决 runtime 本身，但把当前缺口和建议路径写清楚。
- `#31`, `#32`, `#33`
  - 是研究与 review 支撑材料，帮助读懂主线，不替代功能验收。
- `#34`, `#35`
  - 是团队协作入口，重点是“不同电脑上怎么复用 repo-side Codex 资产”。

## 3. 推荐 review bucket

### Bucket A：先降低 open draft 数量

这几条基本不依赖外部环境，可以优先 review：

- `#34`
- `#35`
- `#29`
- `#30`

适用场景：

- 维护者想先消化低风险、低耦合的 repo-side 改动
- 当前还拿不到公司 Ubuntu 主机，不想让整批 PR 都卡住

### Bucket B：研究线说明材料

这几条适合在 `BEVFusion / shadow` 方向已经确认继续推进时 review：

- `#31`
- `#32`
- `#33`

适用场景：

- 维护者已经接受当前研究线仍以 `BEVFusion` 为基线
- 希望把论文、状态快照、PR review 顺序一起补齐

### Bucket C：核心 repo-side 交付

这条最值得重点看，但也最容易被“正式回执未完成”影响判断：

- `#28`

这里要分清两件事：

- `repo-side 是否已经收口`
- `正式 execute 验收是否已经收口`

当前结论是：

- `#28` 的 repo-side 交付已经齐了
- 但正式 execute 验收仍然卡在公司 Ubuntu 主机

所以 reviewer 在看这条时，最好明确表态下面二选一：

1. 先接受 repo-side 冻结，允许在正式主机回执回来前先合并文档 / 配置 / report 侧改动
2. 保持 draft，等真实 `--execute` 回填后再转 ready

## 4. 推荐 review 顺序

如果 reviewer 想最少上下文切换，我建议按下面顺序看：

1. `#28`
2. `#29`
3. `#30`
4. `#31`
5. `#32`
6. `#33`
7. `#34`
8. `#35`

原因：

- 先看 `#28`，可以先判断这轮 `BEVFusion / shadow` repo-side 交付是否成立
- 再看 `#29/#30`，就能知道为什么当前还缺正式回执
- 再看 `#31/#32/#33`，研究线的摘要和 review guide 才不会脱离上下文
- `#34/#35` 可以并行看，因为它们更偏团队协作入口，不会影响运行时判断

如果 reviewer 的目标不是“先吃主线”，而是“先快速关闭低风险 draft”，也可以反过来先看：

1. `#34`
2. `#35`
3. `#29`
4. `#30`
5. `#31`
6. `#32`
7. `#33`
8. `#28`

## 5. 当前最推荐的 maintainer 动作

如果今天只能做很少的 review，我建议：

1. 先 review `#34` 和 `#35`
2. 再 review `#29` 和 `#30`
3. 然后决定 `#28` 是“先并 repo-side”还是“继续等 execute 回执”

这样做的好处是：

- 先把协作入口和主机说明收掉
- 不会把所有 PR 都压在 Ubuntu 主机 availability 上
- 等 `#28` 真要转 ready 时，周边材料已经齐了

## 6. 当前 blocker 只剩哪一个

截至 `2026-04-16`，当前这批 PR 真正共享的外部 blocker 只有一个：

- 公司 Ubuntu 主机上的真实 `simctl run --execute` 回填

这会影响：

- `#28` 的正式验收闭环

但不会阻止以下事情先推进：

- 团队工作流文档与脚本
- 子 agent onboarding
- 远端访问说明与 blocker 清单
- 研究阅读与状态快照

## 7. 结论

当前队列不适合再继续无上限开新 draft PR。更合适的动作是：

- 先按 bucket 吃掉已经开的 `#28 ~ #35`
- 对 `#28` 明确“repo-side 先合并”还是“继续等待 execute 回填”的口径
- 拿到公司 Ubuntu 主机后，再把真正卡在正式回执上的部分推进到 ready
