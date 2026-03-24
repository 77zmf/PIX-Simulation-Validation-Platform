# 项目复盘与优化建议

## 当前结论

这套项目目前已经具备了“管理层 + 控制平面 + 自动化层”的基础闭环，但距离“团队可持续使用的公开道路仿真验证平台”还差 3 个关键落地点：

- 真实运行时环境还没有在公司 Ubuntu 主机上完成闭环打通
- 公开道路地图资产、重建输入和场景模板还没有形成第一批可重复回归的正式场景
- 自动提醒已经能产出 digest，但邮件发送和 UE5 远端执行仍受外部条件约束

所以当前问题不是“缺方向”，而是“要把已经确定的方向从骨架推到稳定执行态”。

## 已经做对的地方

### 1. 项目路线已经收敛

- 主线明确为 `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15`
- 场景主线明确为公开道路资产 + 高价值 corner case
- 算法路线明确为 `BEVFusion` 基线 + `UniAD-style shadow` 主线 + `VADv2` 对照
- `UE5 / E2E` 被明确放到下一阶段预备线，而不是反向拖慢本季度交付

### 2. 管理层已经成型

- Notion 已覆盖项目书、季度计划、Program Board、Scenario Backlog 和 Weekly Review
- GitHub 已覆盖任务看板、场景看板、公开主页和 digest issue
- Notion 负责详细计划，GitHub 负责公开执行镜像和自动提醒

### 3. 控制平面已经有骨架

- `simctl` 已覆盖 `bootstrap / up / down / run / batch / replay / report / digest / notion-check`
- GitHub Actions 已覆盖基础检查和项目 digest
- digest 已经能在没有 SMTP 的情况下安全退化到 issue 和 artifact

## 当前遗漏

### 1. 真运行时仍是第一缺口

仓库和自动化更多解决的是“控制平面”和“项目管理”，并没有替代真实环境联调。现在必须真正落地但还没完成的是：

- 公司 Ubuntu 主机访问、网络和权限确认
- `ROS 2 Humble`、`colcon`、`rosdep` 和基础依赖安装
- `Autoware Universe` 工作区拉起与首次编译
- `CARLA 0.9.15` 在公司 Ubuntu 主机上稳定启动
- `autoware_carla_interface` 真实桥接打通
- 第一条 L0 smoke 路线产出真实 `run_result` 和报告

如果这部分继续延迟，项目会停留在“管理很清楚，但验证还没落地”的状态。

### 2. 公开道路资产还停留在结构化阶段

你们已经定义了资产束结构、Scenario Backlog 和 Top 5 corner case 方向，但还缺：

- 第一批真实 `metadata.yaml`
- 第一批标准化 lanelet / pointcloud 目录
- 第一条公开道路 replay 模板
- 第一组能复现场景问题的参数化 corner case

### 3. 自动化还有两个外部依赖

- 邮件提醒还缺 SMTP Secrets
- UE5 / 高保真实验还缺远端 GPU 节点

这两件事不会阻塞当前主线，但会影响团队提醒效率和下一阶段切换速度。

## 我建议的优化顺序

### P0：先把主线从“骨架”变成“真闭环”

这一阶段只做 4 件事：

- 完成公司 Ubuntu 主机环境准备
- 拉起 `Autoware Universe` 工作区
- 拉起 `CARLA 0.9.15`
- 打通第一条 L0 smoke 闭环并产出报告

只有这一段落地，项目才真正从“准备阶段”进入“可验证阶段”。

### P1：把公开道路资产和场景从目录变成验证输入

- 先做 `gy_qyhx_gsh20260302` 的完整资产束
- 再做 1 个公开道路 replay 模板
- 再做 1 个现场问题复现的 corner case 模板

重点不是数量，而是形成可重复运行的模板。

### P2：把提醒系统从 digest 升级成团队习惯

- SMTP 打通后开启邮件提醒
- 每周 review 固定引用 digest issue 和最新报告
- 所有阻塞项都必须在 GitHub Project 里显式标记 `Blocked`

### P3：让下阶段平滑进入公开道路 E2E shadow

- 明确 `BEVFusion` topic、输出结构和 planner 输入契约
- 固化 `UniAD-style` 主 shadow、`VADv2` 对照的评测口径
- 先 shadow，再固定路线受控闭环，不直接做端到端控制接管

## 当前最值得盯的 6 个动作

1. 完成公司 Ubuntu 主机的开发访问和权限准备
2. 在公司 Ubuntu 主机上稳定启动 `CARLA 0.9.15`
3. 编译 `Autoware Universe` 并准备 `autoware_carla_interface`
4. 用第一条 L0 smoke 路线生成真实 `run_result.json`
5. 把 `gy_qyhx_gsh20260302` 资产整理成公开道路标准目录
6. 明确远端 GPU 节点的规格、访问方式和负责人

## 管理原则建议

- 本季度新增工作必须能回答“是否提升稳定闭环、自动回归、公开道路场景复用或下季度 E2E 准备”
- 如果不能支撑上述目标，就不进入本季度主线
- 项目书和主页继续保持“对外清楚、对内可执行”，但工程资源优先投给真实闭环，而不是继续扩展示层
