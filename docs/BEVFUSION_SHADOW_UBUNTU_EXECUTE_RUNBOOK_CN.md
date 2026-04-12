# BEVFusion Shadow Ubuntu Execute Runbook

对应 issue：

- [#18 P1 感知与 Shadow E2E：BEVFusion 接口与指标口径](https://github.com/pixmoving-moveit/zmf_ws/issues/18)
- [#27 Q2 BEVFusion 基线与 Shadow E2E 研究计划](https://github.com/pixmoving-moveit/zmf_ws/issues/27)

这份 runbook 只服务一件事：在公司 `Ubuntu 22.04` 主机上，把 `BEVFusion` 感知基线、`UniAD-style shadow`、`VADv2 shadow` 的真实 `--execute` 结果跑出来，并回填到同一份 `simctl report` 里。

它不是新的 bring-up 文档。主机环境如果还没准备好，先看：

- [docs/UBUNTU_HOST_BRINGUP_CN.md](./UBUNTU_HOST_BRINGUP_CN.md)
- [docs/TOMORROW_COMPANY_HOST_CHECKLIST_CN.md](./TOMORROW_COMPANY_HOST_CHECKLIST_CN.md)
- [docs/BEVFUSION_SHADOW_INTERFACE_BASELINE_CN.md](./BEVFUSION_SHADOW_INTERFACE_BASELINE_CN.md)

## 1. 本次执行的边界

- 正式 runtime 仍然只在公司 `Ubuntu 22.04` 主机上做。
- `BEVFusion` 仍是感知基线。
- `UniAD-style` 和 `VADv2` 仍然只做 `shadow` 旁路比较，不接管 stable 主控。
- 三条真实运行都落在同一个 `run_root`，便于一次性生成 `Shadow Comparison` 和 `Gate Verdicts`。

建议统一使用：

```bash
RUN_ROOT="runs/issue18_shadow_execute"
```

## 2. 执行前检查

在仓库根目录执行：

```bash
bash infra/ubuntu/preflight_and_next_steps.sh
bash infra/ubuntu/check_host_readiness.sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

只有当下面几件事都成立时，再继续本 runbook：

- 主机已经是 `Ubuntu 22.04`
- `CARLA 0.9.15`、`Autoware Universe`、`ROS 2 Humble` 的 bring-up 链路已经过基础自检
- `simctl run --execute` 不会因为环境缺失直接失败

## 3. 本次要跑的 3 条真实场景

| 目标 | 场景 | 建议槽位 | 目标 gate |
| --- | --- | --- | --- |
| 感知基线 | `scenarios/l2/perception_bevfusion_public_road_occlusion.yaml` | `stable-slot-03` | `perception_bevfusion_public_road_gate` |
| 主参考 shadow | `scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml` | `stable-slot-01` | `e2e_bevfusion_uniad_shadow_gate` |
| 对照 shadow | `scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml` | `stable-slot-02` | `e2e_bevfusion_vadv2_shadow_gate` |

这里特意把感知基线放到 `stable-slot-03`，避免它占住 `stable-slot-01` 之后影响 `UniAD-style shadow`。

## 4. 执行顺序

### Step 1. 感知基线

```bash
simctl run \
  --scenario scenarios/l2/perception_bevfusion_public_road_occlusion.yaml \
  --run-root "${RUN_ROOT}" \
  --slot stable-slot-03 \
  --execute
```

执行后记录两件东西：

- stdout JSON 里的 `artifacts.run_dir`
- stdout JSON 里的 `artifacts.run_result`

如果场景在主机上持续占用槽位，等结果文件落盘后手动释放：

```bash
simctl down --stack stable --run-dir <run_dir_perception> --execute
```

### Step 2. UniAD-style shadow

```bash
simctl run \
  --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml \
  --run-root "${RUN_ROOT}" \
  --slot stable-slot-01 \
  --execute
```

如需释放槽位：

```bash
simctl down --stack stable --run-dir <run_dir_uniad> --execute
```

### Step 3. VADv2 shadow

```bash
simctl run \
  --scenario scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml \
  --run-root "${RUN_ROOT}" \
  --slot stable-slot-02 \
  --execute
```

如需释放槽位：

```bash
simctl down --stack stable --run-dir <run_dir_vadv2> --execute
```

说明：

- 最稳妥的方式是先顺序跑通，再考虑把 `stable-slot-01` 和 `stable-slot-02` 拆到两个终端并行执行。
- 如果任何一条 `run_result.json` 没有生成，不要先改指标，先回到 host readiness 和 launch 日志定位问题。

## 5. 统一生成对照报告

三条运行都完成后：

```bash
simctl report \
  --run-root "${RUN_ROOT}" \
  --output-dir "${RUN_ROOT}/report_shadow_issue18"
```

重点看下面三个产物：

- `${RUN_ROOT}/report_shadow_issue18/summary.json`
- `${RUN_ROOT}/report_shadow_issue18/report.md`
- `${RUN_ROOT}/report_shadow_issue18/report.html`

现在 `report.md` 和 `report.html` 里应该能看到：

- `## Shadow Comparison`
- `### Profile-Specific Signals`
- `### Gate Verdicts`
- `### Comparison Gaps`

## 6. 达标时该看到什么

### 感知基线 gate

`perception_bevfusion_public_road_gate` 重点看：

- `detection_recall >= 0.92`
- `false_positive_per_frame <= 0.25`
- `tracking_id_switches <= 2`
- `occupancy_iou >= 0.72`
- `lane_topology_recall >= 0.88`
- `latency_ms <= 120`
- `planner_interface_disagreement_rate <= 0.12`

### Shadow 共享指标

`UniAD-style shadow`：

- `route_completion >= 0.96`
- `collision_count <= 0`
- `trajectory_divergence_m <= 0.60`
- `min_ttc_sec >= 2.0`
- `planner_disengagement_triggers <= 1`

`VADv2 shadow`：

- `route_completion >= 0.95`
- `collision_count <= 0`
- `trajectory_divergence_m <= 0.65`
- `min_ttc_sec >= 1.9`
- `planner_disengagement_triggers <= 1`

### Profile-specific 指标

`UniAD-style shadow`：

- `comfort_cost <= 0.30`
- `red_light_violations <= 0`
- `unprotected_left_yield_failures <= 0`

`VADv2 shadow`：

- `cut_in_yield_failures <= 0`
- `shadow_uncertainty_coverage >= 0.80`

最理想的首批结果是：

- `Shadow Comparison` 两条 profile 都出现
- `Comparison Gaps` 为 `None`
- `Gate Verdicts` 里共享指标的 `Failed` 和 `Missing` 都是 `0`

## 7. 当前哪些算真实验收，哪些还不算

已经算真实验收的部分：

- 公司 Ubuntu 主机上的真实 `--execute` 运行
- 真实 `run_result.json`、`report.md`、`report.html`
- 共享指标和 profile-specific 指标的 gate 判定

还不算正式闭环完成的部分：

- `BEVFusion -> planner tensor` 在线适配的工程实现细节
- `shadow_control` 的 takeover 能力
- 研究线扩展到 `Hydra-MDP / Hydra-NeXt / MomAD`

## 8. issue 回贴模板

建议把结果直接回贴到 `#18`，格式可以用：

```text
真实 execute 回填：
- perception run_id: ...
- UniAD-style shadow run_id: ...
- VADv2 shadow run_id: ...

Shadow Comparison：
- route_completion: ...
- trajectory_divergence_m: ...
- min_ttc_sec: ...
- planner_disengagement_triggers: ...

Gate Verdicts：
- UniAD-style: passed=... failed=... missing=...
- VADv2: passed=... failed=... missing=...

当前 blocker：
- ...

下一步动作：
- ...
```

如果这一步失败，优先回贴：

- 哪条场景失败
- 失败发生在 bring-up、运行中、还是 report 汇总阶段
- 是否生成了 `run_result.json`
- 是否需要先回到 `docs/UBUNTU_HOST_BRINGUP_CN.md` 继续补主机环境
