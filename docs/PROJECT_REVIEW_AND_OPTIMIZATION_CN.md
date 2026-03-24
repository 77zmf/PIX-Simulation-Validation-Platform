# 项目复盘与优化建议

## 当前结论

这套项目目前已经具备了“管理层 + 控制平面 + 自动化层”的基础闭环，但距离“公开道路可持续验证平台”还差 3 个关键落地点：

- 真实运行时环境还没有在当前宿主机上完成闭环打通
- 公开道路地图资产、重建输入和场景模板还没有形成可重复回归的第一批正式场景
- 自动提醒已经能出 digest，但邮件发送和远端 GPU 仍受外部条件约束

因此，这个项目当前不是“缺方向”，而是“需要把已经明确的方向从骨架推到稳定执行态”。

## 已经做对的地方

### 1. 项目方向已经重新收敛

- 主线明确为 `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15`
- 场景路线调整为 `公开道路结构化场景 + 高价值 corner case`
- 算法路线调整为 `BEVFusion 生产基线 + UniAD-style shadow 主线 + VADv2 对照`
- `UE5 / E2E` 仍然被明确放到下一周期预备线，而不是反向拖慢本季度主交付

### 2. 管理层已经成型

- Notion 已经覆盖项目书、季度计划、Program Board、Scenario Backlog 和 Weekly Review
- GitHub 已经形成任务看板、场景看板、公开主页和 digest issue
- 双层管理模式清楚：Notion 负责详细计划，GitHub 负责公开执行镜像与自动化输入

### 3. 控制平面和自动化骨架已经有了

- `simctl` 已经覆盖 `bootstrap / up / down / run / batch / replay / report / digest / notion-check`
- GitHub Actions 已经覆盖基础检查和项目 digest
- digest 已经能读取 GitHub / Notion 数据源、聚合提醒，并在无 SMTP 时退化到 issue 与 artifact

## 当前遗漏

### 1. 真实运行时仍是第一缺口

当前仓库和自动化更多解决的是“控制平面”和“项目管理”，并没有代替真实环境联调。真正必须完成但仍未完成的是：

- WSL2 + Ubuntu 22.04 的长期可用环境
- Autoware Universe 工作区拉起与编译
- CARLA 0.9.15 本机稳定启动
- `autoware_carla_interface` 真桥接打通
- 第一个真实闭环 `run_result` 和报告

如果这部分迟迟不落地，项目会停留在“管理很清楚，但验证还没落地”的状态。

### 2. 公开道路资产仍停留在结构化阶段

你们已经定义了资产束结构、Scenario Backlog 和 Top 5 corner case 方向，但还缺：

- 第一批真实 `metadata.yaml`
- 第一批标准化 pointcloud / lanelet 目录
- 第一条公开道路场景模板
- 第一组能复现现场问题的参数化 corner case

### 3. 自动化仍有两个外部依赖

- 邮件提醒还缺 SMTP Secrets
- UE5 / 高保真实验还缺远端 GPU 节点

这两件事不影响当前主线推进，但会影响“团队自动化”和“下一周期切换速度”。

## 我建议的优化顺序

### P0：把主线从“骨架”变成“真闭环”

这一阶段只做 4 件事：

- 在当前主机上完成 WSL2、Ubuntu 22.04、ROS 2 Humble 基础环境
- 拉起 Autoware Universe 工作区
- 拉起 CARLA 0.9.15
- 打通第一条 L0 smoke 闭环并产出报告

只有这一段落地，项目才真正从“准备阶段”进入“可验证阶段”。

### P1：把公开道路资产和场景从目录变成验证输入

- 先做 `gy_qyhx_gsh20260302` 的完整公开道路资产束
- 再做 1 个公开道路 replay 场景模板
- 再做 1 个现场问题复现 corner case

这里的重点不是场景数量，而是形成可反复运行的模板。

### P2：把提醒系统从 digest 升级成团队习惯

- SMTP 打通后开启邮件提醒
- 每周 review 固定引用 digest issue 和最新报告
- 所有阻塞项必须在 GitHub Project 中显式维护 `Blocked`

### P3：让下一周期平滑进入公开道路 E2E shadow

- 明确 `BEVFusion` topic、输出结构和 planner 输入契约
- 固化 `UniAD-style` 主 shadow 与 `VADv2` 对照的评测口径
- 先 shadow、再固定路线受控闭环，不直接做端到端控制接管

## 当前最值得盯的 6 个动作

1. 完成 WSL2 / Ubuntu 22.04 / ROS 2 Humble 基础环境
2. 在 Windows 主机上稳定拉起 CARLA 0.9.15
3. 编译 Autoware Universe 并准备 `autoware_carla_interface`
4. 用第一条 L0 smoke 路线生成真实 `run_result.json`
5. 把 `gy_qyhx_gsh20260302` 资产束整理成公开道路标准目录
6. 明确远端 GPU 节点的规格、访问方式和负责人

## 建议的管理原则

- 本季度所有新增工作，必须能回答“是否提升稳定闭环、自动化回归、公开道路场景复用或下周期 E2E 准备”
- 如果不能提升这四项之一，就不进入本季度主线
- 项目书和页面继续保持“对外清楚、对内可执行”，但工程资源优先投给真实闭环，而不是继续扩展展示层
