# BEVFusion 基线与 Shadow E2E 研究计划

{{YANG_MENTION}} {{COORDINATOR_MENTION}}

这条 issue 用来收口 `BEVFusion` 基线、`UniAD-style / VADv2` shadow 路线，以及它们和 stable 主线之间的接口关系。

## Owner 边界

- `{{YANG_MENTION}}`：`BEVFusion` 基线、shadow planner 接口、指标口径
- `{{COORDINATOR_MENTION}}`：研究线与主线执行口径对齐，避免研究链漂离可验证主线

## 目标

- 保持 `BEVFusion` 作为当前感知基线
- 把 shadow 路线先做成“旁路观测”，而不是直接 takeover
- 形成可比较的输入、输出、指标和结论模板

## 本周优先输出

- `BEVFusion` 当前接入边界
- shadow planner 输入输出契约草案
- 对照指标清单和口径说明
- 首批研究场景建议

## 必看内容

- `README.md`
- `docs/ALGORITHM_RESEARCH_ROADMAP_CN.md`
- `docs/FUTURE_EXECUTION_ROADMAP_CN.md`
- `docs/PAPER_READING_MAP_CN.md`
- `docs/PAPER_LANDSCAPE_CN.md`
- `docs/TEAM_AGENT_USAGE_CN.md`
- `docs/SUBAGENT_CATALOG.md`

## 建议阅读顺序

1. `README.md`
2. `docs/ALGORITHM_RESEARCH_ROADMAP_CN.md`
3. `docs/PAPER_READING_MAP_CN.md`
4. `docs/PAPER_LANDSCAPE_CN.md`
5. `docs/TEAM_AGENT_USAGE_CN.md`
6. `docs/SUBAGENT_CATALOG.md`

## 推荐子agent

- `BEVFusion` / `UniAD-style` / `VADv2` / shadow 路线：`public_road_e2e_shadow_explorer`
- 多研究线比较与对照设计：`algorithm_research_explorer`

## 推荐起手方式

1. 先冻结 `BEVFusion` 当前输出边界，不要一开始就扩模型
2. 先写 shadow planner 接口草案，明确输入张量、语义字段、时间同步和输出形式
3. 先统一指标口径，再推进具体实验
4. 所有结论都回到具体场景、具体 profile、具体 gate

## 指标口径至少覆盖

- 感知输出稳定性
- planner 旁路输出可比性
- 关键场景通过率
- 延迟、频率和资源占用
- 结论是否能回指到具体场景和日志

## 建议动作

- 先定义评估口径，再做实现细节扩张
- 所有研究结论都要能回指到具体场景和 KPI
- 不要让研究线破坏 stable 主线 bring-up 和闭环验收

## 建议回报格式

```text
本周研究结论：
- ...

接口草案变化：
- ...

指标口径变化：
- ...

当前假设：
- ...

当前 blocker：
- ...

下一步实验：
- ...
```

## 验收

- `BEVFusion` 基线位置明确
- shadow 路线是旁路比较而不是直接替换主链
- 对照指标、场景和输出格式都有书面记录
- 接口草案和指标口径能支持后续实现，不再只停留在论文口头描述
