# 计划同步快照（2026-03-24）

这份文档用于把仓库内已经确认的季度路线整理成一份可以同步到 GitHub 和 Notion 的统一口径。它不是新的方向提案，而是截至 `2026-03-24` 的执行快照。

## 当前主线

- 主交付仍然是 `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` 的稳定闭环
- 公司 `Ubuntu 22.04` 主机是稳定栈的主运行环境
- `bootstrap / up / run / batch / replay / report` 仍然是唯一认可的控制平面入口
- 场景主线已经切到公开道路资产和场景沉淀，不再只做抽象 `site proxy`
- 感知主线保持 `BEVFusion`
- 公开道路 `E2E shadow` 当前按两条线准备：
  - 主线：`BEVFusion + UniAD-style shadow`
  - 对照：`BEVFusion + VADv2 shadow`
- 三维重建按三段推进：
  - 当前季度：`map refresh`
  - 中期方向：`static Gaussian reconstruction`
  - 后续方向：`dynamic Gaussian reconstruction`

## 未来两周执行重点

### P0：先把真实验证链路打通

- 完成公司 Ubuntu 主机的访问、网络和开发权限确认
- 完成 `ROS 2 Humble`、Autoware 工作区和依赖准备
- 在公司 Ubuntu 主机上拉起 `CARLA 0.9.15`
- 打通 `autoware_carla_interface`
- 产出第一条真实 `run_result.json`

### P1：把公开道路资产变成可重复输入

- 固化 `gy_qyhx_gsh20260302` 的 lanelet、projector、pointcloud 和 metadata
- 产出第一条公开道路 replay 模板
- 固化至少 1 个高价值公开道路 corner case 模板

### P2：给下阶段算法研究准备入口

- `BEVFusion` 继续服务传统 planning/control 和 shadow planner
- `UniAD-style` 和 `VADv2` 只做 `trajectory-level shadow`，不做直接控制接管
- 三维重建先完成 `map refresh -> static Gaussian` 的研究入口，不进入本季度主交付

## GitHub / Notion 同步结论

### GitHub

- 仓库侧计划文档已经切换到公司 Ubuntu 主机口径
- GitHub Task Board 和 Scenario Board 作为公开执行镜像继续保留
- Digest workflow 继续作为自动提醒入口

### Notion

- 项目书、执行页、Weekly Review、Program Board 已同步到 Ubuntu 主机方案
- 未来两周任务排期已经改成四月初完成环境搭建和自动化数据闭环
- `杨志朋 / Zhipeng Yang` 已作为统一姓名口径出现在项目文案中

## 可行性判断

结论：当前计划可行，但前提是保持分阶段推进，不能把所有研究线同时拉成真实训练和闭环交付。

### 本季度可完成

- 一条稳定闭环验证链
- 一套可重复的公开道路资产和场景模板
- `BEVFusion` 感知基线接入公开道路研究流程
- `UniAD-style` / `VADv2` 的 shadow 研究入口和评估口径
- 三维重建的 `map refresh` 基线，以及 `static Gaussian` 的研究准备

### 不适合作为本季度主交付

- 直接端到端控制接管
- 大规模 UE5 高保真公开道路生产验证
- 动态 Gaussian 进入正式生产链
- 同时把 `UniAD-style`、`VADv2`、`Hydra-NeXt` 和动态重建都做成真实闭环系统

## 当前最大风险

- 真实 `--execute` 路径还没有在公司 Ubuntu 主机上打通
- 第一条公开道路场景还没有从资产结构推进到稳定回归输入
- SMTP、远端 GPU、UE5 仍依赖外部资源，不应反向阻塞当前主线

## 决策规则

- 能提升稳定闭环、回归自动化、公开道路场景复用或下季度 shadow 准备的事项，进入主线
- 不能直接支撑上述目标的事项，不进入本季度主线
- 三维重建必须优先服务地图刷新、定位回归和场景复现，不单独追求展示效果
