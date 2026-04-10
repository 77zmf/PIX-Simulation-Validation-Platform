# BEVFusion 基线与 Shadow E2E 接口基线

更新时间: `2026-04-10`

这份文档对应 `owner-yang` 研究任务, 用来把以下内容收口到仓库里:

- `BEVFusion` 当前接入边界
- `BEVFusion -> shadow planner` 第一版接口草案
- `UniAD-style` 和 `VADv2` 的指标口径
- 首批研究场景与验证路径

当前阶段仍然坚持两个约束:

- `BEVFusion` 是感知基线, 不是新的控制接管入口
- `shadow planner` 只做 `observation_only` 比较, 不直接 takeover

## 1. 当前仓库入口

感知基线:

- `adapters/profiles/perception_bevfusion_public_road.yaml`
- `evaluation/kpi_gates/perception_bevfusion_public_road_gate.yaml`
- `scenarios/l2/perception_bevfusion_public_road_occlusion.yaml`

Shadow 主路线:

- `adapters/profiles/e2e_bevfusion_uniad_shadow.yaml`
- `evaluation/kpi_gates/e2e_bevfusion_uniad_shadow_gate.yaml`
- `scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml`

Shadow 对照路线:

- `adapters/profiles/e2e_bevfusion_vadv2_shadow.yaml`
- `evaluation/kpi_gates/e2e_bevfusion_vadv2_shadow_gate.yaml`
- `scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml`

## 2. BEVFusion 接入边界

当前冻结边界如下:

- 角色: `production_perception_baseline_and_shadow_input`
- 运行基线: `stable + CARLA 0.9.15 + UE4.26`
- 控制权限: `false`, 不接管 stable 主线控制
- 输入依赖: `sensors + calibration + lanelet2_or_hd_map`
- 输出责任: `detections + occupancy + tracks + planner_interface`

给 shadow planner 的最小接口字段:

- `object_queries`
- `lane_graph_features`
- `occupancy_queries`
- `ego_history`

这个边界的意义是先把感知输出契约稳定住, 再让 planner 研究线在同一份输入上比较, 避免一边换感知口径一边换 planner 结构。

## 3. Shadow Planner 接口草案

合同版本:

- `2026q2-shadow-v1`

共同约束:

- `mode = observation_only`
- `control_takeover = false`
- 时间基准: `stable_stack_sim_time`
- 允许输入来源: `perception_bevfusion_public_road`
- 当前感知时延预算: `120 ms`

UniAD-style shadow:

- 比较目标: `planning_control_research`
- 必需输入:
  - `bevfusion_objects`
  - `bevfusion_tracks`
  - `bevfusion_occupancy`
  - `lane_graph_features`
  - `ego_history`
- 主要输出:
  - `shadow_multimodal_trajectories`
  - `shadow_trajectory`
  - `shadow_control`

VADv2 shadow:

- 比较目标: `e2e_bevfusion_uniad_shadow`
- 必需输入:
  - `bevfusion_objects`
  - `bevfusion_tracks`
  - `bevfusion_occupancy`
  - `lane_graph_features`
  - `ego_history`
- 附加表征:
  - `vadv2_scene_tokens`
- 主要输出:
  - `vadv2_scene_tokens`
  - `shadow_trajectory`
  - `shadow_control`

解释:

- `shadow_control` 当前只允许作为 debug/分析输出保留, 不进入正式主控链
- `UniAD-style` 先承担主 shadow 路线
- `VADv2` 保持对照角色, 重点看不确定性覆盖与行为分歧

## 4. 指标口径

感知基线 gate:

- 文件: `evaluation/kpi_gates/perception_bevfusion_public_road_gate.yaml`
- 核心指标:
  - `detection_recall >= 0.92`
  - `false_positive_per_frame <= 0.25`
  - `tracking_id_switches <= 2`
  - `occupancy_iou >= 0.72`
  - `lane_topology_recall >= 0.88`
  - `latency_ms <= 120`
  - `planner_interface_disagreement_rate <= 0.12`

UniAD-style shadow gate:

- 文件: `evaluation/kpi_gates/e2e_bevfusion_uniad_shadow_gate.yaml`
- 核心指标:
  - `route_completion >= 0.96`
  - `collision_count <= 0`
  - `trajectory_divergence_m <= 0.60`
  - `min_ttc_sec >= 2.0`
  - `comfort_cost <= 0.30`
  - `red_light_violations <= 0`
  - `unprotected_left_yield_failures <= 0`
  - `planner_disengagement_triggers <= 1`

VADv2 shadow gate:

- 文件: `evaluation/kpi_gates/e2e_bevfusion_vadv2_shadow_gate.yaml`
- 核心指标:
  - `route_completion >= 0.95`
  - `collision_count <= 0`
  - `trajectory_divergence_m <= 0.65`
  - `min_ttc_sec >= 1.9`
  - `cut_in_yield_failures <= 0`
  - `planner_disengagement_triggers <= 1`
  - `shadow_uncertainty_coverage >= 0.80`

## 5. 首批研究场景建议

第一批优先场景已经在仓库里落位:

1. `scenarios/l2/perception_bevfusion_public_road_occlusion.yaml`
   目标: 先看 `BEVFusion` 在公开道路遮挡条件下的感知质量和 planner 接口稳定性。
2. `scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml`
   目标: 用 `UniAD-style shadow` 看无保护左转的轨迹差异和让行失败。
3. `scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml`
   目标: 用 `VADv2` 看遮挡行人和 cut-in 风险下的不确定性覆盖。

推荐的推进顺序:

1. 先过 `L2 perception` 场景, 确认感知口径稳定。
2. 再跑 `UniAD-style shadow` 主路线。
3. 最后用 `VADv2` 做对照, 重点看收益和副作用是否清楚。

## 6. 如何验证

本地控制面验证:

```bash
python -m unittest discover -s tests -v
simctl run --scenario scenarios/l2/perception_bevfusion_public_road_occlusion.yaml --run-root runs --mock-result passed
simctl run --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml --run-root runs --mock-result passed
simctl run --scenario scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml --run-root runs --mock-result passed
```

公司 Ubuntu 主机上的真实验证:

```bash
simctl run --scenario scenarios/l2/perception_bevfusion_public_road_occlusion.yaml --run-root runs --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml --run-root runs --slot stable-slot-01 --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml --run-root runs --slot stable-slot-02 --execute
```

这次收口对应的验证口径:

- 怎么跑: 见上面的 `simctl run`
- 用哪个场景验证: 一个 `L2 perception` + 两个 `E2E shadow`
- 预期观察什么: `run_result.json` 中的 profile、gate、slot 和 shadow 指标是否完整
- 现在什么是 stub: 本地 `--mock-result` 只验证控制面与配置闭环
- 现在什么是真实: Ubuntu 主机上的 `--execute`
- 怎么回滚: 回退 profile 中的 `contract_version / interface_contract` 字段和本文件, 不影响 stable 主线运行脚本

## 7. 当前结论

仓库当前已经具备:

- `BEVFusion` 基线位置
- `UniAD-style` 主 shadow 路线
- `VADv2` 对照路线
- 对应的场景和 KPI gate

这次补齐后, 缺口从“有 profile 但缺收口口径”缩小成了“还需要 Ubuntu 主机上的真实运行结果”。下一步更适合做真实 `--execute` 验证, 而不是继续扩 profile 种类。
