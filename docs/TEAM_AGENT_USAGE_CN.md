# 团队 Agent 使用说明

## 1. 目的

这份文档说明仓库里的 subagent 规格如何被团队复用，以及当前项目里每类 agent 的推荐边界。

当前仓库 agent 规格目录：

- `ops/subagents/`

调用入口：

- `python -m simctl subagent-spec`

## 2. 当前可复用 Agent

- `execution_runtime_explorer`
- `algorithm_research_explorer`
- `project_automation_explorer`
- `gaussian_reconstruction_explorer`
- `public_road_e2e_shadow_explorer`
- `stable_stack_host_readiness_explorer`

## 3. 团队使用边界

### 朱民峰

优先使用：

- `stable_stack_host_readiness_explorer`
- `execution_runtime_explorer`

适用问题：

- 公司 Ubuntu 主机
- CARLA / Autoware bring-up
- `simctl run -> run_result -> report -> replay`
- runtime、health check、执行链路
- 并行槽位、端口、ROS domain 和 run-dir 隔离

### 罗顺雄 / lsx

优先使用：

- `gaussian_reconstruction_explorer`
- `execution_runtime_explorer`

适用问题：

- 公共道路资产束
- replay 模板
- pointcloud / lanelet / metadata 整理
- map refresh
- static Gaussian 研究入口

### 杨志鹏

优先使用：

- `public_road_e2e_shadow_explorer`
- `algorithm_research_explorer`

适用问题：

- `BEVFusion` 感知基线
- `UniAD-style` / `VADv2` shadow
- 感知输出契约
- shadow planner 指标口径
- 公共道路 E2E 研究路线

### Codex PMO

优先使用：

- `project_automation_explorer`
- `algorithm_research_explorer`

适用问题：

- GitHub Project
- GitHub issue pack
- digest
- 周会材料
- 阻塞项汇总

说明：

- 当前项目管理已经统一到 GitHub-only
- 不再维护双系统同步
- 不再依赖邮件提醒接口

## 4. 其他电脑如何同步

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
python -m pip install -e .
python -m simctl subagent-spec --list
python -m simctl subagent-spec --name execution_runtime_explorer
python -m simctl subagent-spec --name execution_runtime_explorer --format spawn_json
```

## 5. 推荐选择顺序

- 主机或稳定栈问题：`stable_stack_host_readiness_explorer`
- 执行链和结果问题：`execution_runtime_explorer`
- 公共道路 E2E 问题：`public_road_e2e_shadow_explorer`
- 三维重建问题：`gaussian_reconstruction_explorer`
- 多研究线总览问题：`algorithm_research_explorer`
- 看板和 digest 问题：`project_automation_explorer`

## 6. 当前结论

- 团队 agent 规格已经版本化进仓库
- 其他成员拉最新 `main` 后即可复用
- 当前项目管理侧统一围绕 GitHub Project 和 digest 运行
