# Codex 项目快照（PIX Simulation Validation Platform）

## 1. 项目一句话
这是一个围绕 `Autoware Universe + ROS 2 Humble + CARLA 0.9.15` 的自动驾驶仿真验证控制平面仓库，主目标不是“搭环境演示”，而是把 `bootstrap / up / run / batch / replay / report / digest` 变成可复现、可回归、可交付的验证主链。

## 2. 当前季度主线
1. 在公司 Ubuntu 22.04 主机上打通 `stable` 栈闭环。
2. 把 `simctl` 变成团队日常使用的控制平面。
3. 把 `site_gy_qyhx_gsh20260302` 和相关 corner case 沉淀成可复用资产与场景。
4. 保持 `BEVFusion + UniAD-style / VADv2 shadow` 为受控研究线，不阻塞稳定主线。

## 3. 当前边界
- 正式稳定闭环只在公司 Ubuntu 22.04 主机上跑。
- Mac / Windows 负责代码、文档、Codex 协作、digest、轻量 `simctl` 操作。
- 本季度不做直接端到端控制接管。
- AI 只用于 digest、报告解释、失败归因、文档与代码辅助，不进入实时控制闭环。

## 4. 主数据流
`资产束/场景定义 -> simctl run 或 batch -> Autoware + CARLA 执行 -> run_result.json -> KPI gate -> report / replay -> digest`

## 5. 交付层次
- 控制平面：`src/simctl/`
- 运行平面：`stack/`、`infra/ubuntu/`
- 资产与场景层：`assets/`、`scenarios/`、`adapters/profiles/`
- 评测与运营层：`evaluation/kpi_gates/`、`ops/`、`docs/`

## 6. 关键现状
- 仓库已经有 repo-level `AGENTS.md`、subagent 规格、repo-side skills、GitHub-only digest automation 方向。
- 当前最重要的缺口仍是“真实 Ubuntu 主机 bring-up 与闭环结果收尾”，而不是再扩更多 agent。
- `launch_submitted` 不能被视为最终闭环，最终应落到可解释的 `passed / failed` 与 KPI 结果。

## 7. Codex 在这个仓库里最该做什么
- 帮忙读懂和修改 `simctl` 控制平面代码与配置
- 整理 run / batch / report / digest 相关问题
- 对齐项目计划、阶段目标、验收口径
- 根据子 agent / skill 边界，把任务导向合适入口
- 输出可执行的 next actions、验证步骤和 rollback 说明

## 8. Codex 不该做什么
- 把自己当作 runtime 控制器
- 忽略主机边界，直接把 Mac/Windows 当正式验证主机
- 用临时脚本绕过 `simctl` 和既有 runbook
- 把研究线建议混成稳定主线结论
