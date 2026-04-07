# BEVFusion 基线与 Shadow E2E 研究计划

{{YANG_MENTION}} {{COORDINATOR_MENTION}}

这条 issue 用来收口 `BEVFusion` 基线、`UniAD-style / VADv2` shadow 路线，以及它们和 stable 主线之间的接口关系。

## 目标

- 保持 `BEVFusion` 作为当前感知基线
- 把 shadow 路线先做成“旁路观测”，而不是直接 takeover
- 形成可比较的输入、输出、指标和结论模板

## 本周优先输出

- `BEVFusion` 当前接入边界
- shadow planner 输入输出契约草案
- 对照指标清单
- 首批研究场景建议

## 必看内容

- `README.md`
- `docs/ALGORITHM_RESEARCH_ROADMAP_CN.md`
- `docs/FUTURE_EXECUTION_ROADMAP_CN.md`
- `docs/PAPER_READING_MAP_CN.md`
- `docs/PAPER_LANDSCAPE_CN.md`
- `docs/TEAM_AGENT_USAGE_CN.md`
- `docs/SUBAGENT_CATALOG.md`

## 推荐子agent

- `BEVFusion` / `UniAD-style` / `VADv2` / shadow 路线：`public_road_e2e_shadow_explorer`
- 多研究线比较与对照设计：`algorithm_research_explorer`

## 建议动作

- 先定义评估口径，再做实现细节扩张
- 所有研究结论都要能回指到具体场景和 KPI
- 不要让研究线破坏 stable 主线 bring-up 和闭环验收

## 建议回报格式

```text
本周研究结论：
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

