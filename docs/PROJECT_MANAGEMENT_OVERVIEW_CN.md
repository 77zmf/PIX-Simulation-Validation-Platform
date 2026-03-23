# 项目总览

## 1. 这个项目到底要做什么

这个项目不是单独搭一个 `Autoware` 或 `CARLA` 环境，而是建设一套面向自动驾驶算法验证的仿真底座，核心目标有四个：

- 建立 `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` 的稳定闭环主线
- 建立自动化验证、批量回归、回放和报告能力
- 复用现场地图与点云资产，沉淀 `site proxy` 和 `corner case`
- 为 `UE5` 和端到端算法准备下一周期的高保真实验线

## 2. 三个月内要完成什么

### 第 1 阶段：环境与最小闭环

- 准备 Windows 主机、WSL2、Ubuntu 22.04、ROS 2 Humble
- 准备 `Autoware Universe` 工作区
- 启动 `CARLA 0.9.15`
- 打通最小工作流：`bootstrap -> up -> run -> replay -> report`

### 第 2 阶段：自动化验证

- 打通 `autoware_carla_interface`
- 固化 L0 smoke 和 L1 回归场景
- 统一 `run_result.json`、回放入口和报告输出
- 建立 KPI 门禁和失败归因入口

### 第 3 阶段：现场资产与复杂场景

- 标准化 `gy_qyhx_gsh20260302` 资产束
- 沉淀至少 1 个 `site proxy` 场景
- 梳理 Top 5 `corner case`
- 将现场问题转成可复用的场景模板

### 并行准备：UE5 与端到端

- 准备远端 GPU 主机
- 准备 `UE5` 高保真实验线
- 准备端到端 `shadow` 指标与实验入口

## 3. 团队分工

- `朱民峰`：稳定主线、控制平面、自动化脚本、KPI、项目推进
- `罗顺雄 / lsx`：地图点云资产、`site proxy`、`corner case`
- `杨志鹏 / Zhipeng Yang`：UE5 远端实验线、感知 / E2E shadow

## 4. 未来端到端怎么做

当前最合适的路线不是直接学习油门、刹车和方向，而是先走：

- `BEV` 继续作为主感知基线
- `VAD` 作为感知 + 规划一体化端到端链路并行运行
- 先做 `shadow`，再做固定路线受控闭环
- 控制继续保留 `Autoware` 的经典控制链路和 fallback

也就是：

`BEV 基线 + VAD shadow -> 固定路线闭环 -> site proxy / corner case -> 后续微调`

## 5. 这套项目管理怎么看

### Notion

- 项目书：完整方案、范围、KPI、风险
- 项目总览与导航：一页看懂项目和入口
- 2026Q2 团队三个月执行计划：季度路线图
- 项目执行管理页：执行中枢
- Weekly Review Dashboard：每周推进模板
- Program Board / Scenario Backlog：任务和场景推进

### GitHub

- 仓库：脚本、配置、场景、KPI、适配器、部署说明
- GitHub Pages：展示项目目标、季度路线、团队分工、端到端路线和入口

## 6. 当前最关键的验收口径

- 至少 1 条稳定闭环链路可重复执行
- `bootstrap / up / run / batch / replay / report` 主链路可执行
- `gy_qyhx_gsh20260302` 形成标准资产束
- 至少 1 个 `site proxy` 场景进入验证流程
- `BEV 基线 + VAD shadow` 路线形成可执行方案
