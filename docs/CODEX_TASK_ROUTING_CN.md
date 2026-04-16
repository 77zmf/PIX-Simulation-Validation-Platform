# Codex 任务路由表

> 目的：让 Codex 看到任务时，先知道该看哪里、跑什么、交给哪个子 agent、产出什么

## 1. 推荐读取顺序
1. `README.md`
2. `AGENTS.md` 或当前目录的 `AGENTS.override.md`
3. `docs/CODEX_PROJECT_SNAPSHOT_CN.md`
4. `docs/CODEX_TASK_ROUTING_CN.md`
5. 具体任务对应的专题文档 / 配置 / 脚本

## 2. 问题类型 -> 文件 -> 命令 -> agent/skill

| 问题类型 | 优先文件 | 常用命令 | 推荐 subagent | 推荐 skill | 默认输出 |
|---|---|---|---|---|---|
| Ubuntu 主机准备 / bring-up / 依赖问题 | `infra/ubuntu/`、`stack/profiles/stable.yaml`、`docs/TOMORROW_COMPANY_HOST_CHECKLIST_CN.md` | `bash infra/ubuntu/preflight_and_next_steps.sh`、`bash infra/ubuntu/check_host_readiness.sh`、`simctl bootstrap --stack stable` | `stable_stack_host_readiness_explorer` | `autoware-release-check`（如需 readiness 结论） | 缺项清单、补齐命令、风险、下一步 |
| `simctl run / batch / report / replay` 执行链问题 | `src/simctl/`、`stack/`、`evaluation/kpi_gates/`、`runs/` | `simctl run`、`simctl batch`、`simctl report`、`simctl replay` | `execution_runtime_explorer` | `simctl-run-analysis` | 根因、KPI 摘要、回放锚点、owner next action |
| 场景与资产标准化 | `assets/`、`scenarios/`、`adapters/profiles/` | `simctl batch --scenario-dir ... --mock-result passed` | `gaussian_reconstruction_explorer` 或 `public_road_e2e_shadow_explorer` | `carla-case-builder` | case 定义、输入资产、成功标准、验证方法 |
| BEVFusion / UniAD-style / VADv2 / 研究路线 | `adapters/profiles/`、`docs/ALGORITHM_RESEARCH_ROADMAP_CN.md` | 以配置梳理和接口审查为主，不默认要求真实 execute | `algorithm_research_explorer` 或 `public_road_e2e_shadow_explorer` | `simctl-run-analysis` 或 `carla-case-builder` | 接口契约、指标、差距、研究 next step |
| 项目管理 / digest / 周会材料 / board hygiene | `ops/project_automation.yaml`、`ops/issues/README.md`、`docs/PROJECT_MANAGEMENT_OVERVIEW_CN.md` | `simctl digest` | `project_automation_explorer` | `ai-superbody-pmo` | milestone 状态、阻塞、风险、owner next actions |

## 3. 本地机器与正式运行主机的边界

### Mac / Windows 上适合做的事
- 拉最新代码、写文档、改配置、读代码
- 运行单元测试
- 生成 digest、report
- 查看和渲染 subagent 规格
- 运行 mock batch 验证控制平面

### 只应在公司 Ubuntu 主机做的事
- 正式 `CARLA 0.9.15 + Autoware Universe` bring-up
- 正式 `simctl up/run/batch --execute`
- host readiness / dpkg / 驱动 / CUDA / TensorRT 补齐
- 并行槽位真实压测

## 4. Codex 输出模板
默认按下面七段输出，便于团队复用：

1. **objective**：这次问题要解决什么  
2. **scope / assumptions**：环境边界、是否 stub、是否需要 Ubuntu 主机  
3. **evidence**：具体文件、命令、日志、结果对象  
4. **analysis / decision**：原因判断或设计决策  
5. **changes / next steps**：具体改什么、谁来做  
6. **validation**：怎么验证、看哪些 KPI / 工件  
7. **risk / rollback**：风险点与回退方式

## 5. 特别提醒
- `launch_submitted` 不是最终闭环结果。
- 任何“建议加一个临时脚本”的想法，都应先检查能否扩展 `simctl`、profile、scenario、report 流程。
- 研究线建议必须标注“不会阻塞稳定主线”。
