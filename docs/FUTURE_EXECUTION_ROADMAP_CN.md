# 未来执行路线图

这份文档用于把当前项目从“启动执行”继续推进到“季度交付”和“下一阶段研发布局”。

时间口径以 `2026-03-26` 为准，默认前提是：

- 稳定主线仍是 `Autoware Universe + ROS 2 Humble + CARLA 0.9.15`
- 公开道路是主要研究语境
- `BEVFusion` 继续作为感知基线
- `UniAD-style shadow` 是主研究入口，`VADv2 shadow` 是对照线
- 三维重建按 `map refresh -> static Gaussian -> dynamic Gaussian` 分阶段推进

## 一、未来两周

目标：先把“能执行”变成“可重复交付”。

### P0：稳定栈与真实闭环

- 完成公司 Ubuntu 主机访问、依赖、权限和网络清单
- 拉起 `CARLA 0.9.15`
- 准备 Autoware 工作区与 `autoware_carla_interface`
- 拿到第一条真实 `run_result.json`
- 打通 `report` 和 `replay`

### P1：公开道路资产

- 标准化 `gy_qyhx_gsh20260302` 资产束
- 固化 lanelet / projector / pointcloud / metadata
- 产出第一条 replay 模板
- 产出至少 1 个高价值 corner-case 模板

### P1：感知与 Shadow E2E

- 冻结 `BEVFusion` 感知输出契约
- 建立 `BEVFusion -> shadow planner` 输入映射
- 确定 `UniAD-style` 与 `VADv2` 的第一版指标口径

### P1：项目节奏

- 每个 owner 在 GitHub issue 中持续回报 blocker、next action、交付日期
- digest 和周会材料只做收口，不再扩任务面

## 二、本季度

目标：形成“稳定验证主线 + 公开道路研究副线”的最小闭环。

### 稳定验证主线

- 至少 1 条稳定闭环路径可重复通过
- `bootstrap / up / run / batch / replay / report` 日常可用
- 至少 1 条 L0 smoke 和 1 条 L1 regression 场景稳定复现

### 公开道路资产主线

- 第一套公开道路资产束可直接被场景引用
- Top 5 corner case 形成模板化定义
- 公开道路 replay 入口可复用，不再依赖临时脚本

### 感知与 E2E 研究副线

- `BEVFusion` 感知基线服务主线和 shadow planner
- `UniAD-style shadow` 与 `VADv2 shadow` 都能进入同一套评价口径
- 研究只停留在 `trajectory-level shadow`，不做端到端控制接管

### 三维重建副线

- `map refresh` 成为公开道路资产更新入口
- `static Gaussian` 形成研究入口和采集要求
- 不把 `dynamic Gaussian / 4DGS` 当作本季度交付目标

## 三、下季度

目标：从“研究入口”推进到“可比较、可验证、可积累”。

### 稳定栈

- 将真实 `--execute` 路径进一步稳定化
- 补足 host readiness、health check、runtime telemetry
- 将验证流程从单次跑通升级为批量回归

### 公开道路验证

- 扩大 corner-case 覆盖面
- 增加 merge、unprotected left、occlusion、cut-in 等高价值场景
- 建立“现场问题 -> 场景模板 -> KPI gate -> 报告”的固定回路

### Shadow E2E

- 系统比较 `UniAD-style` 与 `VADv2` 的收益和失效模式
- 判断是否需要引入更强调闭环稳定性的路线
- 保持 classical planning/control 作为主线 fallback

### 重建

- 将 `static Gaussian` 与地图刷新、定位回归、replay 准备真正挂钩
- 决定是否有必要推进动态 actor 重建
- 如果动态收益不清晰，不进入正式交付

## 四、六到十二个月

目标：从项目验证平台成长为可复用的公开道路研发基础设施。

### 平台层

- 形成稳定的验证平台基线
- 将主机环境、验证流程、报告和场景资产管理固化
- 减少对个人经验和一次性脚本的依赖

### 算法层

- 感知、规划控制、shadow E2E 和三维重建形成可并行推进的研发轨道
- 每条研发轨道都能回到统一的验证口径
- 逐步形成可比较、可归档的算法证据库

### 资产层

- 建立持续积累的公开道路资产库
- 让 corner case、地图更新和回放资产进入周期性维护
- 让重建结果真正服务验证和场景复现，而不是只服务展示

## 五、不做什么

为了避免项目失控，以下方向默认不进入当前主线承诺：

- 不直接承诺端到端控制接管
- 不把大规模 UE5 高保真生产验证作为当前硬交付
- 不把 `dynamic Gaussian / 4DGS` 作为当前季度必须完成的目标
- 不在稳定闭环没打通前同时扩四条研究线的真实交付范围

## 六、推荐的 Agent 使用顺序

### 当前执行问题

- 稳定栈 / Ubuntu 主机：`stable_stack_host_readiness_explorer`
- `run_result` / runtime 问题：`execution_runtime_explorer`

### 研究路线问题

- 公开道路 E2E：`public_road_e2e_shadow_explorer`
- 三维重建：`gaussian_reconstruction_explorer`
- 多研究线总览：`algorithm_research_explorer`

### 管理与同步问题

- 看板 / digest / 同步：`project_automation_explorer`

## 七、更新原则

这份路线图应该只在以下情况更新：

- 阶段目标发生变化
- 主线阻塞导致季度目标需要调整
- 研究路线从“入口准备”升级到“真实对比验证”
- 团队成员或 owner 边界发生变化

如果只是单周任务变化，直接更新 GitHub issue，不改这份文档。
