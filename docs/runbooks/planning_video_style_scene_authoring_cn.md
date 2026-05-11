# Planning 视频式场景构建流程

## 目标

把参考视频或真实路测片段沉淀成可复跑的 PIX stable 场景，而不是只保存一段展示视频。最终证据链仍然按：

`source evidence -> scenario YAML -> simctl --execute -> runtime evidence -> run_result -> KPI gate -> report/replay/bugpack`

## 当前参考源

- 视频式参考：`/Users/cyber/Desktop/录屏2026-05-11 02.06.17.mov`
- 真实问题源：`/Users/cyber/Documents/zmf_test-data/mac_handoff/82th_20260508_1438_dangerous_forced_lane_change`
- 真实案例 manifest：`assets/manifests/planning_road_test_failcases_202605.yaml`
- 真实案例 replay draft：`scenarios/l2/planning_control_roadtest_forced_lane_change_replay_draft.yaml`
- CARLA 可执行视觉场景：`scenarios/l2/planning_control_overtake_reference_scene.yaml`

## 场景拆解

参考视频中的关键元素应被拆成可配置输入：

- 路型：多车道直线或缓弯路段，优先用已有 Town01 surrogate，正式回归再替换为 public-road CARLA/OpenDRIVE fixture。
- Ego：`vehicle.pixmoving.robobus`，使用 robobus117th sensor topology。
- NPC：前方慢车、左侧/右侧相邻车道车、远端前车，第一版用 CARLA actor bridge 进入 Autoware object stream。
- 任务：跟车、超车压力、强制变道风险、回正或减速响应。
- 可视化：CARLA overview mp4、Autoware/RViz planning overlay、object stream 证据。
- KPI：无碰撞、TTC 安全、actor object stream 非空、ego 有控制响应、传感器 topic/sample 正常。

## 分阶段执行

1. 真实证据折叠：先跑 replay probe，确认真实案例指标进入 `run_result/KPI/bugpack`。

```bash
python3 ops/runtime_probes/planning_roadtest_replay_probe.py \
  --run-dir <run_dir> \
  --manifest assets/manifests/planning_road_test_failcases_202605.yaml \
  --profile forced_lane_change
```

2. Town01 视觉 surrogate：先用可执行 CARLA 场景复现“视频式多车道超车压力”。

```bash
simctl run \
  --scenario scenarios/l2/planning_control_overtake_reference_scene.yaml \
  --run-root runs \
  --slot stable-slot-01 \
  --execute
```

3. 公开道路升级：等 82th 路段具备确定的 CARLA/OpenDRIVE fixture 和 actor tracks 后，把 Town01 surrogate 替换为 public-road asset bundle。

## 升级为正式真实场景所需输入

- 82th 事件路段的 CARLA 可加载地图或 OpenDRIVE。
- Lanelet2/projector/localization 对齐证据。
- ego 初始 pose、goal、关键 waypoint。
- NPC 或障碍物轨迹，至少包含 14:37:30-14:39:29 CST 的 lead/adjacent/static obstacle。
- RViz planning overlay：lane-change candidate/reference、virtual wall、static obstacle avoidance、trajectory。
- 接管锚点：manual/brake/teleop takeover 和控制模式切换。

## 判定口径

- Town01 surrogate 只能说明场景模板、actor bridge、传感器和规控响应链路可跑。
- `planning_control_roadtest_forced_lane_change_replay_draft` 只能说明真实路测证据已经进入 KPI/bugpack。
- 正式闭环必须在公司 Ubuntu host 上生成 `run_result.json`、runtime evidence、KPI gate、report/replay，并完成 cleanup。
