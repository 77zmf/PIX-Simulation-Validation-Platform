# 算法研究路线图

这份文档把当前季度内的研究线落到仓库结构中。目标不是追求“最强算法”，而是建立可重复验证、可回归、可交接的研究闭环。

## 总原则

- 本季度主交付仍然是稳定闭环
- 所有研究线都挂到统一的 `scenario -> run_result -> gate -> report` 流程
- 所有研究线都运行在 `CARLA 0.9.15 / UE4.26` 的 `stable` 栈上
- `E2E shadow` 只做 shadow，不直接接管控制链路

## 1. 规划控制研究

目标：

- 把稳定闭环从“能跑”推进到“可比较、可回归、可解释”

关注指标：

- `route_completion`
- `collision_count`
- `min_ttc_sec`
- 横纵向误差
- 停车线超调
- 舒适性代价
- fallback 次数

仓库入口：

- `adapters/profiles/planning_control_research.yaml`
- `evaluation/kpi_gates/planning_control_research_gate.yaml`
- `scenarios/l2/planning_control_public_road_merge_regression.yaml`

## 2. 感知研究

目标：

- 明确 `BEVFusion` 作为公开道路感知基线
- 让感知输出稳定服务规划控制和 E2E shadow

关注指标：

- detection recall
- false positives per frame
- tracking ID switches
- occupancy IoU
- lane topology recall
- planner interface disagreement rate

仓库入口：

- `adapters/profiles/perception_bevfusion_public_road.yaml`
- `evaluation/kpi_gates/perception_bevfusion_public_road_gate.yaml`
- `scenarios/l2/perception_bevfusion_public_road_occlusion.yaml`

## 3. E2E shadow 研究

目标：

- 把公开道路 E2E 研究限定在 trajectory-level shadow
- 建立一条主 shadow 路线和一条对照路线：
  - 主路线：`BEVFusion + UniAD-style shadow`
  - 对照路线：`BEVFusion + VADv2 shadow`

关注指标：

- trajectory divergence
- route completion
- collision count
- min TTC
- comfort cost
- unprotected-left yield failures
- cut-in yield failures

仓库入口：

- `adapters/profiles/e2e_bevfusion_uniad_shadow.yaml`
- `adapters/profiles/e2e_bevfusion_vadv2_shadow.yaml`
- `evaluation/kpi_gates/e2e_bevfusion_uniad_shadow_gate.yaml`
- `evaluation/kpi_gates/e2e_bevfusion_vadv2_shadow_gate.yaml`
- `scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml`
- `scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml`

## 4. 重建与地图资产研究

目标：

- 把重建定位为公开道路地图刷新、场景复现和定位回归链路的一部分
- 先做 `map refresh`，再做 `static Gaussian`，最后才考虑 `dynamic Gaussian`

仓库入口：

- `adapters/profiles/reconstruction_public_road_map_refresh.yaml`
- `adapters/profiles/reconstruction_static_public_road_gaussians.yaml`
- `adapters/profiles/reconstruction_dynamic_public_road_gaussians.yaml`
- `scenarios/l2/reconstruction_public_road_map_refresh.yaml`
- `scenarios/l2/reconstruction_static_public_road_gaussian_base.yaml`
- `scenarios/l3/reconstruction_dynamic_public_road_gaussian_replay.yaml`

## 5. 与稳定主线的关系

- 所有研究任务都不能抢占稳定闭环交付
- 研究场景和稳定场景共享同一条 `stable` 栈
- 研究线如需并行运行，先复用 `stable` 多槽位能力，再评估是否进入常规回归
