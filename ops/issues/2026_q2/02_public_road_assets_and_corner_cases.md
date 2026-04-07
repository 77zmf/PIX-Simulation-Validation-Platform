# 公开道路资产、corner case 与重建输入收口

{{LSX_MENTION}} {{COORDINATOR_MENTION}}

这条 issue 面向公开道路资产主线，目标是把 `site_gy_qyhx_gsh20260302` 及后续复用输入收口成可持续复用的资产束和场景入口。

## 目标

- 把公开道路地图、点云、元数据整理成统一资产束
- 把 corner case 整理成可回放、可索引、可复现实例
- 为后续 `map refresh / static Gaussian / dynamic Gaussian` 研究保留干净输入

## 本周优先输出

- 资产束结构定义
- 已有公开道路输入清单
- 缺失项清单
- corner case 索引
- 至少一条可被 stable 栈复用的场景模板

## 必看内容

- `README.md`
- `docs/PROJECT_OPERATING_TEAM_CN.md`
- `docs/FUTURE_EXECUTION_ROADMAP_CN.md`
- `docs/PAPER_READING_MAP_CN.md`
- `docs/LOCAL_PDF_INDEX_CN.md`
- `assets/manifests/`
- `scenarios/`

## 推荐子agent

- 资产结构、重建输入、Gaussian 路线：`gaussian_reconstruction_explorer`
- replay / runtime 复现链路：`execution_runtime_explorer`

## 建议动作

- 先盘点当前资产和缺口，不要先做格式重写
- 优先保留能支撑 stable 栈和 replay 的最小输入
- 对每个 corner case 写清：
  - 来源
  - 现象
  - 是否能复现
  - 需要哪些原始输入
  - 成功信号

## 建议回报格式

```text
资产新增：
- ...

corner case 新增：
- ...

当前缺口：
- ...

需要主线配合：
- ...
```

## 验收

- 资产束结构统一
- corner case 有索引而不是散落在聊天记录里
- 至少一条公开道路输入能回指到 stable 栈场景或 replay 模板

