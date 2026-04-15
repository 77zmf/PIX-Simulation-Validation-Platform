# BEVFusion Shadow E2E 研究状态快照

对应 issue：

- [#10 BEVFusion 基线与 Shadow E2E 研究计划](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/10)
- [#5 P1 感知与 Shadow E2E：BEVFusion 接口与指标口径](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/5)
- [#7 论文整理：公开道路感知、Shadow E2E 与三维重建阅读清单](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/7)
- [#25 明确远端 GPU 节点规格与访问方案](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/25)
- [#26 输出远端 GPU 资源清单与 UE4 阻塞说明](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/26)

更新时间：

- `2026-04-15`

这份文档不是重新定义算法路线，而是把当前仓库里和 `BEVFusion / Shadow E2E` 相关的 repo-side 交付、阻塞项和下一步执行顺序收成一页纸，方便 issue `#10` 持续同步。

## 1. 当前结论

- 当前主线已经收口为 `BEVFusion -> UniAD-style shadow / VADv2 shadow`。
- `shadow` 在当前阶段仍然只是 `observation_only`，不接管 stable 主链控制。
- 当前最缺的不是新的论文结论，而是公司 Ubuntu 主机上的真实 `--execute` 回填。

## 2. 当前仓库内的状态划分

### 已在默认分支可见

- `docs/ALGORITHM_RESEARCH_ROADMAP_CN.md`
- `docs/PAPER_READING_MAP_CN.md`
- `docs/PAPER_LANDSCAPE_CN.md`
- `docs/LOCAL_PDF_INDEX_CN.md`

这些内容已经足够说明研究总路线、论文入口和分类结构。

### 已形成 repo-side 交付，但仍在 Draft PR

| 主题 | 当前状态 | 入口 |
| --- | --- | --- |
| `BEVFusion -> shadow planner` 契约、对照指标、report 汇总、Ubuntu execute runbook | `Draft PR #28` | [PR #28](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/28) |
| 远端 GPU 资源清单与 UE4 阻塞说明 | `Draft PR #29` | [PR #29](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/29) |
| 远端 GPU 访问方案 | `Draft PR #30` | [PR #30](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/30) |
| 杨志朋 Shadow 阅读纪要 | `Draft PR #31` | [PR #31](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/31) |

### 当前明确 blocked

- 公司 Ubuntu 主机没有新的回执。
- 真实 `--execute` 结果还没回填。
- `SSH / Tailscale / CarlaUE4.sh / runner` 还没有新的实时确认。

## 3. 这条研究线当前已经完成到哪里

### Executable

- 已明确当前研究主线不是“直接 takeover”，而是“旁路比较”。
- 已明确第一阶段比较对象是 `UniAD-style shadow` 和 `VADv2 shadow`。
- 已明确共享指标口径应该至少覆盖：
  - `route_completion`
  - `collision_count`
  - `trajectory_divergence_m`
  - `min_ttc_sec`
  - `planner_disengagement_triggers`
- 已明确阅读输出需要回指到 profile、scenario、KPI gate，而不是停留在论文摘要。

### Placeholder

- `Hydra-MDP / Hydra-NeXt / MomAD` 当前仍然只作为中期观察名单。
- 它们还没有进入当前季度的默认实现队列。

### Blocked

- 真实 runtime 验收仍然依赖公司 Ubuntu 22.04 主机。
- 目前还不能对 `shadow` 路线给出正式 closed-loop 结论，只能给出 repo-side 和 mock/control-plane 结论。

## 4. 当前最重要的合并顺序

如果现在先做 repo-side 收口，不等 Ubuntu 主机，推荐合并顺序是：

1. [PR #28](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/28)
2. [PR #29](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/29)
3. [PR #30](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/30)
4. [PR #31](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/31)

原因：

- `#28` 是主研究线的核心 repo-side 契约和指标交付。
- `#29 / #30` 负责解释为什么当前还不能正式回填 runtime 验收。
- `#31` 是阅读线的补强，重要但不阻塞主线接口和执行路径。

## 5. 拿到 Ubuntu 主机后的首个对比里程碑

第一批真实执行应该只跑这 3 条：

```bash
simctl run --scenario scenarios/l2/perception_bevfusion_public_road_occlusion.yaml --run-root runs --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml --run-root runs --slot stable-slot-01 --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml --run-root runs --slot stable-slot-02 --execute
```

完成后立刻执行：

```bash
simctl report --run-root runs
```

首个里程碑不是“宣布 E2E 已经 ready”，而是确认：

- `BEVFusion` 输出是否真的能稳定映射到 shadow planner 输入
- `UniAD-style / VADv2` 是否能用同一套共享指标对比
- `Shadow Comparison / Comparison Gaps / Gate Verdicts` 是否足以支撑 issue 回贴

## 6. 现在不建议做的事

- 不建议在 Ubuntu 主机回执缺失时继续扩新的 planner 实现分支。
- 不建议在 stable 闭环未补齐前引入新的感知主线替代 `BEVFusion`。
- 不建议把 `Hydra-MDP / Hydra-NeXt / MomAD` 提前拉入当前季度实现主线。

## 7. issue #10 的下一步同步格式

后续在 issue `#10` 下同步时，建议固定用这 5 行结构：

```text
当前研究结论：
- ...

当前 repo-side 交付：
- ...

当前 blocker：
- ...

下一步执行：
- ...

对应 PR / 结果入口：
- ...
```

这样可以把 `#10` 维持成总线状态 issue，而不是把细节散落到多个评论里。
