# 项目管理总览

## 1. 这个项目到底要做什么

这个项目不是单独搭一套 `Autoware` 或 `CARLA` 环境，而是建设一套面向自动驾驶研发的仿真验证底座。当前目标聚焦 4 件事：

- 打通 `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` 的稳定闭环
- 固化自动化验证、回归、回放、KPI 门禁和报告
- 复用现场地图、点云和问题案例，沉淀 `site proxy` 与 `corner case`
- 为未来 `UE5 / E2E` 实验线准备入口，但不破坏当前稳定主线

## 2. 当前完整项目周期

当前项目按 12 周推进：

### Weeks 1-2

- 准备 Windows、WSL2、Ubuntu 22.04、ROS 2 Humble
- 编译 Autoware 工作区
- 验证 CARLA 0.9.15 启动

### Weeks 3-4

- 打通 `autoware_carla_interface`
- 验证 clock、TF、控制反馈
- 固化 L0 smoke 与最小报告模板

### Weeks 5-6

- 跑第一批 L1 回归
- 固化 `run_result.json`、回放和报告
- 让自动化链路进入可重复使用状态

### Weeks 7-8

- 标准化 `gy_qyhx_gsh20260302` 资产束
- 整理地图、点云、rosbag、案例索引
- 完成 Top 5 corner case 首版梳理

### Weeks 9-10

- 让至少 1 个 `site proxy` 场景进入正常验证流程
- 完成至少 1 个高价值 corner case 复现

### Weeks 11-12

- 收口季度验收项
- 复盘阻塞项和风险
- 为下一周期的 `UE5 / E2E` 做好宿主、指标和入口准备

## 3. 可行性判断

### 现在就可行

- GitHub 双看板公开执行管理
- Notion 详细项目管理
- GitHub Pages 项目主页
- 仓库内控制平面与 digest 自动化

### 本季度可行

- 稳定主线最小闭环
- 自动化回归和 KPI 门禁
- 第一批 site proxy 资产和场景
- `BEV 基线 + VAD shadow` 的受控验证入口

### 依赖外部条件

- 邮件提醒需要 SMTP Secrets
- UE5 高负载实验需要远端 GPU 节点
- 真正大规模数字孪生不在当前季度主线

## 4. 当前技术路线

### 稳定主线

- Windows 主机负责 CARLA 图形和宿主编排
- WSL2 Ubuntu 22.04 负责 Autoware、ROS 2 和桥接
- `simctl` 统一负责 `bootstrap / up / run / batch / replay / report`

### 场景路线

- 先做 `site proxy`
- 再沉淀 Top 5 corner case
- 场景要做成模板，不做一次性脚本

### 算法路线

当前推荐路线是：

`BEV 基线 + VAD shadow -> 一致性评测 -> fallback 策略 -> 固定路线受控闭环`

也就是说：

- 现有 BEV 感知继续做主基线
- VAD 先做 shadow，不直接接管控制
- 先验证可行性，再进入下一周期更深的 E2E 路线

## 5. 当前管理结构

### Notion

- 项目书：完整方案、范围、KPI、风险
- 项目总览：一页看懂项目和入口
- 季度计划：12 周路线和验收口径
- Program Board：任务、里程碑、风险
- Scenario Backlog：场景来源、优先级、成功信号

### GitHub

- 仓库：代码、脚本、配置、场景、文档
- GitHub Pages：公开项目门户
- GitHub Project 1：任务执行看板
- GitHub Project 2：场景验证看板

## 6. 自动管理怎么做

当前自动管理方案是：

- GitHub 双看板作为公开执行镜像
- `simctl digest` 每日汇总任务、场景、阻塞项和验证快照
- GitHub Actions 在工作日自动运行 digest
- 如已配置 SMTP Secrets，则自动发邮件提醒团队
- 如未配置邮件，则保留 artifact、workflow summary 和 digest issue

## 7. 当前团队分工

- `朱民峰`：稳定主线、控制平面、自动化、KPI、项目推进
- `罗顺雄 / lsx`：地图点云资产、site proxy、corner case、现场问题前移
- `杨志朋 / Zhipeng Yang`：UE5 远端实验线、感知 / E2E shadow、GPU 条件准备

## 8. 本季度验收口径

- 至少 1 条稳定闭环链路可重复执行
- `bootstrap / up / run / batch / replay / report` 主链路可用
- `gy_qyhx_gsh20260302` 形成标准资产束
- 至少 1 个 `site proxy` 场景进入验证流程
- GitHub 双看板和 Notion 保持同步管理
- 自动 digest 可以生成 owner 维度提醒
