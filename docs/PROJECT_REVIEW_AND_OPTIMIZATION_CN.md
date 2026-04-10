# 项目复盘与优化建议

## 当前状态

仓库当前已经具备这些基础能力：

- `simctl` 控制平面
- GitHub Project 执行看板
- digest 自动汇总
- stable 栈启动与运行骨架
- 公共道路资产与研究场景骨架

真正决定季度交付的关键仍然是：

- 公司 Ubuntu 主机是否完成环境搭建
- `CARLA 0.9.15 + Autoware` 是否形成第一条真实闭环
- `run_result -> report -> replay` 是否稳定产出

## 当前主要缺口

1. 真实闭环还没有在目标主机上完成正式验收
2. 公共道路资产已经有骨架，但还缺首个可复用回归输入
3. 研究线必须继续保留，但统一挂在 `CARLA 0.9.15 / UE4.26` 主运行线上
4. 项目管理已经切到 GitHub-only，后续重点是保证看板字段质量，而不是再维护多套系统

## 优先级建议

### P0

- Ubuntu 主机访问、权限与依赖准备
- ROS 2 / colcon / rosdep / vcs
- CARLA 0.9.15 / Town01 / recorder
- Autoware 工作区、依赖解析、首次编译
- 第一条 `run_result.json`

### P1

- `site proxy` 资产束
- Top 5 corner case
- E2E shadow 对比指标
- 研究场景回放与报告模板

### P2

- 更复杂的公共道路重建链路
- 更大规模的研究场景矩阵
- 更细的 GitHub digest 聚合和失败分类

## 优化建议

- 不再保留外部文档同步和邮件提醒接口，统一用 GitHub Project + digest issue 管理
- 所有研究任务统一落到 `stable` 主栈，不新增独立研究运行栈
- digest 只围绕季度硬门槛输出：环境、闭环、数据闭环、资产束、场景回归
- 优先提升 GitHub Project 字段完整度，而不是增加更多管理工具
