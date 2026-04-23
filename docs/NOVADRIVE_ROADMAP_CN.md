# NovaDrive 全流程路线图

## M0 架构和骨架

交付：

- `src/novadrive/` 包骨架
- 公共 dataclass / JSON 序列化
- `novadrive` stack profile 和 slot catalog
- `novadrive_direct_carla` algorithm profile
- L0/L1/L2 scenario 和 KPI gate
- mock evidence 可被 `simctl finalize` 收口

验收：

- 不启动 Autoware。
- `python -m unittest` 中 NovaDrive 相关测试通过。
- mock run 能生成 `runtime_verification/novadrive_*.json`。

## M1 CARLA Truth 闭环

交付：

- `CarlaRuntime` 通过 CARLA RPC 控制 ego。
- `CarlaTruthProvider` 提供目标对象。
- L0 smoke 和 L1 follow-lane 形成真实 runtime evidence。

验收：

- Ubuntu 主机上 `novadrive_l0_smoke` gate passed。
- `control_rate_hz >= 10`。
- `run_result.json` 最终状态为 `passed` 或可解释的 `failed`。

## M2 L2 规则规划闭环

交付：

- L2 merge / cut-in / lead-brake 场景。
- TTC-aware yield / brake 行为。
- failure taxonomy 能区分 runtime、perception、prediction、planning、control。

验收：

- L2 merge gate passed。
- cut-in 和 lead-brake 至少有明确 passed/failed 结论。
- evidence 能解释减速、让行或失败原因。

## M3 BEVFusion 接管感知

交付：

- `BEVFusionProvider` 消费标准 JSON/JSONL handoff。
- `zmf_bev` 的 nuScenes BEV 分布统计结果进入感知范围基线。
- CARLA truth 转为 oracle comparison。

验收：

- L2 merge 决策使用 BEVFusion detections。
- BEVFusion 缺帧、超时或坐标不可信时，run 失败或 blocked。
- report 中有感知帧率、关键目标检测、truth 差异。

## M4 多场景回归

交付：

- L0/L1/L2 至少 5 个 NovaDrive 场景进入 batch。
- `simctl batch --validate --finalize --report` 可重复。
- KPI 和 failure labels 稳定。

验收：

- batch 报告能按场景列出 passed/failed。
- 失败能回指到 runtime evidence。

## M5 公开道路 Replay

交付：

- public-road scenario template。
- replay runtime adapter。
- corner case catalog。
- public-road KPI gate。

验收：

- 至少一个公开道路 case 完整进入 `asset -> scenario -> run -> evidence -> KPI -> report`。
- case 记录 source asset、owner、route、KPI 和 rollback 条件。

## M6 学习型模块 Shadow

交付：

- UniAD / VADv2 / 自研学习型 planner 作为 shadow provider。
- shadow trajectory comparison section。

验收：

- shadow 不控制车辆。
- shadow 结果不影响 NovaDrive 主链 passed/failed。

## M7 实车接口准备

交付：

- `VehicleRuntime` 抽象。
- CARLA runtime 和 replay runtime 共用 world model / planning / control。
- 实车 adapter 默认只允许 shadow。

验收：

- 不改规划控制核心即可切换 runtime adapter。
- 实车接管前必须有独立安全评审和硬件接口 gate。

