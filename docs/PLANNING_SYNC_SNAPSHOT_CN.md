# 计划同步快照（2026-03-24）

这份文档用于把仓库内已经确认的季度路线，整理成一份可以同步到 GitHub 和 Notion 的统一口径。它不是新的方向提案，而是截至 2026 年 3 月 24 日的执行快照。

## 当前主线

- 主交付仍然是 `Autoware Universe main + ROS 2 Humble + CARLA 0.9.15` 的稳定闭环。
- `bootstrap / up / run / batch / replay / report` 仍然是唯一认可的控制平面入口。
- 场景主线已经切到公开道路，不再把 `site proxy` 当成默认研究口径。
- 感知主线保持 `BEVFusion`。
- 公开道路 `E2E shadow` 当前按两条线准备：
  - 主线：`BEVFusion + UniAD-style shadow`
  - 对照：`BEVFusion + VADv2 shadow`
- 三维重建已经拆成三段：
  - 当前季度：`map refresh`
  - 中期方向：`static Gaussian reconstruction`
  - 未来方向：`dynamic Gaussian reconstruction`

## 两周执行重点

### P0：先把真实验证链打通

- 完成 `WSL2 + Ubuntu 22.04 + ROS 2 Humble` 的稳定运行环境。
- 拉起 `Autoware Universe` 工作区并打通 `autoware_carla_interface`。
- 产出第一条真实闭环 `run_result.json`，不再只依赖 synthetic metrics。

### P1：把公开道路资产变成可重复输入

- 固化 `gy_qyhx_gsh20260302` 的 lanelet、projector、pointcloud 和 metadata。
- 产出第一条公开道路 replay 模板。
- 固化至少 1 个高价值公开道路 corner case 模板。

### P2：给下周期算法研究准备稳定入口

- 感知线继续固定为 `BEVFusion`，先服务传统 planning/control 和 shadow planner。
- `UniAD-style` 和 `VADv2` 都只做 `trajectory-level shadow`，不做直接控制接管。
- 三维重建先完成 `map_refresh -> static_gaussians`，动态 GS 只保留研究入口，不进本季度主交付。

## GitHub / Notion 同步结论

### GitHub

- 仓库内计划文档已经是最新口径。
- 当前机器可读写仓库内容和 issue。
- 当前 GitHub token 只有 `gist, repo, workflow` scope。
- 当前机器不能直接读写 GitHub Project v2，因为缺少 `read:project` / `project` scope。

### Notion

- 仓库已经配置了 Notion 数据源 URL。
- 当前机器没有 `NOTION_TOKEN`。
- 当前机器的 Codex 配置原先没有启用 `rmcp_client`；该前置项已补上。
- 仍然需要执行 Notion OAuth 登录，或者提供 `NOTION_TOKEN`，之后才能真正更新 Program Board / Scenario Backlog。

## 可行性判断

结论：当前计划可行，但前提是保持分阶段推进，不能把所有研究线同时拉成真实训练和闭环交付。

### 可在本季度完成

- 一条稳定闭环验证链。
- 一套可重复的公开道路资产和场景模板。
- `BEVFusion` 感知基线接入公开道路研究流程。
- `UniAD-style` / `VADv2` 的 shadow 研究入口和评估口径。
- 三维重建的 `map refresh` 基线，以及 `static Gaussian` 的研究准备。

### 不适合在本季度当主交付

- 直接端到端控制接管。
- 大规模 UE5 高保真公开道路生产验证。
- 动态 `4DGS` 变成正式生产链。
- 同时把 `UniAD-style`、`VADv2`、`Hydra-NeXt`、动态 GS 都做成真实闭环系统。

## 当前最大风险

- `--execute` 真实路径仍然是占位逻辑，真实运行结果还不能自动回填 gate。
- GitHub Project v2 仍然缺 scope，公开执行看板无法直接同步。
- Notion 仍然缺登录态或 token，详细计划板无法直接落库。
- 远端 GPU、SMTP、UE5 仍依赖外部资源，不应该作为当前主线阻塞项。

## 决策规则

- 能提升稳定闭环、回归自动化、公开道路场景复用、下周期 shadow 准备的事项，进入主线。
- 不能直接支撑这四项的内容，不进入本季度主线。
- 三维重建必须优先服务地图刷新、定位回归和场景复现，不单独追求论文式展示效果。
