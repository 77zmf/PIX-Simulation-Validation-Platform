# 项目管理总览

## 1. 当前管理口径

当前仓库项目管理已经统一到 GitHub，不再依赖外部文档系统，也不再通过邮件提醒。

当前唯一正式管理入口：

- GitHub 仓库：`77zmf/PIX-Simulation-Validation-Platform`
- GitHub Task Board：`Project 2`
- GitHub Scenario Board：`Project 3`
- GitHub Digest Issue：仓库内 `project-digest` 标签 issue

## 2. 管理目标

本仓库的项目管理不是单纯记任务，而是服务下面几件事：

- stable 闭环验证持续可跑
- `simctl` 自动化链路持续可用
- 公共道路资产与 corner case 持续沉淀
- shadow 研究线不阻塞主线
- 每周能通过 digest 和 GitHub 看板快速判断风险、阻塞和责任人

## 3. 当前结构

### Task Board

用于维护：

- 环境搭建
- Autoware / CARLA 主线联调
- 自动化脚本
- KPI 与报告
- 研究线预研任务

### Scenario Board

用于维护：

- site proxy 场景
- corner case 场景
- 回归场景
- shadow 对比场景

### Digest Issue

用于自动汇总：

- 逾期任务
- 近期待办
- 阻塞项
- 逾期场景
- 近期场景
- 运行结果摘要

## 4. 运行方式

本仓库当前项目管理自动化入口：

```bash
python -m simctl digest --config ops/project_automation.yaml --output-dir artifacts/project_digest
```

GitHub Actions 会做：

- 定时生成 digest
- 上传 digest 工件
- 写入 workflow summary
- 更新 GitHub digest issue

## 5. 团队执行要求

- 所有正式任务必须进 GitHub Task Board
- 所有正式场景必须进 GitHub Scenario Board
- owner、status、due date、track、blocked 字段必须维护
- digest 只基于 GitHub Project 生成，字段缺失会直接影响管理质量

## 6. 当前结论

当前仓库已经切换成 GitHub-only 项目管理模式：

- 不再维护第二套外部项目看板
- 不再走邮件提醒接口
- 统一以 GitHub Project + GitHub issue digest 为管理主链路
