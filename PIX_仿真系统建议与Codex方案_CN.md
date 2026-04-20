# PIX 仿真系统建议与 Codex 导入方案（基于 `77zmf/PIX-Simulation-Validation-Platform`）

## 1. 我对这个仓库的判断

这个仓库最强的部分，不是“仿真引擎本身”，而是**围绕仿真验证做控制平面、流程编排、报告、项目运营和 Codex 接入**。  
从结构上看，它已经有：

- `simctl` 统一入口：`bootstrap / up / run / batch / replay / report / digest`
- `stack/profile/slots` 机制：说明作者已经在把“环境启动”抽象成稳定栈
- `assets / scenarios / evaluation / adapters` 分层：说明项目不想再靠散乱脚本堆功能
- `AGENTS.override.md`、`codex_import_manifest.json`、`codex_automation_manifest.json`：说明项目已经开始把仓库做成 **Codex 可读的工程上下文**

但这个仓库当前最关键的问题也很明确：

1. **控制平面已经成型，但真实运行闭环还没有真正收口**  
   现在的主问题不是“再多加一个 agent”或“再写一个文档”，而是把真实 `Autoware + CARLA` 运行链闭到最终结果。

2. **`launch_submitted` 还不是最终可交付状态**  
   只说明启动链路和健康检查过了一部分，不代表形成了真实的“运行证据 -> KPI -> 报告 -> 回放”的闭环。

3. **公开道路资产已经在做标准化，但还没完全晋升为稳定可复用 case**  
   也就是从 `asset bundle` 到 `reusable scenario` 的“晋级链”还需要更强的制度化约束。

4. **研究线方向是对的，但必须继续 shadow-first**  
   继续以 `BEVFusion` 为稳定感知基线，`UniAD-style / VADv2` 先做 shadow 比较，不要直接进入端到端控制接管。

---

## 2. 我给你的核心建议

## 建议 A：把“真实闭环收口”提到绝对第一优先级

建议你把稳定主线的 done definition 明确改成：

`assets/scenario -> simctl run/up --execute -> runtime evidence -> finalized run_result -> KPI gate -> report/replay -> digest`

这里最重要的是多一个 **finalize / collect 阶段**。  
如果没有这个阶段，`run_result.json` 很容易只记录“发起过运行”，而不是“已经完成一次有证据的验证”。

### 建议新增能力
- `simctl finalize --run-dir <...>`
- `simctl collect --run-dir <...>`
- 或者在 `simctl run --execute` 之后自动进入 finalize

### finalize 至少要做的事
- 归档 rosbag / recorder / screenshot / log 路径
- 记录运行是否真正达到 `goal reached / timeout / collision / localization lost`
- 调 KPI gate
- 生成最终 `passed / failed`
- 回收 slot / 清理进程 / 写结束态

---

## 建议 B：把“稳定主线”和“研究线”彻底分叉为两条口径

现在仓库里已经在思想上做了这件事，但建议你在结构和报表上再走一步：

### 稳定主线（blocking）
- 目标：闭环可复现、可回归、可用于周会和项目判断
- 必须项：
  - 固定 host
  - 固定 stack profile
  - 固定 KPI gate
  - 固定 evidence contract
  - 最终状态必须是 `passed/failed`

### 研究线（non-blocking）
- 目标：比较 `BEVFusion baseline` 与 `UniAD-style / VADv2 shadow`
- 必须项：
  - 不接管实时控制
  - 不阻塞稳定主线
  - 输出比较报告而不是“替代上线结论”

建议在报告层直接分两个 section：
- `stable_acceptance_summary`
- `shadow_comparison_summary`

---

## 建议 C：把 Ubuntu host readiness 结果也变成 run artifact

现在这个仓库已经有 host 准备脚本和 readiness 思想，但建议你进一步产品化：

### 建议增加两类工件
- `host_bom.json`
- `preflight_report.json`

### 典型字段
- Ubuntu 版本
- GPU / Driver / CUDA / TensorRT
- CARLA build 信息
- Autoware workspace commit
- `autoware_carla_interface` commit
- ROS domain / ports / namespace
- 关键环境变量
- 依赖检查结论
- readiness pass/fail

这样每次 run 不只是“跑了”，而是知道**在什么 host 基线上跑的**。

---

## 建议 D：把公开道路资产从“文件齐”升级到“语义齐”

当前 `asset-check` 很适合做基础检查，但要想真正成为稳定 case，建议从“存在性检查”升级到“可执行性检查”：

### 资产语义检查建议
- `lanelet2_map.osm` 是否有可达路由
- `map_projector_info.yaml` 与地图原点是否一致
- `pointcloud_map_metadata.yaml` 与 tile 实际覆盖是否一致
- 关键起终点是否都能完成定位初始化
- scenario 中 route / ego spawn / sensor profile 是否与 bundle 兼容

建议把这部分变成：
- `simctl asset-check --semantic`
- `simctl scenario-check --scenario xxx.yaml`

---

## 建议 E：slot 现在更像“并行骨架”，还不是“高负载调度器”

从配置看，项目已经有 4 个 stable slot，这很好；但从工程现实看，**现在更适合 1~2 并行作为常态**。  
建议你给 slot 增加三个机制：

1. `lease / ttl`
   - 防止 external scenario 占住 slot 不释放

2. `cleanup policy`
   - down / finalize 失败时也要尽量释放资源

3. `pressure guard`
   - GPU / CPU / 内存压力超过阈值时，不再继续发新 run

---

## 建议 F：给 run_result 补“证据契约”

建议明确一个固定 contract，避免不同人、不同 run 的结果结构漂移。

### run_result 除现有字段外，建议新增
- `host_bom_path`
- `preflight_report_path`
- `runtime_evidence_path`
- `goal_status`
- `termination_reason`
- `artifact_completeness`
- `finalized_by`
- `finalized_at`

### runtime_evidence 建议至少记录
- CARLA 是否连通
- ROS graph 是否满足核心 topic / tf / clock
- 定位是否建立
- 规划是否有输出
- 控制是否有输出
- 是否到达目标
- 是否发生 collision / timeout / disengagement

---

## 建议 G：让 Codex 重点帮你做“工程收口”，不要帮你做“实时控制”

对这个项目最适合的 Codex 用法，不是“让它替你开仿真车”，而是：

- 读 repo、定位闭环缺口
- 生成和维护 runbook / checklist / digest
- 帮你补 `simctl`、report、manifest、schema、tests
- 帮你做失败归因、项目节奏整理、case 标准化

不建议让 Codex 承担：
- 实时驾驶控制
- 实时在线决策
- 未经约束的自动 execute
- 随意生成一次性脚本替代正式控制平面

---

## 3. 我建议你接下来优先做的 8 个 Codex 任务

1. **STABLE-001**：为 `simctl` 增加 finalize / collect 阶段  
2. **STABLE-002**：把 host readiness 和软件版本基线写进运行工件  
3. **STABLE-003**：补 external scenario 的 slot 生命周期和异常回收  
4. **ASSET-001**：把资产检查从“文件存在”提升到“语义可执行”  
5. **SCENARIO-001**：把 `site_gy_qyhx_gsh20260310` 晋升成首个稳定可复用公开道路 case  
6. **REPORT-001**：把 stable acceptance 与 shadow comparison 分离报告  
7. **RESEARCH-001**：为 shadow 研究线定比较指标口径  
8. **PMO-001**：让 digest 和 run gate 使用同一套状态语义

---

## 4. 这次生成的 Codex 导入包包含什么

本包分成两层：

### 第一层：沿用仓库当前习惯的 overlay
- `AGENTS.override.md`
- `codex_import_manifest.json`
- `docs/CODEX_PROJECT_SNAPSHOT_CN.md`
- `docs/CODEX_TASK_ROUTING_CN.md`
- `docs/PROJECT_PLAN_CODEX_READY_CN.md`
- `docs/CODEX_IMPORT_README_CN.md`

### 第二层：更接近 Codex 原生项目配置
- `.codex/config.toml`
- `.codex/agents/*.toml`
- `tasks/codex_backlog.json`

第一层适合你当前仓库快速落地；  
第二层适合把“自定义 subagent 约定”进一步迁移到 Codex 原生的项目级 agent 方式。

---

## 5. 推荐使用方式

### 最稳妥方式
直接把本包内容拷到你 repo 根目录，优先保留：
- `AGENTS.override.md`
- `docs/*`
- `tasks/codex_backlog.json`

然后再按需合并：
- `.codex/config.toml`
- `.codex/agents/*.toml`

### 推荐第一轮 prompt
```text
Read README.md, AGENTS.md, AGENTS.override.md, docs/CODEX_PROJECT_SNAPSHOT_CN.md, docs/CODEX_TASK_ROUTING_CN.md, and tasks/codex_backlog.json.
Tell me the top 3 engineering blockers to turn launch_submitted into a final closed-loop passed/failed run.
```

### 第二轮 prompt
```text
Focus on STABLE-001 and STABLE-002.
Propose the smallest safe code changes in src/simctl/, evaluation/, and infra/ubuntu/ to add finalize/evidence/host-bom support without breaking the current stable stack.
```

---

## 6. 我对你这个仿真系统的一句话判断

**这个项目已经不是“缺框架”，而是“差最后一公里的真实运行闭环收口”。**  
所以最值得投入的不是继续铺更大故事，而是把：
- host 基线
- real execute
- finalize/evidence
- public-road reusable case
- stable vs shadow 报表分流

这五件事真正闭起来。
