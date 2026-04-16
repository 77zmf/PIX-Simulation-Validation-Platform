# AI超体计划-自动驾驶仿真验证平台建设（Codex 版整理）

> 来源：项目计划书 V1.0（2026-03-24）与当前仓库现状对齐版  
> 用途：给 Codex 作为项目上下文，而不是正式汇报排版稿

## 一、项目背景与目标

### 1.1 研发现状与痛点
当前研发链路已经具备 `Autoware + CARLA` 仿真验证雏形，但仍有三类核心问题：

1. **环境与执行链路依赖人工串联**  
   环境准备、仿真启动、单场景运行、回放和报告仍依赖人工切脚本和手工记录，复现成本高，真实闭环难以稳定重跑。  
   **期望解法**：以 `simctl` 统一 `bootstrap / up / run / batch / replay / report`，再用 AI 做 digest、失败归因和摘要。

2. **公开道路资产难沉淀成标准场景**  
   公开道路地图、点云、现场问题和 corner case 分散在不同来源。  
   **期望解法**：用标准结构沉淀 `lanelet / pointcloud / metadata`，并形成 scenario backlog、回归模板和复盘摘要。

3. **多条算法路线同时推进但缺少统一指标口径**  
   规划控制、感知、E2E shadow 与重建路线并行时，容易出现“能展示但不可回归、能试验但不可交付”。  
   **期望解法**：统一 `run_result`、`KPI gate`、报告模板和周度 digest，帮助团队把判断收敛到“闭环可复现、场景可回归、指标可解释”。

### 1.2 项目目标
围绕稳定闭环、自动化验证、公开道路资产复用和下阶段 E2E shadow 预备四个方向，本季度最小交付目标为：

- **目标一**：在 2026-04-05 前完成公司 Ubuntu 22.04 主机基础环境准备，打通  
  `simctl run -> run_result.json -> report -> replay` 的最小数据闭环。
- **目标二**：在本季度内形成 1 条可重复执行的  
  `Autoware Universe + ROS 2 Humble + CARLA 0.9.15` 稳定闭环，并固化控制平面。
- **目标三**：标准化 `site_gy_qyhx_gsh20260302` 公开道路资产束，沉淀首个可回放公开道路场景，并为  
  `BEVFusion + UniAD-style shadow / VADv2` 对照实验准备输入与指标。

### 1.3 非目标
- 本季度不做直接端到端控制接管。
- 本季度不以大规模 UE5 高保真公开道路生产验证为目标。
- 本季度不追求一次做完动态 Gaussian、全量场景库和完整邮件/Notion 自动同步。

## 二、三阶段交付计划

### Phase 1：MVP / 跑通核心流程
- **目标时间**：2026-04-05
- **核心目标**：完成公司 Ubuntu 主机基线核验与最小闭环验证。
- **主要交付**：
  - Ubuntu host 准备脚本与 runbook
  - CARLA 0.9.15 / ROS 2 Humble / Autoware 工作区基线
  - `simctl bootstrap` 与 L0 smoke `run_result.json`
  - `report.md / report.html`
- **完成标志**：
  - 主机权限、依赖与 dpkg 状态明确
  - `simctl run` 成功产出 `run_result.json`
  - `simctl report` 与 replay 入口可用

### Phase 2：功能完善 / 稳定性提升
- **目标时间**：2026-05-03
- **核心目标**：打通稳定闭环与回归自动化，补齐 KPI 门禁和场景执行链路。
- **主要交付**：
  - `autoware_carla_interface` 最小链路
  - `L0 smoke + L1 regression` 场景集
  - KPI gate 配置与 failure taxonomy
  - `batch / replay / report` 标准流程
- **完成标志**：
  - 至少 1 条稳定闭环路线可重复执行
  - `L1 regression` 可批量跑通
  - 结果可自动汇总为报告与 digest

### Phase 3：优化上线 / 收尾交付
- **目标时间**：2026-06-14
- **核心目标**：完成公开道路资产与场景沉淀，并准备下一周期的 E2E shadow 入口。
- **主要交付**：
  - `gy_qyhx_gsh20260302` 标准资产束
  - 首个公开道路 replay 场景与 Top 5 corner case 清单
  - `BEVFusion` 感知评测基线
  - `UniAD-style shadow / VADv2` 对照指标草案
- **完成标志**：
  - 至少 1 个公开道路场景进入统一验证流程
  - 资产结构、场景、报告和 owner 节奏形成闭环
  - 下季度可在不重设计架构前提下接入 `UE5 / E2E shadow`

## 三、初步技术路径

### 3.1 整体架构
系统按四层设计：

1. **控制平面**  
   以 `simctl` 作为统一 CLI 入口，负责编排 `bootstrap / up / run / batch / replay / report`。

2. **运行平面**  
   公司 Ubuntu 22.04 主机承载 `ROS 2 Humble / Autoware Universe / autoware_carla_interface / CARLA 0.9.15`；本地 Windows 仅负责代码管理、远程触发和结果查看。

3. **资产与场景层**  
   公开道路 `lanelet / pointcloud / metadata / scenario YAML / adapter profile / stack profile` 统一入库；大文件通过 manifest 或外部存储引用。

4. **评测与运营层**  
   `run_result.json / KPI gate / report / replay / digest` 串成闭环；GitHub 是当前正式管理入口。

### 3.2 技术选型
- 前端/展示：GitHub Pages + Markdown 报告（计划书中曾提 Notion，但当前仓库已收敛到 GitHub-only 管理）
- 后端：Python 3.11 + `simctl`
- 数据：YAML / JSON / Markdown / artifacts
- AI：OpenAI API / Codex / 自定义脚本
- 部署与运维：Ubuntu 22.04 主机 + Windows/WSL 管理端 + GitHub Actions
- 仿真与算法：ROS 2 Humble / Autoware Universe / autoware_carla_interface / CARLA 0.9.15 / BEVFusion

### 3.3 关键技术难点与应对
1. **Autoware + CARLA + bridge 联调复杂**  
   应对：固定 Ubuntu 22.04 为正式运行环境，用 `simctl` 和 runbook 固化启动顺序与 smoke 验证。

2. **公开道路资产格式不统一**  
   应对：统一 `lanelet2_map.osm + map_projector_info.yaml + pointcloud_map.pcd/ + metadata.yaml` 结构，场景全部通过 YAML + manifest 管理。

3. **多算法线并行推进导致“能展示但不可回归”**  
   应对：统一 `run_result -> KPI gate -> report` 口径；稳定主线优先，E2E 先做 shadow。

### 3.4 待确认 / 待调研
- 远端 GPU 主机与 UE5 执行资源是否稳定可用
- `BEVFusion -> shadow planner` 的接口契约、延迟预算与指标口径

### 3.5 交付形式
最终交付按五类呈现：
1. 运行侧：Ubuntu host 上可重复执行的命令链
2. 资产侧：标准化公开道路资产束、scenario YAML、adapter/stack profile
3. 结果侧：`run_result.json`、`report.md / report.html`、replay 入口、KPI gate 结果
4. 管理侧：GitHub Project、digest、审阅入口
5. 决策侧：阶段验收标准、周会材料和 owner 级 next actions

## 四、AI 资源预算（保留项目语义）
- OpenAI API 通用文本模型：digest、周报、方案整理、代码辅助
- 批量分析任务：回归报告解释、场景问题归因、文档改写
- 关键里程碑多模型复核：关键节点才开启
- 建议：Phase 1 小额试跑，Phase 2 再按实际 token 消耗扩容

## 五、团队与协作方式

### 成员分工
- **朱民峰**：项目 owner / 稳定主线负责人  
  公司 Ubuntu 主机环境、Autoware + CARLA 主链路、`simctl` 控制平面、KPI 与验收
- **罗顺雄（lsx）**：资产与场景负责人  
  公开道路地图点云资产、重建输入、corner case、场景模板
- **杨志朋（Zhipeng Yang）**：感知与 E2E 预备负责人  
  `BEVFusion` 基线、公开道路感知评测、`UniAD-style / VADv2` shadow 输入与评测
- **Codex PMO 支持位**：项目推进与自动化支持  
  digest、周会材料、阻塞项汇总、文档和看板同步

### 协作约定
- 例会：每周一启动会、周三阻塞清理、周五 Weekly Review
- 沟通与管理：GitHub Project / Issues 为正式主链路
- 代码管理：主分支维护稳定基线，功能开发走 feature 分支，配置与场景变更必须可追踪
- 文档沉淀：`docs/`、项目板、digest

## 六、主要风险
- **高**：公司 Ubuntu 主机 dpkg / DKMS / 驱动状态异常，阻塞依赖安装
- **高**：Autoware + CARLA + bridge 联调链路长，短期难形成稳定闭环
- **中**：公开道路资产字段不统一，场景难复用
- **中**：远端 GPU、UE5、SMTP 等外部资源未到位

## 七、Codex 使用建议
- 先读 `README.md`、根目录 `AGENTS.md`、`docs/CODEX_PROJECT_SNAPSHOT_CN.md`
- 涉及主机 bring-up 时，再读 `docs/TOMORROW_COMPANY_HOST_CHECKLIST_CN.md`
- 涉及 run / report / replay 时，优先走 `execution_runtime_explorer`
- 涉及项目节奏、digest、owner next action 时，优先走 `project_automation_explorer`
