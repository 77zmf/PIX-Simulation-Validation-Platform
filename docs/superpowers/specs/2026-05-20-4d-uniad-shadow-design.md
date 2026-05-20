# 4D-UniAD Shadow 设计

日期：2026-05-20

适用仓库：`77zmf/PIX-Simulation-Validation-Platform`

## 1. 目标

建立第一版 `4D scene -> UniAD-style shadow` 研究链路，让公开道路 4D 场景证据可以进入现有 UniAD shadow 对比口径。

这条链路只做旁路评估，不接管 stable 主控。第一版的成功标准不是训练新模型，而是把 4D 场景证据转换成现有 UniAD shadow 契约能消费的输入，并通过 `simctl run -> validate/finalize -> report` 产生可比较的指标。

## 2. 当前依据

仓库已经具备两侧入口：

- 4D / dynamic Gaussian 侧：`adapters/profiles/reconstruction_dynamic_public_road_gaussians.yaml` 和 `evaluation/kpi_gates/reconstruction_dynamic_public_road_gaussians_gate.yaml`
- UniAD shadow 侧：`adapters/profiles/e2e_bevfusion_uniad_shadow.yaml`、`evaluation/kpi_gates/e2e_bevfusion_uniad_shadow_gate.yaml`、`scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml`
- Ubuntu 主机执行侧：`docs/BEVFUSION_SHADOW_UBUNTU_EXECUTE_RUNBOOK_CN.md`

现有 UniAD-style shadow 合同已经要求：

- `object_queries`
- `lane_graph_features`
- `occupancy_queries`
- `ego_history`
- `route_reference`

4D 侧第一版应服务这些字段，而不是引入新的实时控制链。

## 3. 范围

### In Scope

- 定义 4D 场景证据包格式。
- 定义 `4d_scene_to_uniad_shadow` adapter 合同。
- 选择一个 qiyu 公开道路片段作为首个样本来源。
- 复用现有 UniAD-style shadow profile 和 KPI gate。
- 输出离线 adapter 产物、shadow run artifact、report summary 和 issue-ready 结论。
- 在公司 Ubuntu 22.04 主机上只运行 `simctl --execute` 验证，不在远程主机上默认跑重建训练。

### Out Of Scope

- 新增 UniAD 模型训练或权重管理。
- 把 UniAD `shadow_control` 接入车辆或 CARLA ego 控制。
- 把 Gaussian / NuRec 结果当成 CARLA 0.9.15 可驾驶地图。
- 新增 simulator runtime。
- 把 shadow 结果写成 stable acceptance。

## 4. 方案比较

### 方案 A：adapter-first

先把 4D 场景证据包转换为 UniAD-style shadow 输入，再复用现有 `simctl`、KPI gate 和 report。

优点：

- 最小改动，能最快形成可验证证据。
- 不依赖新模型训练。
- 与现有 `BEVFusion -> UniAD-style shadow` 契约兼容。

缺点：

- 第一版只能证明输入契约和指标链路，不证明真实 UniAD 模型效果。

### 方案 B：4DGS-first

先提升 dynamic Gaussian / 4DGS 质量，再讨论 UniAD 消费。

优点：

- 对视觉 replay 和场景资产质量更有帮助。

缺点：

- 训练成本高，字段到 UniAD 的接口仍然没有冻结。
- 容易把视觉质量问题和 planner shadow 问题混在一起。

### 方案 C：UniAD-runtime-first

先接入真实 UniAD repo 和模型推理，再补 4D 数据。

优点：

- 更接近最终研究形态。

缺点：

- 环境、权重、数据格式和延迟风险都很高。
- 在没有 4D 输入契约前，容易产生一次性 demo，难以复用。

### 推荐

采用方案 A。第一版只交付 adapter 合同和小样本闭环，等 10 到 50 个样本的输入、指标、报告稳定后，再决定是否推进 4DGS 质量提升或真实 UniAD runtime 接入。

## 5. 架构

```text
4D scene evidence pack
  -> 4d_scene_to_uniad_shadow adapter
  -> UniAD-style shadow input pack
  -> existing e2e_bevfusion_uniad_shadow profile
  -> simctl run / validate / finalize
  -> e2e_bevfusion_uniad_shadow_gate
  -> report shadow comparison
```

新设计只新增一个逻辑组件：

- `4d_scene_to_uniad_shadow adapter`

第一版可以先以文档和离线 JSON artifact 形式落地。进入实现阶段后，再决定是否放入 `tools/`、`adapters/` 或 `ops/runtime_probes/`。

## 6. 4D 场景证据包合同

一个 4D 场景证据包至少包含：

```json
{
  "schema_version": "2026q2-4d-uniad-shadow-v1",
  "scene_id": "qiyu_4d_uniad_shadow_sample_001",
  "source": {
    "source_bag": "/data/pix/road_tests/qiyu_recon/<run_id>",
    "capture_manifest": "/data/pix/road_tests/qiyu_recon/<run_id>/capture_manifest.json",
    "calibration": "/data/pix/road_tests/qiyu_recon/<run_id>/calibration",
    "route_reference": "assets/routes/<route>.csv"
  },
  "time_window": {
    "start_sec": 0.0,
    "end_sec": 20.0,
    "tick_hz": 10
  },
  "coordinate_frames": {
    "target_frame": "map",
    "ego_frame": "base_link",
    "max_sensor_skew_ms": 100
  },
  "scene_layers": {
    "static_background": "static_background_manifest.json",
    "dynamic_tracks": "dynamic_tracks.jsonl",
    "occupancy": "occupancy_grid.jsonl",
    "ego_history": "ego_history.jsonl",
    "lane_graph": "lane_graph.json"
  }
}
```

第一版允许 `static_background` 来自 mesh / pointcloud / static Gaussian summary，不要求直接加载 Gaussian splats。`dynamic_tracks` 可以来自真实 object topics、CARLA actor truth、instance masks 或人工整理的 track seed，但必须在 manifest 中标明来源。

## 7. Adapter 输出合同

Adapter 输出 `uniad_shadow_input_pack.json`：

```json
{
  "schema_version": "2026q2-4d-uniad-shadow-v1",
  "scene_id": "qiyu_4d_uniad_shadow_sample_001",
  "profile": "e2e_bevfusion_uniad_shadow",
  "contract_version": "2026q2-shadow-v1",
  "target_frame": "map",
  "planning_tick_hz": 10,
  "inputs": {
    "object_queries": "object_queries.jsonl",
    "lane_graph_features": "lane_graph_features.json",
    "occupancy_queries": "occupancy_queries.jsonl",
    "ego_history": "ego_history.jsonl",
    "route_reference": "route_reference.json"
  },
  "quality": {
    "max_perception_age_ms": 100,
    "time_alignment_passed": true,
    "frame_alignment_passed": true,
    "missing_required_inputs": []
  }
}
```

缺字段时 adapter 不能静默通过。必须输出 `missing_required_inputs`，并让 gate/report 明确显示 blocked 或 failed。

## 8. 首个样本选择

第一版优先使用 qiyu 公开道路小片段：

- 时长：10 到 20 秒。
- 场景：有路口、转弯、让行或动态 actor 的片段优先。
- 数据来源：`reconstruction-rich` capture 或已有 qiyu reconstruction run。
- 验证目标：先证明字段完整、时间同步、坐标一致和 UniAD shadow report 可生成。

不要在第一版直接使用长走廊作为唯一样本。长走廊适合后续压力测试，首个样本应该先降低轨迹、碰撞和地图 seam 的不确定性。

## 9. 远程主机执行流程

主机预检：

```bash
bash infra/ubuntu/check_host_readiness.sh
bash infra/ubuntu/preflight_and_next_steps.sh
```

4D capture 预检：

```bash
bash ops/scripts/record_qiyu_reconstruction_capture.sh \
  --capture-profile reconstruction-rich \
  --mode static \
  --out-root /data/pix/road_tests/qiyu_recon \
  --preflight-seconds 8
```

已有 UniAD shadow 链路验证：

```bash
RUN_ROOT=/data/pix/sim_runs/4d_uniad_shadow_probe

simctl run \
  --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml \
  --run-root "${RUN_ROOT}" \
  --slot stable-slot-01 \
  --execute

simctl report \
  --run-root "${RUN_ROOT}" \
  --output-dir "${RUN_ROOT}/report_shadow"
```

进入实现后，adapter 产物应写入 run 目录或其 `runtime_verification/` 子目录，使 `simctl finalize` 和 `simctl report` 能引用。

## 10. 指标

4D 输入质量指标：

- `time_alignment_passed >= 1`
- `frame_alignment_passed >= 1`
- `required_input_completeness >= 1`
- `dynamic_track_coverage >= 0.80`
- `occupancy_query_coverage >= 0.80`

UniAD-style shadow 指标复用现有 gate：

- `route_completion >= 0.96`
- `collision_count <= 0`
- `trajectory_divergence_m <= 0.60`
- `min_ttc_sec >= 2.0`
- `comfort_cost <= 0.30`
- `red_light_violations <= 0`
- `unprotected_left_yield_failures <= 0`
- `planner_disengagement_triggers <= 1`

第一版报告必须把 4D input quality 和 UniAD shadow result 分开显示。4D 输入失败时，不应该解读 UniAD 指标。

## 11. Error Handling

必须显式失败或阻塞的情况：

- 缺 camera / LiDAR / calibration / route reference。
- 坐标系不能统一到 `map`。
- 时间戳 skew 超过 100 ms。
- actor tracks 与 occupancy 时间轴不一致。
- `object_queries`、`lane_graph_features`、`occupancy_queries`、`ego_history`、`route_reference` 任一缺失。
- CARLA 运行只产生 `launch_submitted`，没有最终 `run_result.json`、KPI gate 或 report。

失败结果写入 adapter summary 和 report，不允许用空数组或默认值伪装通过。

## 12. 测试策略

Repo-side 第一批测试：

- profile/schema 加载测试：确认新合同能被配置检查读取。
- adapter synthetic fixture 测试：用 1 个最小 4D evidence fixture 生成 UniAD shadow input pack。
- missing-field 测试：缺任一 UniAD required input 时必须失败。
- report summary 测试：确认 4D input quality 和 UniAD shadow result 分栏。

远程主机验证：

- 先跑现有 UniAD shadow scenario，确认 report/gate 链路。
- 再把 4D adapter 产物挂入同一 run root。
- 最后用 10 到 50 个小样本做离线 batch，汇总 blocked / failed / passed 分布。

## 13. 风险与回滚

风险：

- 4D 质量指标和 UniAD shadow 指标混在一起，导致结论不可解释。
- Gaussian / NuRec 被误认为 CARLA 0.9.15 地图格式。
- UniAD shadow 输出被误读为可以接管 stable 控制。
- 长走廊 seam / collision 问题污染第一版 adapter 验证。

回滚：

- 移除新增 adapter 配置、fixture 和测试即可回到现有 BEVFusion / UniAD shadow 合同。
- 不改 stable stack、不改正式控制链、不提交大文件或模型权重。
- 所有 4D 输出保留在 `/data/pix/reconstruction/runs/...`、`/data/pix/road_tests/...`、`outputs/` 或 `artifacts/`，不进入 Git 历史。

## 14. 下一步实施计划入口

用户确认本 spec 后，再进入 implementation plan。计划应优先拆成四步：

1. 增加最小 4D evidence fixture 和 adapter 输出 schema。
2. 增加 adapter 生成脚本或 profile。
3. 扩展 report/finalize，使 4D input quality 与 UniAD shadow result 分栏。
4. 在远程主机跑现有 UniAD shadow scenario，并把 adapter 产物回填到同一 report。
