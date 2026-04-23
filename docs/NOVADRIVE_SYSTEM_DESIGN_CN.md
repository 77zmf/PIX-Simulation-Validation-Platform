# NovaDrive 自研自动驾驶系统设计

## 目标

NovaDrive 是一套不依赖 Autoware 的自研自动驾驶系统。它复用 PIX 仓库里的 `simctl`、CARLA 0.9.15、scenario、KPI、report 和 runtime evidence，但实时驾驶决策链完全由 NovaDrive 自己完成。

正式链路是：

```text
scenario / replay / sensor data
-> NovaDrive runtime
-> perception
-> world model
-> tracking / prediction / risk
-> behavior / trajectory planning
-> control
-> CARLA or future vehicle runtime
-> runtime_evidence
-> KPI gate
-> report
```

## 硬边界

- 不启动 Autoware。
- 不依赖 Autoware topic、service、launch 或 planning simulator。
- `simctl` 只负责任务编排、slot、运行工件、KPI 和报告，不进入实时驾驶决策。
- 第一阶段可用 CARLA truth 启动闭环；正式感知阶段必须使用 BEVFusion 或后续自研感知输出。
- CARLA truth 在 BEVFusion 阶段只能作为 oracle comparison，不能替代感知通过。

## 模块分层

```text
novadrive/
  foundation/     time, frame, geometry, schema
  runtime/        CARLA runner, replay runner, recorder, health
  perception/     BEVFusion provider, CARLA truth provider
  world_model/    ego, objects, lanes, route, occupancy, history
  reasoning/      tracker, prediction, risk, scene state
  planning/       behavior, reference line, speed, trajectory
  control/        pure pursuit, PID, command limiter
  evaluation/     artifact validation and metrics handoff
```

## 坐标和时间

- `carla_world`: CARLA 原生世界坐标，用于第一阶段 direct-CARLA 控制。
- `map`: 项目 scenario 语义坐标，沿用现有 YAML 表达；进入 CARLA runtime 时显式转换。
- `ego_base`: 车辆本体坐标，后续用于传感器和控制扩展。
- `lidar` / `bev`: BEVFusion 输入输出坐标，必须由 provider 负责转换到 NovaDrive 标准对象。
- 所有 runtime sample 必须带 `timestamp`，单次 run 内同一模块不得混用 wall time 和 sensor time。

## 公共接口

核心数据类型已经落到 `src/novadrive/foundation/types.py`：

- `EgoState`
- `SensorFrame`
- `DetectedObject`
- `TrackedObject`
- `PredictedObject`
- `WorldState`
- `RiskAssessment`
- `BehaviorDecision`
- `PlannedTrajectory`
- `ControlCommand`
- `RuntimeEvidence`

## 第一版算法

- 感知：`CarlaTruthProvider` 起步，`BEVFusionProvider` 作为正式感知接入点。
- 跟踪：nearest-neighbor association。
- 预测：constant velocity。
- 风险：最小距离、TTC、同车道/并入冲突。
- 行为：`KEEP_LANE`、`YIELD`、`BRAKE`、`STOP`。
- 轨迹：朝目标点的 reference-line trajectory。
- 控制：pure pursuit steering + PID longitudinal command。

## 运行方式

渲染启动计划：

```bash
simctl up --stack novadrive --scenario scenarios/l0/novadrive_smoke.yaml --run-dir runs/<run_id> --slot novadrive-slot-01
```

真实 CARLA 闭环：

```bash
simctl run --scenario scenarios/l0/novadrive_smoke.yaml --run-root runs --slot novadrive-slot-01 --execute
simctl validate --run-dir runs/<run_id> --execute --finalize
simctl report --run-root runs
```

本地 mock runner：

```bash
PYTHONPATH=src python3 -m novadrive.runtime.runner \
  --scenario scenarios/l0/novadrive_smoke.yaml \
  --run-dir /tmp/novadrive_mock \
  --mode mock
```

## 验收

单次运行只有最终 `run_result.json` 中的 gate 结果能作为结论。`launch_submitted` 仍只是中间态。

最低交付链：

```text
scenario -> simctl run -> NovaDrive evidence -> simctl finalize -> KPI gate -> report
```

