# 分支测试默认流程

这份文档定义 Codex 的默认分支测试行为：以后只要用户说明要测试哪个分支、PR、tag 或 commit，Codex 就按这里选择对应验证，不需要每次重新解释流程。

目标不是无差别跑完整仿真，而是像 `zmf_test_data` 一样，根据变更范围选择最相关、最小但可追溯的测试集。

## 1. 用户输入

用户可以只给一个对象：

```text
测试 <branch>
测一下 <PR>
验证 <tag>
检查 <commit>
```

如果用户没有给场景、KPI 或 owner，Codex 默认从分支 diff、场景文件、KPI gate、README、issue 或 PR 描述里推断。
只有当本地未提交改动会被覆盖、分支不存在、或者真实运行主机信息缺失时，才需要先追问。

## 2. 开始前检查

每次先保护工作区：

```bash
cd /Users/cyber/Documents/zmf_ws
git status --short --branch
git fetch origin
```

如果对象是远端分支：

```bash
git switch <branch>
git pull --ff-only origin <branch>
```

如果对象是 commit：

```bash
git switch -c validation/<short-name> <commit>
```

切换后确认变更范围：

```bash
git diff --name-only origin/main...HEAD
git diff --stat origin/main...HEAD
```

如果仓库默认基线未来不是 `main`，以当时的默认分支或 PR base 为准。

## 3. 变更范围到测试选择

| 变更范围 | 默认测试 | 是否需要 Ubuntu 主机 |
|---|---|---|
| `src/simctl/`、`tests/` | `python -m unittest discover -s tests -v`，再跑相关 `simctl` 命令 | 只有涉及 `--execute`、runtime、slot 或 host evidence 时需要 |
| `scenarios/` | 场景 YAML 检查，相关 `simctl run` 或 `simctl batch --mock-result passed`，`simctl report` | L0/L1 真闭环需要 |
| `evaluation/`、KPI gate、report | 单元测试，mock run，`simctl report --run-root runs`，必要时检查 `run_result.json` 状态语义 | final gate 绑定真实 runtime evidence 时需要 |
| `assets/`、`tools/`、公开道路 bundle | `simctl asset-check --bundle ...`，相关工具 smoke，必要时 mock scenario | 资产进入 stable closed-loop 时需要 |
| `stack/`、`infra/ubuntu/` | 配置审查，shell 脚本静态检查，Mac 上只做非 runtime dry-run | 需要，正式 readiness 和 bring-up 必须在公司 Ubuntu 22.04 主机 |
| `adapters/profiles/`、shadow research | 配置检查、指标契约检查、相关 mock run 或 report | 不作为 stable acceptance，必要时只做 shadow 对比 |
| `ops/`、digest、项目自动化 | `simctl digest`，项目配置检查，必要时读 board/digest 输出 | 通常不需要 |
| 纯文档 | 链接和命令口径检查，确认没有改变 runtime contract | 不需要 |

默认先跑本地安全验证，再明确剩余 host-only 验证。
不要把 Mac 上的 mock/dry-run 结果说成正式 stable closed-loop 通过。

## 4. Mac 本地默认验证

Mac 是代码同步和轻量验证入口。默认命令从下面选择，不要求每次全跑：

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed
simctl report --run-root runs
simctl digest
```

公开道路资产相关分支优先补充：

```bash
simctl asset-check --bundle site_gy_qyhx_gsh20260302
simctl asset-check --bundle site_gy_qyhx_gsh20260310
```

重建资产相关分支可以补充：

```bash
python tools/validate_reconstruction_assets.py --bundle site_gy_qyhx_gsh20260310
```

## 5. Ubuntu 主机真实验证

分支涉及 stable runtime、launch、slot、host readiness、Autoware、CARLA、closed-loop KPI 时，正式验证必须在公司 Ubuntu 22.04 主机执行。

主机侧准备：

```bash
cd ~/work/zmf_ws
git fetch origin
git switch <branch>
git pull --ff-only origin <branch>
source .venv/bin/activate
bash infra/ubuntu/preflight_and_next_steps.sh
bash infra/ubuntu/check_host_readiness.sh
simctl bootstrap --stack stable
```

真实 stable 线建议先 L0，再 L1：

```bash
simctl run \
  --scenario scenarios/l0/robobus117th_town01_closed_loop.yaml \
  --run-root runs \
  --execute

simctl batch \
  --scenario-dir scenarios/l1 \
  --run-root runs \
  --parallel 2 \
  --execute

simctl report --run-root runs
```

正式结论必须能追到：

```text
run_result.json -> KPI gate -> report -> replay
```

如果结果只停在 `launch_submitted`，结论是 `blocked` 或 `incomplete`，不是 `passed`。

## 6. 输出格式

每次分支测试结束，按下面口径回复：

```text
验证对象：
- branch / PR / tag / commit:
- base:
- commit:

范围判断：
- 变更目录：
- 测试选择原因：

执行环境：
- Mac 本地：
- Ubuntu stable runtime：

执行命令：
- ...

证据：
- run_result.json:
- report:
- replay:
- digest / asset-check / logs:

结论：
- passed / failed / blocked

剩余风险：
- host-only validation:
- stub/mock 部分：
- rollback:
```

## 7. 边界

- 不为了单个分支新增一次性脚本，优先复用 `simctl`。
- 不把 shadow research 输出当作 stable acceptance。
- 不把截图、启动日志或 `launch_submitted` 当作最终验证结果。
- 大地图、点云、重建输出和模型权重仍然留在 Git 外，通过 manifest 或路径引用。
- 如果分支修改了 runtime contract，回复必须说明如何运行、哪个场景验证、哪个 KPI 或 observable 应改变、什么仍是 stub、如何回滚。
