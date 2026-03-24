# 算法研究路线图

这份文档把当前季度内的三条研究线落到仓库结构中，目标不是一次性追求“最强算法”，而是建立可重复验证、可回归、可交接的研究闭环。

## 总原则

- 本季度主交付仍然是稳定闭环，不做脱离验证链路的单点算法展示。
- 规划控制、感知、三维重建都必须挂到统一的 `scenario -> run_result -> gate -> report` 流程。
- 每条研究线都要有基线、研究问题、输入输出契约、KPI gate 和最小可运行场景。
- `UE5 / E2E` 当前只做 shadow，不直接接管生产控制链路。

## 一、规划控制算法研究

### 本季度目标

- 把稳定闭环从“能跑”推进到“可比较、可回归、可解释”。
- 形成至少 1 条研究型场景，用于比较不同规划控制配置在舒适性、规则遵循和 fallback 行为上的差异。

### 研究问题

- 在 blind curve、merge、occlusion 等典型场景里，当前规划控制链路的失效模式是什么。
- 控制稳定性和安全裕度能否在不牺牲闭环成功率的情况下提升。
- fallback 是否被明确定义、统计和约束。

### 关注指标

- route completion
- collision count
- min TTC
- lateral / longitudinal error
- stop-line overshoot
- comfort cost
- fallback count

### 本仓库入口

- 算法 profile: `adapters/profiles/planning_control_research.yaml`
- KPI gate: `evaluation/kpi_gates/planning_control_research_gate.yaml`
- 研究场景: `scenarios/l2/planning_control_merge_regression.yaml`

## 二、感知算法研究

### 本季度目标

- 在稳定主线中保留 production perception 路径。
- 让 `BEV baseline + VAD shadow` 进入有输入输出契约的 shadow 评测，而不是仅停留在概念。

### 研究问题

- 当前感知输出是否足够稳定地支撑 planning/control。
- BEV 感知输出映射到 VAD shadow 接口时，主要分歧点在哪里。
- 场景复杂度提升后，误检、漏检、ID switch 和时延哪个是主瓶颈。

### 关注指标

- detection recall
- false positives per frame
- tracking ID switches
- occupancy IoU
- latency
- VAD shadow disagreement rate

### 本仓库入口

- 算法 profile: `adapters/profiles/perception_bev_shadow.yaml`
- KPI gate: `evaluation/kpi_gates/perception_bev_shadow_gate.yaml`
- 研究场景: `scenarios/l2/perception_bev_shadow_blind_curve.yaml`

## 三、三维重建算法研究

### 本季度目标

- 把三维重建明确定位为 `site proxy` 资产生产链的一部分，而不是独立脱节的论文路线。
- 形成一条 `采集 -> 对齐 -> 资产刷新 -> 场景可回放` 的最小研究路径。

### 研究问题

- lanelet、pointcloud、GNSS/IMU 和现场采集数据如何稳定对齐。
- 重建结果能否稳定服务于资产束更新和场景复现，而不是只生成可视化结果。
- 资产刷新延迟是否能满足周更或问题复盘节奏。

### 关注指标

- lanelet alignment RMSE
- pointcloud coverage ratio
- revisit consistency
- localization drift
- asset publish latency
- replay readiness score

### 本仓库入口

- 算法 profile: `adapters/profiles/reconstruction_site_proxy.yaml`
- KPI gate: `evaluation/kpi_gates/reconstruction_site_proxy_gate.yaml`
- 研究场景: `scenarios/l2/reconstruction_site_proxy_refresh.yaml`

## 执行顺序

1. 先把规划控制研究线做实，因为它直接决定稳定闭环是否成立。
2. 再把感知研究线接成 shadow，对下周期 `BEV + VAD` 做好数据和指标准备。
3. 最后把三维重建研究线收敛到 site proxy 资产生产，避免和主线争抢算力与时间。

## 每周最小输出

- 每条研究线至少新增一个可追踪工件：场景、run_result、报告、资产版本或 gate 变更。
- 新增算法或配置必须能回答“相对基线解决了什么问题”。
- 所有研究结论都要能回指到具体场景和 KPI，而不是只给主观判断。
