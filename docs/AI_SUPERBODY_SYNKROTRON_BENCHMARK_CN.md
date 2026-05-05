# AI 超体计划：深信科创 / OASIS 对标导入建议

> 用途：把深信科创公开资料中可借鉴的产品方法，翻译成 AI 超体计划中可执行、可验证、可复盘的工程动作。
> 检索时间：2026-05-03。
> 口径：以下内容只作为公开资料对标，不代表对深信科创内部实现、商务能力或交付状态的确认。

## 1. 对标结论

深信科创最值得借鉴的不是单个产品名称，而是它把自动驾驶研发组织成一条闭环：

`真实数据采集 -> 数据治理/重建/标注 -> 场景生成/重放 -> 仿真任务管理 -> 模型训练/评估 -> 结果回灌`

AI 超体计划当前不应复制一个大而全的 OASIS 平台。更合适的导入方式是把其中的数据闭环、场景晋升、回放诊断、合成数据评估和具身 shadow 方法，落到现有链路：

`assets/scenario -> simctl run/batch -> runtime evidence -> run_result -> KPI gate -> report/replay -> digest`

## 2. 可借鉴模块映射

| 深信科创公开能力方向 | 可借鉴方法 | AI 超体计划落点 | 优先级 | 轨道 |
| --- | --- | --- | --- | --- |
| OASIS Data | 数据采集、脱敏、筛选、环境重建、自动标注、场景标签、OpenX 输出 | 建立 `road-test finding -> asset manifest -> scenario -> KPI gate -> report` 的数据资产台账 | P0 | public-road asset/scenario |
| OASIS Sim | 场景编辑、传感器配置、仿真任务、诊断日志、评估结果 | 把 `simctl batch/report/digest` 扩展为任务台账和验收台账 | P0 | stable mainline |
| OASIS Rover / Rewind | 多传感器同步采集、回放、仿真注入 | 定义 rosbag / CARLA recorder / runtime evidence 的回灌契约 | P1 | stable mainline |
| SOTIF / ODD 场景生成 | 从设计运行域生成高风险长尾场景 | 固化 `现场问题 -> 场景模板 -> 参数扰动 -> 批量回归 -> issue digest` | P1 | public-road asset/scenario |
| 静态/动态重建 | HD map、OpenDRIVE、静态数字孪生、动态参与者轨迹重建 | 把 `site_gy_qyhx_gsh20260310` 晋升成可执行 public-road reusable validation case | P1 | reconstruction support |
| BotStream / Dora 具身方向 | 具身任务流、机器人 OS、3DGS 场景、闭环评估 | 只作为 shadow/research：先做 observation/comparison，不进入 stable 控制接管 | P2 | shadow comparison |

## 3. 本项目应先做的三件事

### 3.1 P0：现场问题到场景的资产台账

目标不是再写一份问题清单，而是让每个现场问题都能被判断是否已经进入可复用验证链。

建议字段：

- `finding_id`：现场问题编号或 GitHub issue
- `source_run`：实车 run、rosbag、日志、视频或人工记录
- `time_range`：可复现时间窗，允许粗粒度但不能空
- `asset_bundle`：地图、点云、标定、传感器 profile、车辆参数
- `scenario_id`：对应或待创建的 scenario YAML
- `kpi_gate`：对应或待创建的 KPI gate
- `replay_method`：CARLA recorder、rosbag replay、runtime evidence 或人工回看
- `verdict_state`：`raw / triaged / scenario_ready / runnable / gated / reported`
- `owner` 和 `next_action`

这一步直接服务当前 P0：把 public-road 资产和路测问题变成可回归 case，而不是停留在问题描述。

### 3.2 P0：把 simctl 结果变成任务台账

对标 OASIS Sim 时，不建议先做大 UI。先让 `simctl report/digest` 能稳定回答这些问题：

- 哪些 run 只有 `launch_submitted`，还没有 final KPI？
- 哪些 run 有 runtime evidence，但没有 report/replay？
- 哪些 scenario 已经绑定 asset manifest 和 KPI gate？
- 哪些失败是 `needs_host / needs_assets / needs_runtime_evidence / needs_kpi_gate / needs_report_replay / needs_decision`？
- 哪些结果可以进入 stable acceptance，哪些只能进入 shadow comparison？

输出形态可以先是 `summary.json` 和 `report.md` 字段增强，后续再考虑控制台或看板。

### 3.3 P1：合成数据只在通过真实性与效用门槛后入库

深信科创的合成数据路线值得借鉴，但 AI 超体计划不能把“生成了场景”直接等同于“形成验证证据”。

建议两道门：

1. **真实性门槛**
   - 传感器几何、时间同步、遮挡、天气、光照、目标尺寸、道路拓扑不能明显违背真实数据。
   - 必须说明合成来源：真实 rosbag 种子、重建资产、人工参数扰动或纯生成。
2. **效用门槛**
   - 必须能触发某个具体 KPI 或已知 failure mode。
   - 必须能在报告里说明它补充了哪类 ODD / corner case 覆盖。

未通过这两道门的合成资产，只能作为 research demo，不能作为 stable acceptance 证据。

## 4. 建议新增的执行卡片

| ID | 标题 | 目标产物 | Owner 建议 | 验收方式 |
| --- | --- | --- | --- | --- |
| DATA-001 | Road-test finding ledger | `assets/findings/*.yaml` 或等价台账 | 朱民峰 + 路测 owner | 至少 3 个历史问题能映射到 asset/scenario/KPI 状态 |
| CASE-001 | Public-road reusable case promotion | `site_gy_qyhx_gsh20260310` 对应 scenario + KPI + report 绑定清单 | 罗顺雄 + 朱民峰 | `simctl asset-check` 和 mock/report 链路可跑，host-only 缺口明确 |
| REPORT-002 | Run/task ledger in digest | digest/report 增加 final status、blocked reason、track 分流 | 朱民峰 | 能区分 stable acceptance 与 shadow comparison |
| SYNTH-001 | Synthetic data admission gate | 合成数据入库检查表或 gate 草案 | 算法/仿真 owner | 每个 synthetic case 标注真实性/效用结论 |
| EMBODIED-001 | Embodied shadow task contract | 具身任务 shadow contract 文档 | 研究 owner | 明确 observation/comparison，不接管 stable 控制 |

## 5. 不导入的内容

- 不新增正式 simulator runtime。stable 基线仍是 `CARLA 0.9.15 / UE4.26`。
- 不把 Dora / 具身机器人方向写成当前 stable delivery。
- 不把大规模合成数据生产作为本季度 P0。
- 不把模型训练收益当作验证闭环证据。
- 不让 shadow 输出污染 stable acceptance。

## 6. 最近一周建议动作

1. 先建 DATA-001 的最小台账，挑 3 个历史现场问题做样例。
2. 用 `site_gy_qyhx_gsh20260310` 做 CASE-001 的第一条 public-road reusable case 晋升清单。
3. 在 report/digest 里统一 blocked reason，先不要做大 UI。
4. 给 synthetic / reconstruction / embodied 三类 research 输出加“不能作为 stable acceptance”的固定标记。
5. 周会只汇报进入链路的工件，不汇报泛泛研究方向。

## 7. 公开来源

- Autoware Foundation: `https://autoware.org/autowareio/synkrotron/`
- CARLA Ecosystem: `https://ecosystem.carla.org/`
- CARLA 文档 Synkrotron 页面：`https://carla-ue5.readthedocs.io/en/latest/ecosys_synkrotron/`
- Frost & Sullivan NIE 2025 活动页：`https://www.frostchina.com/zh/content/activity/detail/68c13a24f3453aa11bf233b8`
- Frost & Sullivan 合成数据报告 PDF：`https://img.frostchina.com/attachment/17573472/hAtSLAPtFpqSHWKCJdsGZh.pdf`
