# 杨志朋 Shadow E2E 阅读纪要

对应 issue：

- [#7 论文整理：公开道路感知、Shadow E2E 与三维重建阅读清单](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/7)
- [#10 BEVFusion 基线与 Shadow E2E 研究计划](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/10)
- [#5 P1 感知与 Shadow E2E：BEVFusion 接口与指标口径](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/5)

本文档只覆盖当前由杨志朋主责的研究线：

- `BEVFusion` 感知基线
- `UniAD-style / VAD / VADv2` shadow planner 对照
- `Hydra-MDP / Hydra-NeXt / MomAD` 作为中期观察与储备路线

统一回答 issue #7 要求的 3 个问题：

1. 它解决了什么问题？
2. 它会影响项目中的哪条主线？
3. 它为什么应该现在做，或者为什么暂时不做？

## 当前结论

- 立刻落地的主线仍然是 `BEVFusion -> UniAD-style shadow / VADv2 shadow`。
- `VAD` 更适合作为结构化 scene token 和对照基线，而不是替代当前的 `BEVFusion` 感知主线。
- `Hydra-MDP / Hydra-NeXt / MomAD` 值得持续跟踪，但不应在公司 Ubuntu 主机真实 `--execute` 路径跑通之前扩成当前季度主线任务。

## 1. BEVFusion

论文入口：

- [BEVFusion: Multi-Task Multi-Sensor Fusion with Unified Bird's-Eye View Representation](https://arxiv.org/abs/2205.13542)

- 它解决了什么问题？
  - 解决多传感器感知结果分散、BEV 表征不统一的问题，把检测、跟踪、占据等任务收口到统一 BEV 空间。
- 它会影响项目中的哪条主线？
  - 直接影响公开道路感知主线，也决定 `shadow planner` 的输入边界是否稳定。
- 它为什么应该现在做，或者为什么暂时不做？
  - 应该现在做，因为仓库当前已经把 `BEVFusion` 设为公开道路感知基线，后续 `UniAD-style / VADv2` 的 shadow 输入都依赖它。

当前仓库落点：

- `adapters/profiles/perception_bevfusion_public_road.yaml`
- `evaluation/kpi_gates/perception_bevfusion_public_road_gate.yaml`
- `scenarios/l2/perception_bevfusion_public_road_occlusion.yaml`

## 2. UniAD

论文入口：

- [UniAD: Planning-Oriented Autonomous Driving](https://arxiv.org/abs/2212.10156)

- 它解决了什么问题？
  - 解决感知、预测、规划之间割裂的问题，用规划导向视角组织多任务自动驾驶流水线。
- 它会影响项目中的哪条主线？
  - 直接影响当前 `shadow E2E` 主参考路线，帮助定义我们需要的 planner 输入字段和轨迹输出形式。
- 它为什么应该现在做，或者为什么暂时不做？
  - 应该现在做，但只做 `trajectory-level shadow`。它适合当成主参考路线，不适合在本季度直接 takeover 正式控制链。

当前仓库落点：

- `adapters/profiles/e2e_bevfusion_uniad_shadow.yaml`
- `evaluation/kpi_gates/e2e_bevfusion_uniad_shadow_gate.yaml`
- `scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml`

## 3. VAD

论文入口：

- [VAD: Vectorized Scene Representation for Efficient Autonomous Driving](https://arxiv.org/abs/2303.12077)

- 它解决了什么问题？
  - 解决 planning 输入过于稠密、交互信息不够结构化的问题，用向量化 scene 表征来组织 agent、道路和交互关系。
- 它会影响项目中的哪条主线？
  - 影响 `shadow planner` 的对照线设计，尤其是我们如何定义 `scene token / interaction` 这一层接口。
- 它为什么应该现在做，或者为什么暂时不做？
  - 应该现在做对照理解，但不应替换当前 `BEVFusion` 感知主线。它更适合指导我们怎样做结构化中间层，而不是直接改主线感知。

当前仓库落点：

- `docs/PAPER_READING_MAP_CN.md`
- `docs/PAPER_LANDSCAPE_CN.md`
- `docs/ALGORITHM_RESEARCH_ROADMAP_CN.md`

## 4. VADv2

论文入口：

- [VADv2: End-to-End Vectorized Autonomous Driving via Probabilistic Planning](https://arxiv.org/abs/2402.13243)

- 它解决了什么问题？
  - 解决公开道路规划中不确定性表达不足的问题，把概率规划和风险覆盖纳入统一 planner 输出。
- 它会影响项目中的哪条主线？
  - 直接影响 `VADv2 shadow` 对照线，尤其影响 `shadow_uncertainty_coverage` 这类指标设计。
- 它为什么应该现在做，或者为什么暂时不做？
  - 应该现在做，因为遮挡、cut-in、行人突然出现这些公开道路场景都需要更明确的不确定性口径。

当前仓库落点：

- `adapters/profiles/e2e_bevfusion_vadv2_shadow.yaml`
- `evaluation/kpi_gates/e2e_bevfusion_vadv2_shadow_gate.yaml`
- `scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml`

## 5. Hydra-MDP

论文入口：

- [Hydra-MDP: End-to-end Multimodal Planning with Multi-target Hydra-Distillation](https://arxiv.org/abs/2406.06978)

- 它解决了什么问题？
  - 解决 learned planner 直接训练不稳定、单一 teacher 信号不足的问题，通过多目标蒸馏把 expert planner 的优势迁移到端到端 planner。
- 它会影响项目中的哪条主线？
  - 影响中期 `shadow planner` 升级路线，特别是“如何从现有 classical planner 过渡到 learned planner”这一层方法论。
- 它为什么应该现在做，或者为什么暂时不做？
  - 现在更适合列入观察名单，不适合立刻落主线。原因是仓库还没有稳定的 expert rollout 数据闭环，也还没在 Ubuntu 主机上稳定回填真实 `--execute` 结果。

建议关注点：

- 是否需要多 teacher 信号而不是单 teacher imitation
- 是否能复用现有 `stable` 主线 planner 结果做 distillation teacher

## 6. Hydra-NeXt

论文入口：

- [Hydra-NeXt: Robust Closed-Loop Driving with Open-Loop Training](https://arxiv.org/abs/2503.12030)

- 它解决了什么问题？
  - 解决 open-loop 训练和 closed-loop 真实表现之间的差距，重点提升闭环鲁棒性和恢复能力。
- 它会影响项目中的哪条主线？
  - 影响中期 closed-loop shadow 研究线，也会影响我们未来怎样判断 open-loop 指标是否足够代表真实闭环质量。
- 它为什么应该现在做，或者为什么暂时不做？
  - 暂时不做主线实现，但应该保持高优先级观察。只有在公司 Ubuntu 主机的真实闭环链路跑稳之后，Hydra-NeXt 才有实际落地价值。

建议关注点：

- 如何设计从 open-loop 到 closed-loop 的 bridge
- 如何把恢复能力、偏航修正和长时稳定性纳入 KPI

## 7. MomAD

论文入口：

- [Don't Shake the Wheel: Momentum-Aware Planning in End-to-End Autonomous Driving](https://arxiv.org/abs/2503.03125)

- 它解决了什么问题？
  - 解决端到端 planner 在遮挡、盲弯和复杂交互下轨迹抖动、控制不稳定的问题，把运动连续性和历史动量纳入规划过程。
- 它会影响项目中的哪条主线？
  - 影响中期 planner 平滑性和稳定性优化，尤其会作用到我们现在已经在用的 `trajectory_divergence_m`、`comfort_cost` 等指标。
- 它为什么应该现在做，或者为什么暂时不做？
  - 暂时不做当前季度主线实现，但值得作为后续“减少 shadow 轨迹抖动”的重点观察路线。它更像是第二阶段优化，而不是第一阶段接口冻结任务。

建议关注点：

- 轨迹抖动是否可以拆成独立 KPI
- 历史动量信息能否复用我们当前 `ego_history` 契约

## 8. 面向当前仓库的执行顺序

建议顺序：

1. 先稳住 `BEVFusion` 感知输出契约和 `planner_interface_disagreement_rate`
2. 再做 `UniAD-style shadow` 的真实 `--execute` 回填
3. 再做 `VADv2 shadow` 的不确定性对照
4. 最后再评估 `Hydra-MDP / Hydra-NeXt / MomAD` 是否进入下一阶段研究计划

## 9. 当前不建议扩大的范围

- 不建议在当前季度把 `Hydra-MDP / Hydra-NeXt / MomAD` 直接扩成新的实现分支
- 不建议在稳定闭环未跑通前引入新的感知主线替代 `BEVFusion`
- 不建议把论文阅读输出停留在纯论文摘要，必须回指到仓库里的 profile、scenario、KPI gate

## 10. 下一步可执行动作

仓库内：

- 保持 `BEVFusion -> shadow planner` 契约文档和 KPI 口径一致
- 继续把 `#5 / #10` 的 blocker 和研究结论回贴到同一条线的 issue

公司 Ubuntu 主机：

- `simctl run --scenario scenarios/l2/perception_bevfusion_public_road_occlusion.yaml --run-root runs --execute`
- `simctl run --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml --run-root runs --slot stable-slot-01 --execute`
- `simctl run --scenario scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml --run-root runs --slot stable-slot-02 --execute`

完成这三条真实运行后，再判断是否需要把 `Hydra-MDP / Hydra-NeXt / MomAD` 提前拉入实现队列。
