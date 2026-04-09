# 团队 Agent 使用说明

这份文档用于说明当前仓库里的 agent 体系是什么、如何同步给其他电脑，以及团队成员如何按职责使用同一套 agent 规格。

如果你要看 repo-side skills，请同时看：

- `docs/TEAM_SKILL_USAGE_CN.md`
- `ops/skills/`

## 1. 这套 Agent 是什么

当前仓库已经把可复用的 agent 规格版本化进代码仓库。

这些规格不是“活的会话实例”，而是可重复创建的 agent 定义。  
只要其他成员拉取同一份仓库，并在支持 `spawn_agent` 的环境里使用，就可以重新创建出同样职责和提示词的 agent。

当前仓库内的 agent 规格目录是：

- `ops/subagents/`

加载逻辑在：

- `src/simctl/subagents.py`

命令行入口在：

- `python -m simctl subagent-spec`

## 2. 当前有哪些 Agent

目前仓库里固化了 6 个可复用 agent：

- `execution_runtime_explorer`
- `algorithm_research_explorer`
- `project_automation_explorer`
- `gaussian_reconstruction_explorer`
- `public_road_e2e_shadow_explorer`
- `stable_stack_host_readiness_explorer`

这些 agent 已经进入主线仓库，其他成员拉取最新 `main` 后即可使用。

这 6 个 agent 当前已经按最新主线重新收口到：

- 公司 Ubuntu 主机上的 `stable` 运行栈
- 公开道路资产与回归
- `BEVFusion + UniAD-style / VADv2 shadow`
- GitHub / Notion / issue pack / digest 自动化

## 3. 团队成员怎么用

### 朱民峰

优先使用：

- `stable_stack_host_readiness_explorer`
- `execution_runtime_explorer`

适用问题：

- 公司 Ubuntu 主机
- CARLA / Autoware bring-up
- `simctl run -> run_result -> report -> replay`
- runtime、health check、执行链路问题
- 并行槽位、端口、ROS domain 和 run-dir 隔离问题

### 罗顺雄 / lsx

优先使用：

- `gaussian_reconstruction_explorer`
- `execution_runtime_explorer`

适用问题：

- 公开道路资产束
- replay 模板
- pointcloud / lanelet / metadata 整理
- map refresh
- static Gaussian 研究入口

### 杨志朋

优先使用：

- `public_road_e2e_shadow_explorer`
- `algorithm_research_explorer`

适用问题：

- `BEVFusion` 感知基线
- `UniAD-style` / `VADv2` shadow
- 感知输出契约
- shadow planner 指标口径
- 公开道路 E2E 研究路线

### Codex PMO 支持位

优先使用：

- `project_automation_explorer`
- `algorithm_research_explorer`

适用问题：

- GitHub Project
- GitHub issue pack
- digest
- Notion / GitHub 同步
- 周会材料
- 阻塞项汇总

## 4. 其他电脑怎么同步

其他成员只要能访问这个仓库，就可以同步你的 agent 体系。

最小步骤：

1. 拉取仓库最新主线。
2. 安装仓库环境。
3. 列出 agent 规格。
4. 渲染指定 agent 的调用参数。

推荐命令：

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
python -m pip install -e .
python -m simctl subagent-spec --list
python -m simctl subagent-spec --name execution_runtime_explorer
python -m simctl subagent-spec --name execution_runtime_explorer --format spawn_json
```

### Mac 的推荐口径

如果你自己的 Mac 也要加入这套工作流，建议把它定位为：

- 代码同步终端
- Codex 工作终端
- 文档、digest、研究配置维护终端

不要把 Mac 当作正式 stable runtime 主机。  
Mac 侧具体步骤见：

- `docs/MAC_CODEX_WORKFLOW_CN.md`

## 5. 实际调用方式

### 查看全部规格

```powershell
python -m simctl subagent-spec --list
```

### 查看某一个 agent 的完整定义

```powershell
python -m simctl subagent-spec --name public_road_e2e_shadow_explorer
```

### 输出可直接用于 `spawn_agent` 的参数

```powershell
python -m simctl subagent-spec --name gaussian_reconstruction_explorer --format spawn_json
```

## 6. 这套 Agent 的边界

必须明确几件事：

- 仓库同步的是 agent 规格，不是实时会话。
- 其他成员可以重建同样的 agent，但不能直接接管你当前已经运行中的 agent。
- 如果仓库后续改成私有，其他成员必须先具备仓库访问权限。
- 如果成员本地没有支持 `spawn_agent` 的 Codex 环境，他们只能查看规格，不能真正启动 agent。

## 7. 推荐使用顺序

如果团队成员不知道先用哪个 agent，可以按这个顺序判断：

- 主机或稳定栈问题：`stable_stack_host_readiness_explorer`
- 执行链和结果问题：`execution_runtime_explorer`
- 公开道路 E2E 问题：`public_road_e2e_shadow_explorer`
- 三维重建问题：`gaussian_reconstruction_explorer`
- 多研究线总览问题：`algorithm_research_explorer`
- 看板、digest、同步问题：`project_automation_explorer`

## 8. 维护规则

后续如果你继续扩展 agent 体系，建议遵守这几条：

- 新 agent 一定先加到 `ops/subagents/`
- 同时补对应说明
- 明确 owner、适用问题和不要误用的场景
- 让团队成员只复用主线里已经稳定的 agent 规格，不直接用临时 prompt

## 9. 当前结论

结论很简单：

- 你的 agent 体系已经在仓库主线里
- 其他成员可以同步使用
- 当前标准入口不是某个单独的“我的 agent”命令，而是统一的 `subagent-spec`
- 仓库级默认规则也已经写入 `AGENTS.md`
- repo-side skills 也已经版本化进 `ops/skills/`

如果后面你想给这套 agent 体系再起一个更明确的团队名字，也可以继续在仓库里补一个别名入口。
