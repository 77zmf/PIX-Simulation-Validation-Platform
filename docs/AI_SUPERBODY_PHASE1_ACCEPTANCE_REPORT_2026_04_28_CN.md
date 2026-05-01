# AI 超体计划第一阶段验收汇报稿

汇报日期口径：`2026-04-28`  
材料整理日期：`2026-04-24`  
适用场景：领导汇报、阶段一验收会、项目周会同步

## 1. 汇报结论

建议按下面口径汇报：

> AI 超体计划第一阶段已经完成“仿真验证平台 MVP 骨架”和“公司 Ubuntu 主机稳定栈启动健康验证”的主要准备，具备进入 2026-04-28 第一阶段验收的条件。当前可以验收的是控制平面、环境基线、场景/资产/KPI/报告链路和自动化证据框架；完整稳定闭环仍需在公司 Ubuntu 22.04 主机上补齐 `initialize pose -> set route -> engage -> stop -> KPI finalize` 的真实运行证据。

阶段一建议结论：

- **验收建议**：有条件通过阶段一 MVP 验收。
- **通过范围**：平台控制面、稳定栈启动、运行工件、报告/replay、公开道路资产准备、shadow 研究接口准备。
- **不应夸大的范围**：不能把 `launch_submitted` 表述成完整闭环通过；不能把 Mac/本地测试表述成公司 Ubuntu 主机稳定闭环验收。
- **阶段二前置 P0**：在公司 Ubuntu 主机完成一条 L0/L1 stable case 的 final KPI `passed/failed` 结果。

## 2. 第一阶段目标与当前状态

| 验收项 | 当前状态 | 可汇报结论 |
| --- | --- | --- |
| Ubuntu 22.04 主机 readiness | 已有预检脚本、主机 readiness/runbook、2026-04-16 公司主机启动健康验证记录 | 主机验收路径明确，2026-04-28 需要复跑并固化最新工件 |
| Stable 栈基线 | 已固定为 `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15 + UE4.26` | 第一阶段 runtime 基线已冻结 |
| `simctl` 控制面 | 已覆盖 `bootstrap / up / run / batch / validate / finalize / replay / report / digest / campaign / bugpack` | 已具备统一入口，不再依赖零散脚本 |
| `run_result.json` | mock、batch 和真实启动健康路径均可产出；真实启动可到 `launch_submitted` | 第一阶段 run artifact 链路成立 |
| report / replay | `simctl report` 可产出 `report.md / report.html / summary.json / issue_update.md`；`simctl replay` 可渲染 replay plan | 汇报与复盘入口已形成 |
| runtime evidence / KPI gate | 已有 runtime evidence 收集、KPI gate、finalize 逻辑和测试覆盖 | 代码侧准备好，仍需公司主机真实执行回填 |
| 公共道路资产 | 已有 `site_gy_qyhx_gsh20260302` 与 `site_gy_qyhx_gsh20260310` manifest，包含 lanelet2、projector、pointcloud、metadata | 资产束已标准化到 manifest 层，下一步是晋升 reusable case |
| Shadow 研究线 | BEVFusion、UniAD-style、VADv2 的接口、指标、报告分流已准备 | 研究线可展示为“shadow-only”，不参与第一阶段 stable acceptance |

## 3. 已完成工作

### 3.1 平台控制面

- `simctl` 已经成为统一控制入口，覆盖稳定栈启动、单场景运行、批量运行、验证、finalize、报告、replay、digest、campaign 和 bugpack。
- stable profile 已经将预检、CARLA、SUMO、Autoware bridge、Autoware stack、localization bridge、actor/object bridge、视觉截图和清理动作串到同一条执行链。
- stable slot catalog 已定义 4 个槽位：`stable-slot-01` 到 `stable-slot-04`，具备单机多槽位扩展基础；阶段一默认建议用 `stable-slot-01` 保守验收。

### 3.2 公司 Ubuntu 主机与稳定栈

- 2026-04-16 公司主机记录显示，CARLA 0.9.15 + Autoware 私有 install 的自动化启动健康检查已完成。
- `simctl up/run/down/report` 已经能渲染并执行 117th 稳定线参数。
- `simctl down` 已验证能清理进程、端口和 slot lock。
- NoMachine/visual 模式、截图工具链、CARLA RPC、ROS graph 健康检查都有明确入口。

当前边界：

- 真实 run 当前仍主要停在 `launch_submitted`。
- KPI gate 仍可能是 `awaiting_runtime_results`，因为 initialize pose、set route、engage、stop、轨迹/控制/碰撞/TTC 等采集还未形成最终闭环。

### 3.3 场景、KPI 与验证资产

当前仓库已有量化基础：

| 类别 | 数量 |
| --- | ---: |
| scenario YAML | 32 |
| KPI gate YAML | 24 |
| runtime probe | 10 |
| Python 单测文件 | 27 |
| Ubuntu 脚本 | 10 |
| asset manifest | 4 |
| reusable subagent spec | 7 |

场景覆盖：

- L0：smoke / Robobus117th Town01 closed loop / NovaDrive smoke
- L1：follow lane / SUMO Town01 traffic smoke
- L2：merge、cut-in、multi-actor、public-road merge、crosswalk VRU、stop-line draft、unprotected-left draft、reconstruction
- L3：occluded pedestrian、double occluder、stress、dynamic reconstruction
- E2E shadow：BEVFusion + UniAD-style / VADv2

### 3.4 公共道路与重建资产

- `site_gy_qyhx_gsh20260310` 已作为当前完整 public-road site proxy bundle，manifest 包含：
  - `lanelet2_map.osm`
  - `map_projector_info.yaml`
  - `pointcloud_map.pcd/`
  - `pointcloud_map_metadata.yaml`
  - `pointcloud_tiles=3624`
- `site_gy_qyhx_gsh20260302` 作为 legacy bundle，manifest 中记录 `pointcloud_tiles=3215`。
- 本地重建线已明确定位：Windows/Mac 负责资产准备和轻量验证，公司 Ubuntu 主机消费 handoff manifest，不在阶段一把重建作业放到正式 runtime 主机上。

### 3.5 Shadow / 感知专题

- 研究路线已经收口为 `BEVFusion -> UniAD-style shadow / VADv2 shadow`。
- Shadow 只做 observation/comparison，不接管 stable 生产控制。
- `simctl report` 已支持 Shadow Comparison、Comparison Gaps、Gate Verdicts 和 issue-ready 汇总。
- 感知专题已从平台主线中拆成并行专题，重点服务数据校准、BEVFusion 基线、远距离感知问题归因和后续 shadow 输入准备。

## 4. 证据清单

可以对领导展示的证据类型：

| 证据 | 当前位置 / 说明 |
| --- | --- |
| 项目主目标和运行基线 | `README.md`、`AGENTS.md`、`AGENTS.override.md` |
| 阶段计划 | `docs/PROJECT_PLAN_CODEX_READY_CN.md`、`docs/TEAM_90_DAY_PLAN.md` |
| 阶段验收 checklist | `docs/QUARTER_ACCEPTANCE.md`、AI Superbody phase gate checklist |
| 公司主机真实启动健康记录 | `docs/COMPANY_HOST_SESSION_2026_04_16_CN.md` |
| Robobus/CARLA 视觉证据 | `docs/evidence/2026-04-19/` |
| 稳定栈配置 | `stack/profiles/stable.yaml`、`stack/slots/stable_slots.yaml` |
| 场景与 KPI | `scenarios/`、`evaluation/kpi_gates/` |
| public-road manifest | `assets/manifests/site_gy_qyhx_gsh20260310.yaml` |
| campaign / bughunt | `ops/test_campaigns/`、`docs/runbooks/` |
| PMO / digest 自动化 | `ops/project_automation.yaml`、`docs/PROJECT_MANAGEMENT_OVERVIEW_CN.md` |

本地验证结果：

```text
2026-04-24
PYTHONPATH=src python3 -m unittest discover -s tests -v
Ran 168 tests in 2.726s
OK
```

说明：这代表 repo-local 控制面、配置、schema、report、runtime evidence 和 campaign 逻辑通过单测，不代表公司 Ubuntu 主机 stable closed-loop acceptance。

## 5. 当前阻塞与风险

| 阻塞 / 风险 | 影响 | Owner | 下一步 |
| --- | --- | --- | --- |
| 真实闭环 final KPI 未完成 | 阶段一不能表述为“完整闭环通过” | 朱民峰 | 2026-04-28 在公司 Ubuntu 主机复跑 L0/L1，产出 `run_result -> finalize -> report/replay` |
| `launch_submitted` 仍是中间态 | 容易在汇报中被误解为 passed | 朱民峰 / Codex PMO | 汇报中明确 `launch_submitted != passed` |
| CARLA 侧 Robobus 可驾驶 blueprint/cooked package 仍需确认 | 当前 Prius fallback 不能代表真实 robobus 几何和动力学 | 车辆/仿真资产 owner | 确认是否能提供 CARLA 0.9.15 + UE4.26 可用包 |
| public-road bundle 尚未完全晋升为 reusable validation case | 资产已标准化，但还不是完整可回归 case | 罗顺雄 / 朱民峰 | 补 route、localization seed、semantic asset-check、scenario/KPI/report 绑定 |
| SUMO public-road traffic 仍缺真实 net/route/sumocfg | 当前可先验收 Town01 SUMO smoke，不宜宣称 public-road traffic 已闭环 | 资产/场景 owner | 先用 `stable_l1_sumo_town01_traffic_smoke` 验证协同链路 |
| Shadow 真实 execute 回填缺失 | 不能把研究报告当 stable 验收证据 | 杨志朋 / 朱民峰 | 等 stable 主线复跑后，再补 shadow 三条场景 execute |

## 6. 2026-04-28 验收建议动作

建议验收当天只抓一条主线：先证明阶段一 MVP 闭环，不扩展研究线。

### 6.1 公司 Ubuntu 主机复跑

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
bash infra/ubuntu/preflight_and_next_steps.sh
bash infra/ubuntu/check_host_readiness.sh --visual
```

### 6.2 L0/L1 stable 验收命令

```bash
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

python3 -m simctl.cli run \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-root runs/phase1_acceptance_20260428 \
  --slot stable-slot-01 \
  --execute

python3 -m simctl.cli validate \
  --run-dir <run_dir_from_run_result> \
  --execute \
  --finalize \
  --report

python3 -m simctl.cli down \
  --stack stable \
  --run-dir <run_dir_from_run_result> \
  --execute
```

### 6.3 报告输出

期望验收工件：

- `runs/phase1_acceptance_20260428/<run_id>/run_result.json`
- `runs/phase1_acceptance_20260428/<run_id>/host_bom.json`
- `runs/phase1_acceptance_20260428/<run_id>/preflight_report.json`
- `runs/phase1_acceptance_20260428/<run_id>/runtime_verification/`
- `runs/phase1_acceptance_20260428/report/report.md`
- `runs/phase1_acceptance_20260428/report/report.html`
- `runs/phase1_acceptance_20260428/report/summary.json`
- replay plan / CARLA recorder / rosbag 路径，如果当次 run 生成

验收判定：

- 如果 final status 是 `passed` 或 `failed`，阶段一闭环证据成立。
- 如果仍停在 `launch_submitted`，阶段一可验收“平台 MVP 与启动健康”，但完整 closed-loop KPI 应标记为 P0 留项。
- 如果 `launch_failed`，阶段一验收应转为 blocked，并按 `preflight_report / health_report / command_logs` 定位。

## 7. Owner 下一步

| Owner | Track | 2026-04-28 前后动作 | 输出 |
| --- | --- | --- | --- |
| 朱民峰 | stable mainline | 组织公司 Ubuntu 主机复跑，保存 phase1 acceptance run_root | `run_result.json`、`report.md/html`、`summary.json` |
| 朱民峰 | control plane | 确认 `validate --finalize --report` 能把 runtime evidence 折回 final KPI | final status 与 gate result |
| 罗顺雄 | public-road asset/scenario | 确认 `site_gy_qyhx_gsh20260310` 资产路径、metadata、route/localization 后续缺口 | reusable case 晋升清单 |
| 杨志朋 | shadow comparison | 准备 BEVFusion 输出样例和 shadow 三条场景的 execute handoff | shadow-only 对比回填计划 |
| 车辆/仿真资产 owner | runtime asset | 确认可驾驶 Robobus blueprint/cooked package | 是否替换 Prius fallback 的决策 |
| Codex PMO | PMO/report | 维护验收材料、digest、blocker owner、汇报口径 | 阶段验收汇总与 issue-ready 更新 |

## 8. 需要领导决策

1. **验收口径确认**：阶段一是否按“平台 MVP + 主机启动健康 + 报告链路”验收，而不是强行要求完整规控闭环全部通过。
2. **主机资源锁定**：2026-04-28 到 2026-04-30 是否锁定公司 Ubuntu 22.04 主机给 stable 验收，避免研究线抢占。
3. **车辆资产优先级**：是否明确安排 Robobus CARLA 0.9.15 / UE4.26 可驾驶资产包交付，否则阶段一继续使用 Prius fallback 并标注边界。
4. **阶段二 P0**：是否同意阶段二第一个硬门槛就是“至少 1 条 L0/L1 stable case final KPI `passed/failed`”。
5. **Shadow 边界**：是否确认 BEVFusion / UniAD-style / VADv2 继续作为 shadow comparison，不作为第一阶段稳定验收结论。

## 9. 领导汇报页纲

### 第 1 页：一句话结论

AI 超体计划第一阶段已经完成仿真验证平台 MVP 和稳定栈启动健康验证准备，建议有条件通过阶段一验收；完整规控闭环 KPI 作为阶段二前置 P0。

### 第 2 页：为什么这个阶段有价值

- 把自动驾驶仿真验证从“个人脚本和经验”收敛到统一 `simctl` 控制面。
- 把环境、场景、KPI、报告、replay 和 digest 串成可复盘链路。
- 把 stable 主线、public-road 资产和 shadow 研究线边界分清楚。

### 第 3 页：已经交付的工程底座

- Stable runtime：Autoware Universe main + ROS 2 Humble + CARLA 0.9.15 + UE4.26。
- 控制面：`bootstrap / up / run / batch / validate / finalize / report / replay / digest / campaign`。
- 配置资产：32 个场景、24 个 KPI gate、10 个 runtime probe、4 个 asset manifest、7 个 subagent spec。
- 质量底座：168 条本地单测通过。

### 第 4 页：真实主机与证据

- 2026-04-16 公司 Ubuntu 主机完成 117th 稳定线自动化启动健康验证。
- CARLA RPC、ROS graph、runtime health、down cleanup 已有记录。
- 2026-04-19 已沉淀 Robobus / CARLA 视觉证据。
- 2026-04-28 需要复跑并生成正式验收 run_root。

### 第 5 页：公开道路与研究线进展

- `site_gy_qyhx_gsh20260310` 已整理成 public-road site proxy asset bundle。
- BEVFusion / UniAD-style / VADv2 已形成 shadow-only 接口和报告口径。
- 感知专题独立推进，不拖 stable 主线验收。

### 第 6 页：当前边界

- `launch_submitted` 是中间态，不等于 stable closed-loop passed。
- CARLA 侧 Robobus 可驾驶资产还需确认。
- Public-road bundle 还需要从 manifest 晋升为 reusable validation case。
- Shadow 真实 execute 还需公司主机回填。

### 第 7 页：阶段二硬门槛

- 1 条 L0/L1 stable case 形成 final `passed/failed`。
- run artifact 包含 host BOM、preflight、runtime evidence、KPI gate、report、replay。
- Public-road case 进入统一验证链。
- stable acceptance 与 shadow comparison 在报告里完全分流。

### 第 8 页：需要领导支持

- 锁定公司 Ubuntu 主机验收窗口。
- 明确阶段一验收口径。
- 决策 Robobus CARLA 可驾驶资产投入。
- 同意阶段二 P0 以真实 final KPI 闭环为唯一硬门槛。

## 10. 2 分钟口播稿

这次第一阶段验收，我建议按“平台 MVP 验收”来汇报。过去这段时间，我们已经把 AI 超体计划的仿真验证工作从零散脚本收敛到统一的 `simctl` 控制平面，稳定运行基线固定为 Autoware Universe、ROS 2 Humble、CARLA 0.9.15 和 UE4.26。现在仓库里已经有 32 个场景、24 个 KPI gate、10 个 runtime probe、4 个资产 manifest，以及覆盖控制面、报告、runtime evidence、campaign 的 168 条本地单测。

公司 Ubuntu 主机这边，4 月 16 日已经完成过 117th 稳定线的自动化启动健康验证，CARLA RPC、ROS graph、runtime health 和 down cleanup 都有记录，4 月 19 日也沉淀了 Robobus/CARLA 的视觉证据。也就是说，第一阶段最核心的“平台能组织起来、能启动、能产出 run_result、能报告、能复盘”的能力已经具备。

需要特别说明的是，当前不能把 `launch_submitted` 说成完整闭环通过。完整规控闭环还差 initialize pose、set route、engage、stop，以及轨迹、控制、碰撞和 TTC 等指标采集后的 final KPI。这个建议作为阶段二第一个 P0：在公司 Ubuntu 主机上让至少一条 L0/L1 stable case 形成最终 `passed` 或 `failed`，并且产出 `run_result -> KPI gate -> report -> replay` 的完整证据链。

所以我的验收建议是：阶段一有条件通过，结论聚焦平台 MVP 和稳定栈启动健康；阶段二立即转入真实闭环 final KPI 和 public-road reusable case 晋升。

## 11. 验收红线

汇报时建议明确三条红线：

1. 不把 Mac 本地测试写成公司 Ubuntu 主机验收。
2. 不把 `launch_submitted` 写成 `passed`。
3. 不把 shadow 研究结果写成 stable acceptance。

## 12. 回滚与兜底

- 如果 2026-04-28 公司 Ubuntu 主机不可用：只能汇报 repo-local validation 和历史启动健康证据，正式 stable acceptance 标记为 blocked。
- 如果 Robobus blueprint 不可用：继续用 Prius fallback 做平台链路验证，但必须标注几何和动力学边界。
- 如果 public-road SUMO/net/route 未齐：先验收 Town01 SUMO smoke 的协同链路，不宣称 public-road traffic 闭环。
- 如果 final KPI 未能闭合：保留阶段一 MVP 验收，阶段二 P0 改为 `finalize/runtime_evidence` 收口。

