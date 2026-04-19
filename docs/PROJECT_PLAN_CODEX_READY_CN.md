# PROJECT_PLAN_CODEX_READY_CN.md

> 来源：基于当前仓库现状整理的 Codex 可执行计划
> 目标：不是做展示型规划，而是让 Codex 能直接围绕交付闭环拆任务、读代码、落文档、给出改造建议

## 一、项目目标重述

围绕这个仓库，我建议把季度目标重述成下面四个可落地的工程目标：

### 目标 1：把稳定主线真正闭到最终结果
不是只把 `simctl run` 启起来，而是把下面链条打通：

`scenario -> execute -> runtime evidence -> final KPI -> report/replay -> digest`

**验收口径**
- 至少 1 个稳定 case 能形成最终 `passed/failed`
- `launch_submitted` 只作为中间态存在
- 结果能追溯到 host readiness、运行证据和 artifacts

### 目标 2：把公开道路 bundle 晋升成可复用验证 case
不是只完成文件整理，而是形成：

`asset bundle -> semantic check -> scenario template -> executable case -> regression candidate`

**验收口径**
- 至少 1 个公开道路 case 进入统一验证链
- 输入资产、场景 YAML、KPI gate、报告入口可追溯
- 能被后续 corner case / replay 重复复用

### 目标 3：把 shadow 研究线变成“可比较、不可阻塞”的研究支线
以 `BEVFusion` 作为主线感知基线，`UniAD-style / VADv2` 只做 shadow 比较。

**验收口径**
- 有明确的比较指标口径
- 报告中与稳定主线分栏
- 不影响 stable acceptance 结论

### 目标 4：把 Codex 用在“工程收口”，不是“替代运行”
Codex 的职责应集中在：
- 工程上下文理解
- 任务拆解
- 缺口定位
- 文档/配置/脚本/测试补齐
- digest / triage / 失败归因

---

## 二、分阶段实施建议

## Phase 0：收口策略冻结（建议 2~3 天）
### 目标
先冻结稳定主线的“结果契约”，避免后面边做边漂。

### 交付
- `run_result` 最终字段表
- `runtime_evidence` 草案
- `host_bom / preflight_report` 草案
- `stable_acceptance` 与 `shadow_comparison` 报告骨架

### 建议改动
- 新增文档：`docs/RUNTIME_RESULT_CONTRACT_CN.md`
- 新增 schema：`evaluation/schemas/*.json`

### Done
- 团队对最终结果对象和状态语义达成一致

---

## Phase 1：稳定主线 finalize + evidence（建议 1~2 周）
### 目标
让 stable 主线第一次真正完成“启动成功 -> 运行完成 -> 有最终结论”。

### 核心任务
#### STABLE-001：`simctl finalize`
建议新增：
- `src/simctl/finalize.py`
- CLI 子命令：`simctl finalize --run-dir ...`

职责：
- 收集工件路径
- 写 `runtime_evidence.json`
- 调 KPI gate
- 输出 final status
- 清理 slot / 进程状态

#### STABLE-002：host BOM / preflight
建议新增：
- `infra/ubuntu/export_host_bom.sh`
- `src/simctl/evidence.py` 或 `src/simctl/runtime.py` 增补 host 信息落盘逻辑

职责：
- 固定 host 版本信息
- 每次 run 关联环境基线
- readiness 变成工件而不是口头信息

#### STABLE-003：slot 生命周期
建议新增：
- slot lease / ttl
- finalize/abort 后释放逻辑
- 异常退出的回收路径

### 验收
- 至少 1 个 L0/L1 stable case 形成最终 `passed/failed`
- run artifact 能回答“在哪台主机、什么基线、什么结果、为什么”

---

## Phase 2：公开道路 case 晋升（建议 1~2 周）
### 目标
把 `site_gy_qyhx_gsh20260310` 从资产束提升到真正的可执行 case。

### 核心任务
#### ASSET-001：semantic asset-check
建议在现有 `asset-check` 上增加语义层验证：
- route reachability
- projector consistency
- pointcloud metadata consistency
- localization seed plausibility

#### SCENARIO-001：public-road reusable case promotion
建议沉淀：
- `site proxy` 场景模板
- executable case
- regression candidate
- 对应 KPI gate 与报告模板

### 验收
- 至少 1 个公开道路 case 能进入统一验证流程
- case 具备复用价值，而不是一次性 demo

---

## Phase 3：stable 与 shadow 报表分流（建议 1 周）
### 目标
把“交付结论”和“研究结论”分开，避免报告层语义污染。

### 核心任务
#### REPORT-001：双轨报告
新增两个 section：
- `stable_acceptance_summary`
- `shadow_comparison_summary`

#### RESEARCH-001：比较口径固化
至少比较：
- route completion
- collision
- TTC
- trajectory quality
- behavior / rule compliance
- fallback trigger

### 验收
- 周会和项目判断只看 stable acceptance
- shadow 结果进入技术研究讨论，不直接代替交付结论

---

## Phase 4：项目状态与验证状态统一（建议 3~5 天）
### 目标
让 digest / board 状态不再与 run gate 各说各话。

### 核心任务
#### PMO-001：状态语义统一
建议把项目状态和验证状态映射固定下来，例如：
- `planned`
- `launch_failed`
- `launch_submitted`
- `runtime_collecting`
- `passed`
- `failed`
- `blocked`
- `needs_assets`
- `needs_host`

### 验收
- digest 中 blocker 与实际验证缺口一致
- owner next action 能落到代码、资产、环境或项目层

---

## 三、建议补齐的代码与文档位置

### 代码侧
- `src/simctl/cli.py`
- `src/simctl/runtime.py`
- `src/simctl/reporting.py`
- `src/simctl/evaluation.py`
- `src/simctl/finalize.py`（建议新增）
- `src/simctl/evidence.py`（建议新增）

### 基础设施侧
- `infra/ubuntu/`
- `stack/profiles/stable.yaml`
- `stack/slots/stable_slots.yaml`
- `stack/stable/*.sh`

### 资产与场景侧
- `assets/manifests/`
- `scenarios/`
- `adapters/profiles/`
- `evaluation/kpi_gates/`

### 文档与规范侧
- `docs/RUNTIME_RESULT_CONTRACT_CN.md`（建议新增）
- `docs/CODEX_PROJECT_SNAPSHOT_CN.md`
- `docs/CODEX_TASK_ROUTING_CN.md`
- `docs/PROJECT_PLAN_CODEX_READY_CN.md`

### 测试侧
- `tests/test_finalize.py`
- `tests/test_runtime_evidence.py`
- `tests/test_report_contract.py`

---

## 四、推荐的状态机

建议把 stable-line 运行状态机明确成：

1. `planned`
2. `launch_failed`
3. `launch_submitted`
4. `runtime_collecting`
5. `passed`
6. `failed`

其中：
- `launch_submitted`：说明启动和初步探针通过，但还没有最终运行证据
- `runtime_collecting`：说明正在等待 recorder / bag / metrics / final gate
- `passed/failed`：才是可交付结果

---

## 五、Codex 在这个项目上的最佳工作方式

### 最适合 Codex 的工作
- 读代码定位缺口
- 维护 AGENTS / 路由 / prompt / digest
- 生成和更新 schema / checklist / runbook
- 帮你梳理最小安全改动
- 帮你把任务拆到代码目录、验证方法和 owner next action

### 不适合 Codex 的工作
- 替代实时驾驶控制
- 在未知 host 状态下无约束 execute
- 把临时脚本堆成正式流程
- 以“研究演示”代替“验证闭环”

---

## 六、建议立即给 Codex 的前三个任务

### 任务 1
```text
Read src/simctl/, stack/profiles/stable.yaml, stack/slots/stable_slots.yaml, evaluation/, and tests/.
Design the smallest safe finalize/evidence pipeline that turns launch_submitted into a final passed/failed result.
```

### 任务 2
```text
Read infra/ubuntu/, src/simctl/runtime.py, and report-related code.
Propose how to persist host readiness and software BOM into run artifacts with minimal disruption to the current stable stack.
```

### 任务 3
```text
Read assets/manifests/, scenarios/, adapters/profiles/, and evaluation/kpi_gates/.
Propose how to promote site_gy_qyhx_gsh20260310 into the first reusable public-road validation case.
```
