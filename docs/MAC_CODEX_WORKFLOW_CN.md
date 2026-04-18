# Mac 拉取代码与 Codex 使用说明

这份文档给你自己的 Mac 用，目标不是在 Mac 上跑正式 `Autoware + CARLA` runtime，而是让 Mac 成为：

- 代码同步与日常修改入口
- Codex 工作入口
- 文档、任务、digest、研究配置查看与维护入口
- `simctl` 控制平面的轻量操作入口

正式稳定闭环仍然只在公司 `Ubuntu 22.04` 主机上运行。

## 1. Mac 的角色边界

Mac 可以做：

- 拉取和提交仓库代码
- 用 Codex 打开仓库并继续当前项目
- 查看与修改文档、场景、profile、KPI gate
- 运行 `simctl` 的非 runtime 重载命令
- 渲染 subagent 规格、整理 digest、更新项目材料

Mac 不负责：

- 正式运行 `CARLA 0.9.15 + Autoware Universe` 闭环
- 代替公司 Ubuntu 主机执行稳定栈主验收
- 代替公司 Ubuntu 主机做并行压测

## 2. 第一次准备

建议先安装这些基础工具：

- `git`
- `python3`
- `pip`
- 可选：`gh`

如果你用 Homebrew，可以参考：

```bash
brew install git python gh
```

## 3. 拉取仓库

如果是第一次：

```bash
cd ~/work
git clone https://github.com/77zmf/PIX-Simulation-Validation-Platform.git
cd zmf_ws
```

如果仓库已经在本地：

```bash
cd ~/work/zmf_ws
git pull --ff-only
```

## 4. 准备 Python 环境

```bash
cd ~/work/zmf_ws
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## 5. 在 Mac 上适合执行的命令

这些命令适合在 Mac 上跑：

```bash
python -m unittest discover -s tests -v
simctl subagent-spec --list
simctl subagent-spec --name execution_runtime_explorer
simctl subagent-spec --name execution_runtime_explorer --format spawn_json
simctl digest
simctl report --run-root runs
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed
```

这些命令不建议在 Mac 上作为正式主线执行：

```bash
simctl up --stack stable --execute
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --execute
```

原因很简单：正式稳定栈仍然绑定公司 Ubuntu 主机。

## 6. Mac 上如何继续 Codex 工作

你在 Mac 上只要做到这几步，就能延续当前这套仓库工作流：

1. 拉取最新 `main`
2. 打开仓库目录作为 Codex 工作区
3. 先看这几个入口文档：
   - `README.md`
   - `docs/PROJECT_MANAGEMENT_OVERVIEW_CN.md`
   - `docs/TEAM_AGENT_USAGE_CN.md`
   - `docs/TOMORROW_COMPANY_HOST_CHECKLIST_CN.md`
4. 需要 agent 时，先用：

```bash
simctl subagent-spec --list
```

常用入口：

- `stable_stack_host_readiness_explorer`
- `execution_runtime_explorer`
- `project_automation_explorer`
- `public_road_e2e_shadow_explorer`

## 7. Mac 与公司 Ubuntu 主机如何分工

推荐固定分工：

- Mac：写代码、改文档、看项目板、跑测试、生成 digest、渲染 subagent 规格
- 公司 Ubuntu 主机：跑 stable 栈、做环境 bring-up、做真实并行验证、生成正式 runtime 工件

这样可以避免把开发终端和正式运行主机混在一起。

## 8. 推荐日常同步流程

每天开始：

```bash
git pull --ff-only
source .venv/bin/activate
python -m unittest discover -s tests -v
```

改完代码后：

```bash
git status
git add <files>
git commit -m "docs(scope): update mac codex workflow"
git push
```

如果要切换到公司主机继续验证：

```bash
git push
# 然后在公司 Ubuntu 主机上 pull 最新 main
```

## 9. 你在 Mac 上最应该看的文件

- `README.md`
- `docs/PROJECT_MANAGEMENT_OVERVIEW_CN.md`
- `docs/TEAM_AGENT_USAGE_CN.md`
- `docs/MAC_CODEX_WORKFLOW_CN.md`
- `ops/subagents/`
- `src/simctl/`

## 10. 当前结论

结论就是：

- 你的 Mac 完全可以加入这套仓库工作流
- 但它是“开发与 Codex 协作终端”，不是正式 stable runtime 主机
- 正式闭环、并行回归和环境验收仍然放在公司 Ubuntu 主机上做
