# Git 协作规范

这份文档用于统一 `pixmoving-moveit/zmf_ws` 的分支命名、commit 命名和提交流程，保证不同电脑、不同成员在同一套规则下协作。

## 当前仓库口径

- 当前仓库默认主分支是 `main`，不是 `dev/master`。
- 在这个仓库里，新分支默认从 `main` 切出，再提交 PR 到 `main`。
- 如果后续仓库正式切到 `dev/master` 双分支体系，以仓库当时的默认分支和保护策略为准。
- Codex 桌面环境创建分支时必须带 `codex/` 前缀，所以仓库内由 Codex 创建的分支统一使用 `codex/<标签>/<短名>`。

## 分支命名规则

分支名格式：

```text
codex/<tag>/<short-kebab-case>
```

允许的 `<tag>` 只有以下几类：

- `feature`: 新功能开发
- `bugfix`: 问题修复
- `adhoc`: 特殊部署、临时修复、临时功能
- `refactor`: 项目级重构
- `roadtest`: 多个功能集成后的路测联调

分支短名统一使用 `kebab-case`，避免空格、中文和大小写混用。

推荐示例：

- `codex/feature/subagent-specs`
- `codex/bugfix/runtime-launch-status`
- `codex/adhoc/org-repo-migration`
- `codex/refactor/profile-loader`
- `codex/roadtest/public-road-shadow-stack`

不建议继续使用的旧式命名：

- `codex/sync-subagent-specs`
- `codex/update-org-facing-links`

## Commit 命名规则

提交信息格式：

```text
type(scope): subject
```

允许的 `type`：

- `feat`: 新特性
- `fix`: 问题修复
- `refactor`: 代码重构
- `docs`: 文档修改
- `style`: 代码格式调整，不包含业务逻辑
- `test`: 测试用例修改
- `chore`: 其他杂项修改
- `pref`: 性能优化
- `build`: 构建系统或依赖修改
- `ci`: CI 修改
- `revert`: 回滚前一个提交

`scope` 建议写受影响的模块或目录，例如：

- `runtime`
- `simctl`
- `subagents`
- `project-automation`
- `docs`
- `evaluation`

`subject` 要求：

- 用英文短句
- 直接描述结果，不写废话
- 尽量控制在一行内

推荐示例：

- `feat(subagents): add reusable explorer specs`
- `fix(runtime): distinguish launch_failed from launch_submitted`
- `docs(git-workflow): add collaboration standard`
- `test(runtime): cover background step fast failure`
- `chore(project-automation): switch boards to org namespace`

如果需要更详细说明，可以在标题下补 body：

```text
fix(runtime): persist background logs to files

Redirect background stdout and stderr to per-step log files so long-running
stack processes do not block on PIPE backpressure.
```

## 命名习惯

统一采用以下命名方式：

- `name_name`: 适合 Python 变量、文件内局部标识
- `NameName`: 适合类名
- `nameName`: 适合部分前端或特定风格代码
- `name-name`: 适合仓库名、目录短名、分支短名、URL 路径

避免使用：

- `name_Name`

## 提交流程

标准流程如下：

1. 先同步远端主分支。
2. 从最新 `main` 切出自己的工作分支。
3. 开发完成后先自检，再 `rebase` 到最新 `origin/main`。
4. 提交 PR。
5. 路测或验证通过后再合并。
6. 合并完成后删除分支。

推荐命令：

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c codex/feature/example-work
```

提交前同步主线：

```bash
git fetch origin
git rebase origin/main
```

推送并建立远端分支：

```bash
git push -u origin codex/feature/example-work
```

## Commit 模板

仓库内已提供 commit 模板文件：

- `ops/git/commit-message-template.txt`

本机可执行：

```bash
git config commit.template ops/git/commit-message-template.txt
```

设置完成后，`git commit` 会自动带出模板骨架。

## PR 前检查

提交 PR 前至少确认：

- 分支名符合 `codex/<标签>/<短名>`
- commit 标题符合 `type(scope): subject`
- 已同步最新 `origin/main`
- 本地验证已通过
- PR 描述清楚变更目标、验证方式和风险
- 勾选“合并后删除分支”

## 当前仓库建议

结合当前仓库状态，后续建议统一使用：

- `codex/feature/...` 处理新功能与工具增强
- `codex/bugfix/...` 处理 runtime、CLI、报告和自动化问题
- `codex/adhoc/...` 处理组织迁移、链接修复、临时兼容
- `codex/roadtest/...` 处理公开道路 shadow 联调和多模块集成验证

文档更新后，其他电脑只要拉取仓库，就可以直接按这份规范执行。
