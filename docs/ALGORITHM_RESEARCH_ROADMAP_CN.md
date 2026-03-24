# 算法研究路线图

这份文档把当前季度内的四条研究线落到仓库结构中，目标不是一次性追求“最强算法”，而是建立可重复验证、可回归、可交接的研究闭环。

## 总原则

- 本季度主交付仍然是稳定闭环，不做脱离验证链路的单点算法展示。
- 研究主语境调整为公开道路，不再把 `site proxy` 作为默认主线表述；地图、点云和重建资产转为公开道路场景复现与定位回归的支撑线。
- 规划控制、感知、E2E 和三维重建都必须挂到统一的 `scenario -> run_result -> gate -> report` 流程。
- `UE5 / E2E` 当前只做 shadow，不直接接管生产控制链路。
- 当前推荐算法路径是：`BEVFusion 感知基线 -> UniAD-style shadow 主线 -> VADv2 对照 -> Hydra-NeXt 作为闭环强化预备`。

## 一、规划控制算法研究

### 本季度目标

- 把稳定闭环从“能跑”推进到“可比较、可回归、可解释”。
- 形成至少 1 条公开道路研究型场景，用于比较不同规划控制配置在舒适性、规则遵循、交互处理和 fallback 行为上的差异。

### 研究问题

- 在 merge、unprotected left、cut-in、occlusion 等典型公开道路场景里，当前规划控制链路的失效模式是什么。
- 控制稳定性和安全裕度能否在不牺牲闭环成功率的情况下提升。
- yield、红灯、stop line 和 fallback 是否被明确定义、统计和约束。

### 关注指标

- route completion
- collision count
- min TTC
- lateral / longitudinal error
- stop-line overshoot
- comfort cost
- red-light violations
- yield-rule violations
- fallback count

### 本仓库入口

- 算法 profile: `adapters/profiles/planning_control_research.yaml`
- KPI gate: `evaluation/kpi_gates/planning_control_research_gate.yaml`
- 研究场景: `scenarios/l2/planning_control_public_road_merge_regression.yaml`

## 二、感知算法研究

### 本季度目标

- 在稳定主线中保留 production perception 路径。
- 明确把 `BEVFusion` 作为公开道路多传感器感知基线。
- 让感知输出稳定服务于传统 planning/control 与下一周期 E2E shadow，而不是只停留在检测精度对比。

### 研究问题

- 当前 `BEVFusion` 输出是否足够稳定地支撑 planning/control 和 E2E planner。
- lane topology、occupancy 和 tracks 映射到 planner 输入时，主要分歧点在哪里。
- 场景复杂度提升后，误检、漏检、ID switch、拓扑断裂和时延哪个是主瓶颈。

### 关注指标

- detection recall
- false positives per frame
- tracking ID switches
- occupancy IoU
- lane topology recall
- latency
- planner interface disagreement rate

### 本仓库入口

- 算法 profile: `adapters/profiles/perception_bevfusion_public_road.yaml`
- KPI gate: `evaluation/kpi_gates/perception_bevfusion_public_road_gate.yaml`
- 研究场景: `scenarios/l2/perception_bevfusion_public_road_occlusion.yaml`

## 三、公开道路 E2E 算法研究

### 本季度目标

- 把公开道路 E2E 研究限定为 `trajectory-level shadow`，不做直接控制接管。
- 建立一条主 shadow 路线和一条对照路线：
  - 主路线：`BEVFusion + UniAD-style planning-oriented shadow`
  - 对照路线：`BEVFusion + VADv2 shadow`
- 为下周期是否进入更深闭环试验提供可比较证据。

### 研究问题

- 相比传统 planning/control，planning-oriented shadow planner 在公开道路交互场景里的收益是什么。
- `UniAD-style` 主路线在 unprotected left、merge、cut-in、occluded pedestrian 等场景中的主要失效模式是什么。
- `VADv2` 的不确定性规划是否能降低 shadow 发散和行为抖动。
- 如果 open-loop 与 closed-loop 结论明显不一致，是否需要向 `Hydra-NeXt` 这类更重闭环稳定性的路线演进。

### 关注指标

- route completion
- collision count
- min TTC
- trajectory divergence
- comfort cost
- red-light violations
- unprotected-left yield failures
- cut-in yield failures
- planner disengagement triggers

### 本仓库入口

- 主 shadow profile: `adapters/profiles/e2e_bevfusion_uniad_shadow.yaml`
- 主 shadow gate: `evaluation/kpi_gates/e2e_bevfusion_uniad_shadow_gate.yaml`
- 主 shadow 场景: `scenarios/ue5/e2e_bevfusion_uniad_unprotected_left.yaml`
- 对照 profile: `adapters/profiles/e2e_bevfusion_vadv2_shadow.yaml`
- 对照 gate: `evaluation/kpi_gates/e2e_bevfusion_vadv2_shadow_gate.yaml`
- 对照场景: `scenarios/ue5/e2e_bevfusion_vadv2_occluded_pedestrian.yaml`

## 四、三维重建与地图资产研究

### 本季度目标

- 把三维重建明确定位为公开道路地图资产刷新、定位回归和场景复现链路的一部分，而不是独立脱节的论文路线。
- 形成一条 `采集 -> 对齐 -> 地图刷新候选 -> 场景可回放` 的最小研究路径。

### 研究问题

- lanelet、pointcloud、GNSS/IMU 和现场采集数据如何稳定对齐。
- 重建结果能否稳定服务于地图资产更新、定位回归和公开道路场景复现，而不是只生成可视化结果。
- 资产刷新延迟是否能满足周更或问题复盘节奏。

### 关注指标

- lanelet alignment RMSE
- pointcloud coverage ratio
- localization drift
- revisit consistency
- asset publish latency
- replay readiness score

### 本仓库入口

- 算法 profile: `adapters/profiles/reconstruction_public_road_map_refresh.yaml`
- KPI gate: `evaluation/kpi_gates/reconstruction_public_road_map_refresh_gate.yaml`
- 研究场景: `scenarios/l2/reconstruction_public_road_map_refresh.yaml`

## 执行顺序

1. 先把规划控制研究线做实，因为它直接决定稳定闭环是否成立。
2. 再把 `BEVFusion` 感知研究线做实，为 planning/control 和 E2E shadow 提供稳定输入。
3. 然后把 `UniAD-style` 主 shadow 与 `VADv2` 对照接成公开道路实验线。
4. 最后把三维重建研究线收敛到公开道路地图刷新、定位回归和场景复现，避免和主线争抢算力与时间。

## 每周最小输出

- 每条研究线至少新增一个可追踪工件：场景、run_result、报告、资产版本或 gate 变更。
- 新增算法或配置必须能回答“相对基线解决了什么问题”。
- 所有研究结论都要能回指到具体场景和 KPI，而不是只给主观判断。
