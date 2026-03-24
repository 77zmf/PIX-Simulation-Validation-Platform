# 项目管理总览

## 1. 这个项目到底要做什么

这个项目不是单独搭一套 `Autoware` 或 `CARLA` 环境，而是建设一套面向自动驾驶研发的仿真验证底座。当前聚焦 4 件事：

- 打通 `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` 的稳定闭环
- 固化自动化验证、回归、回放、KPI 门禁和报告
- 复用公开道路地图、点云、重建和问题案例，沉淀可复用场景与 corner case
- 为下一阶段的 `UE5 / E2E` 实验准备入口，但不破坏当前稳定主线

## 2. 本季度目标

当前项目按 12 周推进，本季度交付目标是：

- 在公司 `Ubuntu 22.04` 主机上完成稳定栈环境搭建
- 形成第一条可重复执行的闭环链路
- 打通 `simctl run -> run_result.json -> report -> replay` 数据闭环
- 标准化 `gy_qyhx_gsh20260302` 公开道路资产束
- 形成首批公开道路场景模板和 Top 5 corner case 清单
- 为 `BEVFusion + UniAD-style shadow` 和 `VADv2` 对照线准备受控实验入口

短期硬门槛：

- `2026-04-05` 前完成公司 Ubuntu 主机环境搭建和自动化数据闭环

## 3. 当前技术路线

### 稳定主线

- 公司 `Ubuntu 22.04` 主机作为稳定运行环境
- 同机运行 `ROS 2 Humble`、`Autoware Universe`、`autoware_carla_interface` 和 `CARLA 0.9.15`
- 本地电脑只负责代码管理、远程登录和结果查看
- `simctl` 是唯一认可的控制平面入口：
  `bootstrap / up / run / batch / replay / report`

### 场景与资产主线

- 首批公开道路资产束：`site_gy_qyhx_gsh20260302`
- 目标结构：
  - `lanelet2_map.osm`
  - `map_projector_info.yaml`
  - `pointcloud_map.pcd/`
  - `metadata.yaml`
- 大文件不直接进 Git 历史，统一通过 manifest 或外部存储引用
- 重建路线按阶段推进：
  - 当前季度：`map refresh`
  - 下一阶段：`static Gaussian reconstruction`
  - 更后续：`dynamic Gaussian reconstruction`

### 算法路线

当前推荐路线：

`BEVFusion 生产基线 -> UniAD-style shadow 主线 -> VADv2 对照 -> 受控闭环验证`

也就是说：

- `BEVFusion` 继续承担主感知基线
- `UniAD-style` 先做 shadow，不直接接管控制
- `VADv2` 作为对照路线，用于规划不确定性和行为比较
- 先做轨迹级和行为级验证，再决定是否进入更深的 E2E 路线

### 当前服务器编译基线

- 已有 `CARLA UE5` 源码开发线：`~/zmf_ws/projects/carla_source/CarlaUE5`
- 已有 `Autoware.Universe` 工作区线：`~/zmf_ws/projects/autoware_universe/autoware`
- 当前 Ubuntu host 的推进应沿用这两条现有目录，而不是完全从零重建

## 4. 团队分工

- `朱民峰`：稳定主线、控制平面、自动化、KPI、项目推进
- `罗顺雄 / lsx`：公开道路地图点云资产、重建输入、corner case、现场问题前移
- `杨志朋 / Zhipeng Yang`：`BEVFusion` 基线、公开道路感知与 E2E shadow 预备、UE5 远端实验线
- `Codex PMO 支持位`：每日 digest、周会材料、阻塞提醒、GitHub 和仓库侧管理同步

## 5. 管理结构

### Notion

- 项目书：完整方案、范围、KPI、风险
- 项目总览：一页看懂项目和入口
- 季度计划：12 周路线和验收口径
- Program Board：任务、里程碑、风险、未来两周排期
- Scenario Backlog：场景来源、优先级、成功信号
- Weekly Review：每周推进和阻塞复盘

### 团队机制

- 项目推进团队与作战机制：`docs/PROJECT_OPERATING_TEAM_CN.md`
- 团队由 3 个 owner 角色和 1 个 Codex PMO 支持位组成
- 目标是让“任务板 + digest + 周会 + owner 行动”形成持续推进闭环
- 已明确边界：每个 owner 只对自己的交付负责，Codex PMO 负责推动和提醒，不替代技术拍板

### GitHub

- 仓库：代码、脚本、配置、场景、文档
- GitHub Pages：公开项目主页
- GitHub Project 1：任务执行看板
- GitHub Project 2：场景执行看板
- Digest Inbox：自动汇总的提醒入口

## 6. 自动化怎么运行

当前自动化方案是：

- GitHub 双看板作为公开执行镜像
- `simctl digest` 每日汇总任务、场景、阻塞项和验证快照
- GitHub Actions 在工作日自动运行 digest
- 如果配置了 SMTP，则自动发邮件提醒团队
- 如果没有 SMTP，则保留 artifact、workflow summary 和 digest issue

## 7. 当前最该盯的事情

现阶段不要继续扩展示层，先抓住这 5 项：

1. 完成公司 Ubuntu 主机的访问、权限和基础依赖准备
2. 在公司 Ubuntu 主机上拉起 `CARLA 0.9.15`
3. 编译 `Autoware Universe` 并打通 `autoware_carla_interface`
4. 用第一条 L0 smoke 场景产出真实 `run_result.json`
5. 把 `gy_qyhx_gsh20260302` 整理成首个可复用公开道路资产束

## 8. 本季度验收口径

- 至少 1 条稳定闭环链路可重复执行
- `bootstrap / up / run / batch / replay / report` 主链路可用
- `gy_qyhx_gsh20260302` 形成标准公开道路资产束
- 至少 1 个公开道路场景进入验证流程
- Notion 和 GitHub 双看板保持同步管理
- 自动 digest 能输出按负责人聚合的提醒
