# BEVFusion Shadow 合并后 Review 检查清单

对应 issue：

- [#10 BEVFusion 基线与 Shadow E2E 研究计划](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/10)
- [#27 建立 BEVFusion 公开道路感知基线与 planner 接口评测](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/27)

更新时间：

- `2026-04-20`

这份文档最初用于 `PR #28 ~ #32` 的 review handoff。当前这些核心 repo-side PR 已经陆续合入 `main`，所以本文档更新为“合并后检查清单”：帮助 reviewer 快速确认哪些内容已经完成，哪些内容仍然不能假装成 runtime 验收。

## 1. 当前已合并交付

| PR | 主题 | 当前结论 |
| --- | --- | --- |
| [#28](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/28) | `BEVFusion -> shadow planner` 契约、共享指标、report 汇总、Ubuntu execute runbook | 已合入 `main`，主研究线 repo-side 合同完成 |
| [#29](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/29) | 远端 GPU 资源清单与 UE4 阻塞说明 | 已合入 `main`，资源/阻塞说明完成 |
| [#30](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/30) | 远端 GPU 访问方案 | 已合入 `main`，`Tailscale + OpenSSH` 路径完成 |
| [#32](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/32) | BEVFusion Shadow 研究状态快照 | 已合入 `main`，状态快照更新到当前事实 |
| [#31](https://github.com/77zmf/PIX-Simulation-Validation-Platform/pull/31) | 杨志朋 Shadow E2E 阅读纪要 | 已合入 `main`，链接统一到 `77zmf` 仓库 |

## 2. Reviewer 现在最该看什么

### 接口合同是否稳定

- `docs/BEVFUSION_SHADOW_INTERFACE_BASELINE_CN.md`
- `adapters/profiles/perception_bevfusion_public_road.yaml`
- `adapters/profiles/e2e_bevfusion_uniad_shadow.yaml`
- `adapters/profiles/e2e_bevfusion_vadv2_shadow.yaml`

检查重点：

- `BEVFusion` 输出是否只作为 shadow planner 输入，不直接 takeover stable 主链。
- `UniAD-style` 与 `VADv2` 是否共享核心 comparison metrics。
- `VADv2` 的不确定性指标是否仍然是对照线，而不是新的主控路线。

### report / issue update 是否能支撑回贴

- `src/simctl/reporting.py`
- `tests/test_reporting.py`

检查重点：

- `Shadow Comparison`
- `Comparison Gaps`
- `Gate Verdicts`
- `issue_update.md`

这些输出的作用是让 #5/#10/#27 能被持续回贴，不是替代真实 runtime evidence。

### runtime blocker 是否被说清楚

- `docs/REMOTE_GPU_RESOURCE_AND_UE4_BLOCKERS_CN.md`
- `docs/REMOTE_GPU_ACCESS_PLAN_CN.md`
- `infra/ubuntu/check_host_readiness.sh`

检查重点：

- 远端 GPU/UE4 资源说明有没有区分“已确认”和“仍需现场复核”。
- `Tailscale + OpenSSH` 是否仍只是跨网协作路径，不等价于主机已经完成正式验收。
- self-hosted runner 是否仍然不是 stable runtime 主线的前置条件。

## 3. 已完成与未完成边界

### 可以视为 repo-side 已完成

- BEVFusion shadow interface contract
- UniAD-style / VADv2 shadow profile 口径
- KPI gate 与 shared comparison metrics
- `simctl report` 的 shadow comparison 汇总
- Ubuntu execute runbook
- 远端 GPU/UE4 blocker inventory
- Tailscale/OpenSSH 访问方案
- 研究状态快照和杨志朋阅读纪要

### 不能假装已经完成

- 公司 Ubuntu 主机上的正式 `--execute` runtime 验收
- BEVFusion 输出样例
- UniAD-style / VADv2 shadow 对比样例
- 正式 `run_result.json / report.md / summary.json / issue_update.md`
- 可点击的截图、视频或其他 runtime evidence

## 4. 下一步真正的 review 顺序

1. 先复核 issue [#27](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/27) 是否已经拿到公司 Ubuntu 主机真实运行产物。
2. 如果没有产物，不继续扩新 planner 分支，只维护现有合同和文档。
3. 如果拿到产物，优先检查 `issue_update.md` 是否能直接回贴到 #27。
4. 再根据真实指标判断是否需要收紧 `planner_interface_disagreement_rate`、`trajectory_divergence_m`、`min_ttc_sec` 或 `shadow_uncertainty_coverage`。

## 5. 主机验证入口

拿到公司 Ubuntu 主机后，先跑 readiness：

```bash
bash infra/ubuntu/check_host_readiness.sh
```

第一批真实执行只跑这 3 条：

```bash
simctl run --scenario scenarios/l2/perception_bevfusion_public_road_occlusion.yaml --run-root runs --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml --run-root runs --slot stable-slot-01 --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml --run-root runs --slot stable-slot-02 --execute
simctl report --run-root runs
```

完成后把 `issue_update.md` 回贴到 #27，并把 `run_result/report/summary` 的路径同步到 #5/#10。

## 6. Reviewer 最容易误判的点

- 把 repo-side 合同完成误读成真实 `--execute` 已完成。
- 把 shadow observation-only 误读成可以接管 stable 主链控制。
- 把论文阅读线误读成当前季度要实现 `Hydra-MDP / Hydra-NeXt / MomAD`。
- 把 Tailscale 访问方案误读成公司主机已经完成正式 runtime 验收。

当前最安全的结论是：repo-side BEVFusion shadow 准备已经完成；runtime evidence 仍然集中由 #27 追踪。
