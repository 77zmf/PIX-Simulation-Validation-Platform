# 项目管理总览

## 1. 这个项目在做什么

这个仓库不是单独搭一套 `Autoware` 或 `CARLA` 环境，而是在建设一套面向自动驾驶研发的仿真验证平台。当前主线聚焦四件事：

- 在公司 `Ubuntu 22.04` 主机上稳定运行 `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15 + UE4.26`
- 固化 `bootstrap / up / run / batch / replay / report` 自动化链路
- 复用公开道路地图、点云、重建输入和问题案例，沉淀 `site proxy` 与 `corner case`
- 在同一条 `CARLA 0.9.15` 运行基线上保留 `BEV / VAD / UniAD-style / E2E shadow` 研究入口

## 2. 本季度目标

本季度的交付目标是：

- 完成公司 Ubuntu 主机环境搭建
- 打通第一条可重复执行的稳定闭环链路
- 形成第一条自动化数据闭环
- 标准化 `gy_qyhx_gsh20260302` 公开道路资产束
- 建立首批可回归场景和 `Top 5 corner case`

当前硬门槛：

- `2026-04-05` 前完成 Ubuntu 主机 bring-up 和 `simctl run -> run_result.json -> report -> replay`

## 3. 当前技术路线

### 稳定主线

- 主运行环境：公司 `Ubuntu 22.04`
- 主仿真栈：`Autoware Universe main + ROS 2 Humble + CARLA 0.9.15 + UE4.26`
- 控制平面：`simctl`
- 当前唯一正式运行栈：`stable`

### 并行执行路线

- 当前已经引入 `stable` 栈单机多槽位模型
- 槽位配置文件：`stack/slots/stable_slots.yaml`
- 每个槽位都有独立：
  - `slot_id`
  - `carla_rpc_port`
  - `traffic_manager_port`
  - `ros_domain_id`
  - `runtime_namespace`
  - `gpu_id`
  - `cpu_affinity`
- 当前建议默认用 `--parallel 2` 运行，4 槽位配置先保留用于压测

### 场景与资产主线

- 第一批公开道路资产束：`site_gy_qyhx_gsh20260302`
- 资产目标结构：
  - `lanelet2_map.osm`
  - `map_projector_info.yaml`
  - `pointcloud_map.pcd/`
  - `metadata.yaml`
- 大文件不直接入 Git 历史，通过 manifest 或外部存储引用

### 算法研究线

当前研究路线统一在 `CARLA 0.9.15 / UE4.26` 上推进：

`BEVFusion 基线 -> UniAD-style shadow 主线 -> VADv2 对照 -> 受控闭环验证`

约束：

- `BEVFusion` 继续承担主感知基线
- `UniAD-style` 先做 shadow，不直接接管控制
- `VADv2` 作为对照线，用于比较轨迹差异和行为分歧
- 所有研究线共享同一条 `stable` 栈和同一套运行时

## 4. 团队分工

- `朱民峰`：稳定主线、Ubuntu 主机、控制平面、自动化、KPI 和项目推进
- `罗顺雄 / lsx`：公开道路地图点云资产、重建输入、corner case、现场问题前移
- `杨志朋 / Zhipeng Yang`：`BEVFusion` 基线、公开道路感知、E2E shadow 研究
- `Codex PMO 支持位`：每日 digest、周会材料、阻塞项聚合、仓库侧管理同步

## 5. 管理结构

### Notion

- 项目书：完整方案、范围、KPI、风险
- 项目总览：一页看懂项目和入口
- Program Board：任务、里程碑、风险、两周排期
- Scenario Backlog：场景来源、优先级、成功信号
- Weekly Review：每周推进和阻塞复盘

### GitHub

- 仓库：代码、脚本、配置、场景、文档
- Task Board：任务执行看板
- Scenario Board：场景执行看板
- Digest Inbox：自动汇总提醒入口

## 6. 当前最该盯的事

1. 完成公司 Ubuntu 主机访问、权限和基础依赖准备
2. 在公司 Ubuntu 主机上拉起 `CARLA 0.9.15`
3. 编译 `Autoware Universe` 并打通 `autoware_carla_interface`
4. 用第一条 L0/L1 场景产出真实 `run_result.json`
5. 把 `gy_qyhx_gsh20260302` 整理成首个可回归的公开道路资产束
6. 先把 `--parallel 2` 跑稳，再做 4 槽位压测

## 7. 本季度验收口径

- 至少 1 条稳定闭环链路可重复执行
- `bootstrap / up / run / batch / replay / report` 主链路可用
- `gy_qyhx_gsh20260302` 形成标准资产束
- 至少 1 个公开道路场景进入验证流程
- `stable` 栈支持单机多槽位并行回归
- GitHub / Notion 双看板和 digest 提醒保持同步
