# BEVFusion Shadow E2E 研究状态快照

对应 issue：

- [#10 BEVFusion 基线与 Shadow E2E 研究计划](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/10)
- [#5 P1 感知与 Shadow E2E：BEVFusion 接口与指标口径](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/5)
- [#7 论文整理：公开道路感知、Shadow E2E 与三维重建阅读清单](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/7)
- [#25 明确远端 GPU 节点规格与访问方案](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/25)
- [#26 输出远端 GPU 资源清单与 UE4 阻塞说明](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/26)

更新时间：

- `2026-04-20`

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
- `docs/BEVFUSION_SHADOW_INTERFACE_BASELINE_CN.md`
- `docs/BEVFUSION_SHADOW_UBUNTU_EXECUTE_RUNBOOK_CN.md`
- `docs/REMOTE_GPU_RESOURCE_AND_UE4_BLOCKERS_CN.md`
- `docs/REMOTE_GPU_ACCESS_PLAN_CN.md`

这些内容已经足够说明研究总路线、论文入口、接口合同、Ubuntu 执行入口、远端 GPU 资源口径和访问方案。

### 已完成 repo-side 合并

| 主题 | 当前状态 | 入口 |
| --- | --- | --- |
| `BEVFusion -> shadow planner` 契约、对照指标、report 汇总、Ubuntu execute runbook | 已合入 `main`，merge commit `1a6c3cb` | [PR #28](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/28) |
| 远端 GPU 资源清单与 UE4 阻塞说明 | 已合入 `main`，merge commit `2118bfd` | [PR #29](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/29) |
| 远端 GPU 访问方案 | 已合入 `main`，merge commit `d296e47` | [PR #30](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/30) |

### 仍在 repo-side 收口队列

| 主题 | 当前状态 | 入口 |
| --- | --- | --- |
| BEVFusion Shadow 研究状态快照 | 本文档，准备从 Draft 转 ready | [PR #32](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/32) |
| 杨志朋 Shadow 阅读纪要 | 仍需基于最新 `main` 复核和解冲突 | [PR #31](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/31) |
| BEVFusion Shadow PR review guide | 需要按 #28/#29/#30 已合并事实更新，否则内容会过期 | [PR #33](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/33) |

### 当前明确 blocked

- 真实 `--execute` 结果还没回填到 issue `#27`。
- `BEVFusion` 输出样例、`UniAD-style / VADv2` shadow 对比样例、`run_result/report/summary` 仍需要公司 Ubuntu 主机正式产物。
- `SSH / Tailscale / CarlaUE4.sh / runner` 的最终实时证据仍需用现场命令补齐；repo-side 访问方案与资源清单已经完成。

## 3. 这条研究线当前已经完成到哪里

### Executable

- 已明确当前研究主线不是“直接 takeover”，而是“旁路比较”。
- 已明确第一阶段比较对象是 `UniAD-style shadow` 和 `VADv2 shadow`。
- 已把 `BEVFusion -> shadow planner` 接口合同、profile、KPI gate、report/issue_update 输出和 Ubuntu runbook 合入 `main`。
- 已把远端 GPU/UE4 blocker inventory 与 Tailscale/OpenSSH 访问方案合入 `main`。
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

## 4. 当前最重要的收口顺序

截至 `2026-04-20`，repo-side 主合同已经完成合并。接下来推荐顺序是：

1. 合并本文档对应的 [PR #32](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/32)，把研究状态快照更新到当前真实状态。
2. 复核并收口 [PR #31](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/31)，把杨志朋阅读纪要与当前接口合同对齐。
3. 复核 [PR #33](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/33)，如果仍保留 review guide，需要改成“已合并后的复盘/后续检查清单”，不要继续写旧的 draft merge 顺序。
4. 拿到公司 Ubuntu 主机后，集中推进 issue [#27](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/27) 的真实 runtime evidence。

原因：

- `#28 / #29 / #30` 已经完成主研究线、资源清单和访问方案收口。
- `#31 / #32 / #33` 属于状态、阅读和 review 管理层，不应阻塞 runtime evidence。
- `#27` 才是下一阶段真正需要公司主机产物的验收入口。

## 5. 拿到 Ubuntu 主机后的首个对比里程碑

第一批真实执行应该只跑这 3 条：

```bash
bash infra/ubuntu/check_host_readiness.sh
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
- 不建议把已经完成的 #28/#29/#30 继续当作 draft 阻塞项讨论；后续讨论应转向真实运行证据。

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
