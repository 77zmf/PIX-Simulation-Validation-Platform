# Windows Codex 工作流与 Repo-side 同步入口

对应 issue：

- [#12 仓库级 AGENTS 与 repo-side skills 安装入口](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/12)
- [#11 子agent上手、阅读顺序与协同约定](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/11)

这份文档服务两件事：

1. 让 Windows 电脑能稳定作为 Codex 开发与协作终端。
2. 让仓库内的 `AGENTS.md`、`ops/subagents/`、`ops/skills/` 变成可同步、可复用的 repo-side 默认入口。

它不负责把 Windows 电脑变成正式 `Autoware + CARLA` runtime 主机。正式 stable runtime 仍然只在公司 `Ubuntu 22.04` 主机上完成。

## 1. Windows 电脑的角色边界

Windows 电脑适合做：

- 拉取和提交仓库代码
- 运行 Codex
- 阅读和维护文档、issue、PR
- 运行 `simctl` 的本地 mock / report / digest / subagent-spec
- 作为 AGENTS 与 repo-side skills 的同步终端

Windows 电脑不负责：

- 正式 `simctl run --execute`
- 公司 Ubuntu 主机上的 stable 闭环验收
- 替代 `CARLA 0.9.15 + ROS 2 Humble + Autoware Universe` 正式 runtime

## 2. 最小前置条件

建议先准备这些工具：

- `git`
- `python`
- `ssh`
- 可选：`gh`
- Codex Desktop 或可用的 Codex 本地客户端

本仓库当前在 Windows 上验证通过的 Python 版本是：

- `Python 3.13.0`

## 3. 推荐目录

建议：

- 仓库：`D:\Git\PIX-Simulation-Validation-Platform`
- 本地资产根目录：`D:\PIX-Simulation-Validation-Assets`

## 4. 首次环境准备

```powershell
cd D:\Git
git clone https://github.com/77zmf/PIX-Simulation-Validation-Platform.git
cd D:\Git\PIX-Simulation-Validation-Platform

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
```

如需补 Windows 侧本地准备：

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\windows\bootstrap_host.ps1 `
  -WorkspaceRoot 'D:\Git\PIX-Simulation-Validation-Platform' `
  -AssetRoot 'D:\PIX-Simulation-Validation-Assets' `
  -Execute
```

## 5. 仓库内默认入口

先看：

1. `README.md`
2. `AGENTS.md`
3. `docs/TEAM_AGENT_USAGE_CN.md`
4. `docs/TEAM_SKILL_USAGE_CN.md`
5. `docs/WINDOWS_CODEX_WORKFLOW_CN.md`
6. `ops/subagents/`
7. `ops/skills/`

常用命令：

```powershell
.\.venv\Scripts\Activate.ps1
python -m simctl subagent-spec --list
python -m simctl subagent-spec --name execution_runtime_explorer
python -m simctl subagent-spec --name execution_runtime_explorer --format spawn_json
python -m unittest tests.test_research_configs -v
python -m unittest tests.test_cli -v
```

## 6. 本地 Codex 与仓库入口的关系

仓库内版本化的是：

- `AGENTS.md`
- `ops/subagents/`
- `ops/skills/`

本地 Codex 默认目录通常是：

- `%USERPROFILE%\.codex\AGENTS.md`
- `%USERPROFILE%\.codex\skills\`

当前推荐规则：

- 以仓库内 `AGENTS.md` 作为 repo-side source of truth
- 以仓库内 `ops/skills/` 作为 repo-side skills source of truth
- 不要只靠聊天记录复制 prompt
- 新电脑先拉仓库，再决定是否同步到本地 `%USERPROFILE%\.codex\`

## 7. Windows 上如何同步 repo-side 规则

仓库内已经提供同步脚本：

- [sync_repo_side_codex_assets.ps1](../infra/windows/sync_repo_side_codex_assets.ps1)

默认是 dry-run，只打印将要执行的动作，不会修改本地 `%USERPROFILE%\.codex\`：

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\windows\sync_repo_side_codex_assets.ps1
```

如果你确认要同步：

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\windows\sync_repo_side_codex_assets.ps1 -Execute
```

如果只想同步 skills：

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\windows\sync_repo_side_codex_assets.ps1 -SyncSkills -Execute
```

如果只想同步 `AGENTS.md`：

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\windows\sync_repo_side_codex_assets.ps1 -SyncAgents -Execute
```

脚本会：

- 默认把仓库 `AGENTS.md` 同步到 `%USERPROFILE%\.codex\AGENTS.md`
- 默认把 `ops/skills/<skill-name>/` 同步到 `%USERPROFILE%\.codex\skills\<skill-name>\`
- 在覆盖前自动备份到 `%USERPROFILE%\.codex\repo_sync_backups\<timestamp>\`

## 8. 当前 repo-side skills

当前仓库包含这些 skills：

- `autoware-bug-report`
- `autoware-release-check`
- `carla-case-builder`
- `simctl-run-analysis`
- `ai-superbody-pmo`

常用入口：

- [ops/skills/README.md](../ops/skills/README.md)
- [docs/TEAM_SKILL_USAGE_CN.md](./TEAM_SKILL_USAGE_CN.md)

## 9. 当前 repo-side subagents

当前仓库包含这些 subagents：

- `execution_runtime_explorer`
- `algorithm_research_explorer`
- `project_automation_explorer`
- `gaussian_reconstruction_explorer`
- `public_road_e2e_shadow_explorer`
- `stable_stack_host_readiness_explorer`

常用入口：

- [docs/SUBAGENT_CATALOG.md](./SUBAGENT_CATALOG.md)
- [docs/TEAM_AGENT_USAGE_CN.md](./TEAM_AGENT_USAGE_CN.md)

## 10. Windows 上已经适合做的验证

可做：

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest tests.test_research_configs -v
python -m unittest tests.test_cli -v
python -m simctl.cli --repo-root . run --scenario scenarios/l0/smoke_stub.yaml --run-root D:\PIX-Simulation-Validation-LocalCheck\runs --mock-result passed
python -m simctl.cli --repo-root . report --run-root D:\PIX-Simulation-Validation-LocalCheck\runs --output-dir D:\PIX-Simulation-Validation-LocalCheck\report
```

不建议在 Windows 上把下面这些当成正式验收：

```powershell
simctl up --stack stable --execute
simctl run --scenario ... --execute
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --execute
```

## 11. 当前结论

结论很简单：

- Windows 电脑完全可以作为这套仓库的 Codex / 文档 / mock / report / AGENTS / skills 同步终端
- 它可以把“repo-side 规则和 skill pack”同步得很完整
- 但它不能替代公司 Ubuntu 主机去产出正式 stable runtime 回执
