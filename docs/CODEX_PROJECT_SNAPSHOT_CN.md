# CODEX_PROJECT_SNAPSHOT_CN.md

> 用途：给 Codex 一个紧凑、工程化的项目快照
> 范围：只描述当前仓库主线，不代替完整设计文档

## 1. 项目一句话摘要

这是一个围绕 `Autoware Universe + ROS 2 Humble + CARLA 0.9.15` 搭建的**仿真验证控制平面仓库**。
仓库重点是把 `bootstrap / up / run / batch / replay / report / digest` 统一到 `simctl`，并沉淀公开道路资产、场景模板、KPI 门禁、报告和项目节奏。

## 2. 当前最重要的判断

### 已经比较成型的部分
- `simctl` 作为统一 CLI 已经覆盖主要验证入口
- `stack profile + slots` 已经具备稳定栈编排意识
- `assets / scenarios / adapters / evaluation` 分层比较清晰
- 已经开始把 repo 做成 Codex 可消费的工程上下文
- 稳定主线与研究线的边界是清楚的：主线优先，shadow 不接管

### 当前最关键的缺口
1. **真实运行闭环还没最终收口**
   - 当前要补的是真实 execute 之后的 finalize / evidence / final gate
2. **公开道路资产还要再向“可复用 case”晋升**
   - 不能停留在 bundle 已整理、文件已齐的阶段
3. **重建线缺真实图像/视频输入**
   - 在有真实输入前，COLMAP / Gaussian 只能做工具和流程层 readiness

## 3. 主线原则

### 稳定主线
- 以公司 Ubuntu 22.04 主机为正式运行环境
- 以 `stable` stack 为正式执行栈
- 以 `CARLA 0.9.15` 为唯一正式仿真运行时
- 以 `run_result -> KPI gate -> report/replay -> digest` 为正式交付链

### 研究线
- 感知稳定基线保持 `BEVFusion`
- `UniAD-style / VADv2` 先走 shadow / comparison
- 研究线不阻塞稳定主线
- 不把直接端到端控制接管作为当前阶段目标

## 4. 对 Codex 最有价值的任务类型

1. **稳定栈运行闭环收口**
2. **主机 readiness 和软件基线沉淀**
3. **公开道路资产 -> 场景 -> 回归 case 晋升**
4. **run_result / KPI / report / digest 状态统一**
5. **shadow 对比报告和接口契约梳理**

## 5. 建议 Codex 优先关注的工程对象

- `src/simctl/`
- `stack/profiles/`
- `stack/slots/`
- `stack/stable/`
- `infra/ubuntu/`
- `assets/manifests/`
- `scenarios/`
- `evaluation/`
- `tests/`
- `ops/`

## 6. 当前推荐的工程改造方向

### P0：运行闭环
- 增加 finalize / collect 阶段
- 明确 runtime evidence contract
- 让 `launch_submitted` 成为中间态，而不是“仿佛完成态”

### P1：主机与环境基线
- 增加 `host_bom.json`
- 增加 `preflight_report.json`
- 把环境 readiness 结果写入运行工件

### P1：资产与场景
- 在 `asset-check` 之上增加语义级检查
- 增加 `scenario-check`
- 固化首个公开道路可回归 case

### P2：报告与项目运营
- stable acceptance 与 shadow comparison 分离
- digest 使用与 run gate 一致的状态语义
- 增强 failure taxonomy

## 7. 建议增加的目录/文件（最小增量方案）

- `src/simctl/finalize.py`
- `src/simctl/evidence.py`
- `evaluation/schemas/runtime_evidence.schema.json`
- `evaluation/schemas/run_result.schema.json`
- `infra/ubuntu/export_host_bom.sh`
- `tests/test_finalize.py`
- `tests/test_runtime_evidence.py`
- `docs/RUNTIME_RESULT_CONTRACT_CN.md`

## 8. Codex 看到项目时应该先记住什么

- 这不是缺少“agent 数量”的问题，而是缺少“真实闭环收口”
- 任何建议都应优先强化 `simctl` 主链，而不是旁路脚本
- 任何研究建议都要明确标注“不阻塞稳定主线”
- `launch_submitted` 不是最终验证结果
- 可复用 case 的沉淀，和真实运行闭环一样重要
