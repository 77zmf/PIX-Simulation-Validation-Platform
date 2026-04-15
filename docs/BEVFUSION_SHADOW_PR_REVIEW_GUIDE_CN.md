# BEVFusion Shadow PR Review Guide

对应 issue：

- [#10 BEVFusion 基线与 Shadow E2E 研究计划](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/10)

这份文档是短期 `review handoff`，目标不是长期保存所有状态，而是帮助当前 reviewer 在 `PR #28 ~ #32` 之间快速建立顺序感、范围感和 blocker 边界。

更新时间：

- `2026-04-15`

## 1. 当前 draft PR 一览

| PR | 主题 | 结论 | 建议优先级 |
| --- | --- | --- | --- |
| [#28](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/28) | `BEVFusion -> shadow planner` 契约、共享指标、report 汇总、Ubuntu execute runbook | 主研究线核心交付 | `P0` |
| [#29](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/29) | 远端 GPU 资源清单与 UE4 阻塞说明 | 解释当前 runtime blocker | `P1` |
| [#30](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/30) | 远端 GPU 访问方案 | 解释主机访问路径和 runner 边界 | `P1` |
| [#31](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/31) | 杨志朋阅读纪要 | 补齐阅读线 repo-side 交付 | `P2` |
| [#32](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/32) | 研究状态快照 | 解释整条线现在到哪一步 | `P2` |

## 2. 推荐 review / merge 顺序

如果当前目标是“先把 repo-side 收口，再等 Ubuntu 主机回执”，推荐顺序是：

1. [PR #28](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/28)
2. [PR #29](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/29)
3. [PR #30](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/30)
4. [PR #31](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/31)
5. [PR #32](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/32)

原因：

- `#28` 是主研究线本体，不先看它，后面的状态文档和 blocker 文档会失去中心。
- `#29 / #30` 是“为什么现在还没法做正式 runtime 验收”的配套说明，适合紧跟 `#28`。
- `#31 / #32` 更偏阅读与状态管理，重要，但不阻塞接口和执行路径本身。

## 3. 每个 PR reviewer 最该看什么

### PR #28

优先看：

- `BEVFusion` 输出契约是否真的能映射到 `shadow planner` 输入
- `UniAD-style / VADv2` 是否真的共享同一套 comparison metrics
- `simctl report` 产出的 `Shadow Comparison / Comparison Gaps / Gate Verdicts / issue_update.md` 是否足以支撑 issue 回贴
- 文档里有没有把 mock 结论说成真实 runtime 结论

如果 reviewer 只看一个 PR，应该先看它。

### PR #29

优先看：

- 当前资源信息和阻塞项是否基于真实已有回执，而不是猜测
- UE4 / CARLA / GPU / nvcc / TensorRT 的 blocker 是否写清楚了“已确认”和“未确认”
- 下一步依赖是否足够具体

### PR #30

优先看：

- 当前推荐访问路径是否足够保守且可执行
- `Tailscale + OpenSSH` 是否写成当前默认方案
- self-hosted runner 是否被正确限定为“非前置条件”

### PR #31

优先看：

- 阅读结论是否回指到了仓库里的 profile、scenario、KPI gate
- `Hydra-MDP / Hydra-NeXt / MomAD` 是否被错误提升成当前季度实现主线

### PR #32

优先看：

- 是否把当前主线、blocker、合并顺序写清楚
- 是否和 `#28 ~ #31` 的实际状态保持一致
- 是否把“还缺 Ubuntu 主机回执”说成了当前唯一主 blocker

## 4. 哪些内容现在可以 merge，哪些不能假装完成

### 现在可以 merge 的

- 契约文档
- 指标口径
- report 汇总逻辑
- Ubuntu execute runbook
- 远端资源/访问说明
- 阅读纪要和状态快照

### 现在不能假装已经完成的

- 真正的 Ubuntu 主机 runtime 验收
- `shadow` 路线的正式 closed-loop 结论
- `SSH / Tailscale / CarlaUE4.sh / runner` 的最新实时状态

## 5. 从 draft 切到 ready for review 的最低条件

### PR #28

- reviewer 接受“当前结论是 repo-side + mock/control-plane 结论，不是 runtime 验收结论”
- 对契约、指标和 report 汇总没有结构性异议

### PR #29 / #30

- reviewer 接受当前 blocker 表述方式
- reviewer 认可“先说明现状，再等主机回执”的节奏

### PR #31 / #32

- reviewer 认可阅读结论和状态快照没有越权下 runtime 结论
- reviewer 认可文档入口位置和当前问题范围匹配

## 6. reviewer 最容易误判的点

- 把 mock / docs / report 工具准备误读成“真实 execute 已完成”
- 把阅读线结论误读成“下一季度一定要实现 Hydra 路线”
- 把远端访问方案误读成“当前已经能 SSH 上主机”

## 7. 当前最推荐的 reviewer 操作方式

如果 reviewer 时间很有限，建议这样看：

1. 先看 [PR #28](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/28)
2. 再看 [PR #29](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/29) 和 [PR #30](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/30)
3. 最后看 [PR #31](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/31) 和 [PR #32](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/32)

如果 reviewer 希望先统一认知，再逐个看 PR，推荐先读：

- `docs/BEVFUSION_SHADOW_PR_REVIEW_GUIDE_CN.md`
- `docs/BEVFUSION_SHADOW_RESEARCH_STATUS_CN.md`

再进入具体 PR。

## 8. review 完成后的真正下一步

就算 `#28 ~ #32` 全部 merge，也只代表 repo-side 收口完成。

真正的下一步仍然是：

```bash
simctl run --scenario scenarios/l2/perception_bevfusion_public_road_occlusion.yaml --run-root runs --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml --run-root runs --slot stable-slot-01 --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml --run-root runs --slot stable-slot-02 --execute
simctl report --run-root runs
```

只有这一步回填之后，`shadow` 研究线才会从“repo-side 已准备好”进入“runtime 验收开始成立”。
