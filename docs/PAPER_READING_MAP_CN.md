# 论文阅读地图

## 目标

这份文档把当前仓库相关论文按项目主线做统一整理，方便团队和子 agent 沿同一套研究口径推进。

- 对应协同 issue：[#22 论文整理：公开道路感知、Shadow E2E 与三维重建阅读清单](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/22)
- 完整领域总览：[PAPER_LANDSCAPE_CN.md](./PAPER_LANDSCAPE_CN.md)
- 当前项目主线：
  - `BEVFusion` 感知基线
  - 公开道路 `Shadow E2E / planner`
  - 三维重建与高保真场景资产
  - 中长期候选路线观察

## A. 当前主线必读

| 方向 | 论文 | 入口 | 为什么现在读 |
| --- | --- | --- | --- |
| 感知基线 | BEVFusion | [arXiv 2205.13542](https://arxiv.org/abs/2205.13542) | 当前公开道路感知基线，后续 planner 和 E2E 都围绕统一 BEV 表征展开。 |
| 规划一体化 | UniAD | [arXiv 2212.10156](https://arxiv.org/abs/2212.10156) | 规划导向的一体化代表路线，用来定义公开道路任务视角。 |
| Shadow planner 对照 | VAD | [arXiv 2303.12077](https://arxiv.org/abs/2303.12077) | 作为向量化场景表征和 Shadow planner 的对照基线。 |
| 不确定性建模 | VADv2 | [arXiv 2402.13243](https://arxiv.org/abs/2402.13243) | 更适合公开道路的概率规划，可作为重点对照。 |
| 指标校准 | BEV-Planner | [arXiv 2312.03031](https://arxiv.org/abs/2312.03031) | 用来判断 open-loop 指标与真实 closed-loop 表现之间的落差。 |
| Gaussian 基础 | 3D Gaussian Splatting | [arXiv 2308.04079](https://arxiv.org/abs/2308.04079) | 统一 3DGS 基础概念和术语。 |
| 静态几何 | 2D Gaussian Splatting | [arXiv 2403.17888](https://arxiv.org/abs/2403.17888) | 更强调几何精度，适合静态道路资产和地图刷新。 |
| 动态重建 | DrivingGaussian | [arXiv 2312.07920](https://arxiv.org/abs/2312.07920) | 面向自动驾驶动态场景的 Gaussian 路线。 |
| 城市场景重建 | Street Gaussians | [arXiv 2401.01339](https://arxiv.org/abs/2401.01339) | 公开道路动态重建对照基线。 |

## B. 下一阶段重点阅读

| 方向 | 论文 | 入口 | 关注点 |
| --- | --- | --- | --- |
| 蒸馏式 planner | Hydra-MDP | [arXiv 2406.06978](https://arxiv.org/abs/2406.06978) | 如何从现有 expert / rule planner 蒸馏到 learned planner。 |
| 闭环增强 | Hydra-NeXt | [arXiv 2503.12030](https://arxiv.org/abs/2503.12030) | 如何缩小 open-loop 到 closed-loop 的稳定性差距。 |
| 稳定性 | MomAD | [arXiv 2503.03125](https://arxiv.org/abs/2503.03125) | 遮挡、盲弯和轨迹抖动场景下的稳定性处理。 |
| 大规模静态重建 | CityGaussianV2 | [arXiv 2411.00771](https://arxiv.org/abs/2411.00771) | 是否适合道路资产刷新和地图更新。 |
| LiDAR 监督 | LiHi-GS | [arXiv 2412.15447](https://arxiv.org/abs/2412.15447) | 是否更贴近车端数据形态和定位需求。 |
| Static/Dynamic 分解 | DeSiRe-GS | [arXiv 2411.11921](https://arxiv.org/abs/2411.11921) | 是否适合公开道路静态/动态分解重建。 |
| 高保真闭环 | HUGSIM | [arXiv 2412.01718](https://arxiv.org/abs/2412.01718) | reconstruction 如何服务闭环 simulator。 |

## C. 观察名单

| 论文 | 入口 | 当前判断 |
| --- | --- | --- |
| SparseDrive | [arXiv 2405.19620](https://arxiv.org/abs/2405.19620) | 与当前 `BEVFusion` 主线差异较大，先观察。 |
| GenAD | [arXiv 2402.11502](https://arxiv.org/abs/2402.11502) | 生成式 planner 候选，但当前优先级不高。 |
| 4D Gaussian Splatting | [arXiv 2310.08528](https://arxiv.org/abs/2310.08528) | 通用动态 Gaussian 基线，先作为对照，不直接做主线。 |

## D. 按成员分配的优先阅读顺序

### 杨志朋

1. BEVFusion
2. UniAD
3. VAD
4. VADv2
5. Hydra-MDP
6. Hydra-NeXt
7. MomAD

### 罗顺雄 / lsx

1. 2D Gaussian Splatting
2. DrivingGaussian
3. Street Gaussians
4. CityGaussianV2
5. LiHi-GS
6. DeSiRe-GS
7. HUGSIM

### 朱民峰

1. BEV-Planner
2. UniAD
3. VADv2
4. Hydra-NeXt
5. HUGSIM

## E. 阅读输出格式

每篇论文统一回答 3 个问题：

1. 它解决了什么问题？
2. 它会影响项目中的哪条主线？
3. 它为什么应该现在做，或者为什么暂时不做？

建议先把阅读摘要跟帖到 issue `#22`，后续再汇总进正式设计文档或实验计划。

## F. 仓库内本地 PDF

仓库里已经收纳的 PDF 见 [LOCAL_PDF_INDEX_CN.md](./LOCAL_PDF_INDEX_CN.md)。
