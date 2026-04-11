# BEVFusion Shadow Interface Baseline

本文档收口 `BEVFusion` 公开道路感知基线、`BEVFusion -> shadow planner` 接口草案，以及 `UniAD-style / VADv2` 的第一版对照指标口径。

目标不是直接把研究线接进正式控制链，而是先把接口、验证方法和回滚边界写清楚，确保研究线能复用 `stable + CARLA 0.9.15 + UE4.26` 的同一条验证底座。

## 1. 基线定位

- `BEVFusion` 仍是当前公开道路感知基线。
- `UniAD-style` 与 `VADv2` 只以 `shadow` 方式输出旁路结果，不接管主控。
- 当前契约版本固定为 `2026q2-shadow-v1`。
- 契约主入口是 [adapters/profiles/perception_bevfusion_public_road.yaml](../adapters/profiles/perception_bevfusion_public_road.yaml)。

`integration_boundary=production_perception_baseline_and_shadow_input` 表示两件事：

1. 主线感知仍以 `BEVFusion` 产物为准。
2. shadow planner 只消费主线感知已经稳定输出的对象、占据和轨迹信息，不额外扩感知模型边界。

## 2. BEVFusion 输出契约

### 输入前提

- `sensors`: `production_perception_or_carla0915_high_fidelity`
- `calibration`: 必需
- `map`: `lanelet2_or_hd_map`
- 时间戳来源：`synchronized_sensor_fusion_stamp`
- 最大时间偏差：`100 ms`
- 目标坐标系：`map`

### 输出对象

- `bevfusion_objects`
  - 字段：`object_id`、`class_label`、`position_xyz_m`、`size_lwh_m`、`yaw_rad`、`velocity_xy_mps`、`confidence`、`tracking_state`
- `bevfusion_occupancy`
  - 字段：`grid_origin_xy_m`、`resolution_m`、`horizon_sec`、`occupancy_probability`
- `bevfusion_tracks`
- planner 接口通道
  - `object_queries`
  - `lane_graph_features`
  - `occupancy_queries`
  - `ego_history`

其中 `ego_history` 约束为：

- 时间窗：`2.0 s`
- 最低频率：`10 Hz`
- 字段：`timestamp`、`position_xyz_m`、`yaw_rad`、`velocity_xy_mps`、`acceleration_xy_mps2`

## 3. Shadow Planner 映射

### UniAD-style shadow

入口定义位于 [adapters/profiles/e2e_bevfusion_uniad_shadow.yaml](../adapters/profiles/e2e_bevfusion_uniad_shadow.yaml)。

必需输入：

- `object_queries`
- `lane_graph_features`
- `occupancy_queries`
- `ego_history`
- `route_reference`

同步约束：

- `target_frame=map`
- `max_perception_age_ms=100`
- `planning_tick_hz=10`

输出形式：

- `shadow_multimodal_trajectories`
  - `top_k=6`
- `shadow_trajectory`
  - `horizon_sec=8.0`
  - `step_sec=0.5`
- `shadow_control`
  - `observation_only=true`

### VADv2 shadow

入口定义位于 [adapters/profiles/e2e_bevfusion_vadv2_shadow.yaml](../adapters/profiles/e2e_bevfusion_vadv2_shadow.yaml)。

必需输入：

- `object_queries`
- `lane_graph_features`
- `ego_history`
- `route_reference`
- `vectorized_scene_tokens`

附加约束：

- `vectorized_scene_tokens` 来源于 `vadv2_scene_tokens`
- 需要保留不确定性表征
- `shadow_control` 仍然只用于旁路分析

同步约束与 `UniAD-style shadow` 一致：

- `target_frame=map`
- `max_perception_age_ms=100`
- `planning_tick_hz=10`

## 4. 对照指标口径

共享核心指标：

- `route_completion`
- `collision_count`
- `trajectory_divergence_m`
- `min_ttc_sec`
- `planner_disengagement_triggers`

`UniAD-style shadow` 重点补充：

- `comfort_cost`
- `red_light_violations`
- `unprotected_left_yield_failures`

`VADv2 shadow` 重点补充：

- `cut_in_yield_failures`
- `shadow_uncertainty_coverage`

落地文件：

- [evaluation/kpi_gates/perception_bevfusion_public_road_gate.yaml](../evaluation/kpi_gates/perception_bevfusion_public_road_gate.yaml)
- [evaluation/kpi_gates/e2e_bevfusion_uniad_shadow_gate.yaml](../evaluation/kpi_gates/e2e_bevfusion_uniad_shadow_gate.yaml)
- [evaluation/kpi_gates/e2e_bevfusion_vadv2_shadow_gate.yaml](../evaluation/kpi_gates/e2e_bevfusion_vadv2_shadow_gate.yaml)

## 5. 首批验证场景

感知基线：

- [scenarios/l2/perception_bevfusion_public_road_occlusion.yaml](../scenarios/l2/perception_bevfusion_public_road_occlusion.yaml)

UniAD-style shadow：

- [scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml](../scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml)

VADv2 shadow：

- [scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml](../scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml)

## 6. 如何验证

### 本地 Windows 开发环境

本地主要验证控制面、契约和配置，不替代 Ubuntu 正式 runtime。

可执行：

```bash
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m unittest discover -s tests -v
```

可做 mock 场景闭环：

```bash
.venv\Scripts\python -m simctl.cli --repo-root . run --scenario scenarios/l2/perception_bevfusion_public_road_occlusion.yaml --run-root runs --mock-result passed
.venv\Scripts\python -m simctl.cli --repo-root . run --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml --run-root runs --mock-result passed
.venv\Scripts\python -m simctl.cli --repo-root . run --scenario scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml --run-root runs --mock-result passed
```

### 公司 Ubuntu 22.04 主机

真实运行验证应在正式主机上执行：

```bash
simctl run --scenario scenarios/l2/perception_bevfusion_public_road_occlusion.yaml --run-root runs --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml --run-root runs --slot stable-slot-01 --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml --run-root runs --slot stable-slot-02 --execute
```

## 7. 哪些 KPI 或可观察量应该变化

- 感知契约冻结后，应优先稳定 `planner_interface_disagreement_rate`、`lane_topology_recall` 和 `latency_ms`。
- `UniAD-style shadow` 应优先关注 `trajectory_divergence_m`、`min_ttc_sec` 和 `unprotected_left_yield_failures`。
- `VADv2 shadow` 应优先关注 `trajectory_divergence_m`、`cut_in_yield_failures` 和 `shadow_uncertainty_coverage`。
- 这次改动不会改变 stable 主线正式控制逻辑，只会让 profile snapshot、接口说明和 shadow 对照口径更明确。

## 8. 当前哪些仍是 stub，哪些已经是真实约束

真实约束：

- profile 中的输入输出字段
- 场景与 gate 的引用关系
- 共享核心指标口径
- shadow 只做旁路分析，不 takeover

仍是 stub：

- `BEVFusion` 到真实 planner tensor 的在线适配实现
- `shadow_control` 的真实 runtime 回放结果
- 公司 Ubuntu 主机上的真实 `--execute` 指标回填

## 9. 回滚方式

如果本轮契约需要回滚：

1. 删除或回退三个 profile 里的 `contract_version`、`integration_boundary`、`planner_interface_contract`、`interface_contract` 字段。
2. 删除本文档引用。
3. 保持既有 scenario 与 KPI gate 不变，确保 stable 主线运行路径不受影响。

回滚影响：

- 只会降低研究线接口说明的清晰度。
- 不应影响 `stable` 主线已有的 `bootstrap / up / run / report / replay` 控制面能力。
