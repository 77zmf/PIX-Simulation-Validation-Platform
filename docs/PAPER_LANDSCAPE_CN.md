# 自动驾驶论文全景图

## 目标

这份文档用于把当前项目相关论文按领域完整归档，作为仓库侧的统一研究入口。

- 精读入口：[PAPER_READING_MAP_CN.md](./PAPER_READING_MAP_CN.md)
- 本地 PDF 索引：[LOCAL_PDF_INDEX_CN.md](./LOCAL_PDF_INDEX_CN.md)
- 协同讨论入口：[issue #22](https://github.com/pixmoving-moveit/zmf_ws/issues/22)

当前文档不追求“收尽所有论文”，而是优先覆盖当前项目真正相关的主线：

1. 数据集与评测
2. 感知与多传感器 BEV
3. 预测、占用与世界模型
4. 规划控制与端到端驾驶
5. 在线地图构建
6. 三维重建与 Gaussian 路线
7. 仿真、场景与安全评测

## A. 数据集与评测基线

| 方向 | 论文 | 链接 | 作用 |
| --- | --- | --- | --- |
| 多模态感知数据集 | nuScenes: A multimodal dataset for autonomous driving | [arXiv 1903.11027](https://arxiv.org/abs/1903.11027) | 多传感器感知、检测、跟踪和占用预测的常用基线。 |
| 大规模感知数据集 | Scalability in Perception for Autonomous Driving: Waymo Open Dataset | [arXiv 1912.04838](https://arxiv.org/abs/1912.04838) | 感知和 tracking 的高质量公开道路数据基线。 |
| 运动预测数据集 | Large Scale Interactive Motion Forecasting for Autonomous Driving: The Waymo Open Motion Dataset | [arXiv 2104.10133](https://arxiv.org/abs/2104.10133) | 交互式 motion forecasting 和 joint prediction 的主流基线。 |
| 感知与预测数据集 | Argoverse 2: Next Generation Datasets for Self-Driving Perception and Forecasting | [arXiv 2301.00493](https://arxiv.org/abs/2301.00493) | 兼顾 perception、forecasting 和 map 的公开道路数据集。 |
| 闭环规划基准 | nuPlan: A closed-loop ML-based planning benchmark for autonomous vehicles | [arXiv 2106.11810](https://arxiv.org/abs/2106.11810) | 规划和闭环评测基线，适合校准 open-loop 与 closed-loop 差异。 |
| 闭环 E2E 基准 | Bench2Drive: Towards Multi-Ability Benchmarking of Closed-Loop End-To-End Autonomous Driving | [arXiv 2406.03877](https://arxiv.org/abs/2406.03877) | 更贴近端到端公开道路能力评测。 |
| 非反应式评测 | NAVSIM: Data-Driven Non-Reactive Autonomous Vehicle Simulation and Benchmarking | [arXiv 2406.15349](https://arxiv.org/abs/2406.15349) | 在真实数据和闭环评测之间提供更便宜的中间层。 |

## B. 感知与多传感器 BEV

| 方向 | 论文 | 链接 | 当前贴合度 |
| --- | --- | --- | --- |
| 综述 | Vision-Centric BEV Perception: A Survey | [arXiv 2208.02797](https://arxiv.org/abs/2208.02797) | 高，适合统一术语和路线图。 |
| 图像 lifting 基线 | Lift, Splat, Shoot: Encoding Images From Arbitrary Camera Rigs by Implicitly Unprojecting to 3D | [arXiv 2008.05711](https://arxiv.org/abs/2008.05711) | 中，理解 camera-only BEV 发展脉络。 |
| 多相机检测 | BEVDet: High-Performance Multi-Camera 3D Object Detection in Bird-Eye-View | [arXiv 2112.11790](https://arxiv.org/abs/2112.11790) | 中，适合补感知路线背景。 |
| 时空 BEV | BEVFormer: Learning Bird's-Eye-View Representation from Multi-Camera Images via Spatiotemporal Transformers | [arXiv 2203.17270](https://arxiv.org/abs/2203.17270) | 中高，适合理解时序 BEV。 |
| 多传感器统一 BEV | BEVFusion: Multi-Task Multi-Sensor Fusion with Unified Bird's-Eye View Representation | [arXiv 2205.13542](https://arxiv.org/abs/2205.13542) | 很高，当前项目感知主线。 |
| 对象中心时序建模 | StreamPETR: Exploring Object-Centric Temporal Modeling for Multi-View 3D Object Detection | [arXiv 2303.11926](https://arxiv.org/abs/2303.11926) | 中，可作多相机时序增强参考。 |
| 稀疏时空融合 | Sparse4D: Multi-View 3D Object Detection with Sparse Spatial-Temporal Fusion | [arXiv 2211.10581](https://arxiv.org/abs/2211.10581) | 中，适合作为高效多视角时序基线。 |

## C. 预测、占用与世界模型

| 方向 | 论文 | 链接 | 当前贴合度 |
| --- | --- | --- | --- |
| 多相机占用 | SurroundOcc: Multi-Camera 3D Occupancy Prediction for Autonomous Driving | [arXiv 2303.09551](https://arxiv.org/abs/2303.09551) | 中高，适合 BEV 后续占用建模。 |
| 视觉占用 | OccFormer: Dual-path Transformer for Vision-based 3D Semantic Occupancy Prediction | [arXiv 2304.05316](https://arxiv.org/abs/2304.05316) | 中高，适合理解 occupancy 表征。 |
| 交互预测 | M2I: From Factored Marginal Trajectory Prediction to Interactive Prediction | [arXiv 2202.11884](https://arxiv.org/abs/2202.11884) | 中，适合作为交互预测补课。 |
| 多 agent 统一预测 | Scene Transformer: A Unified Architecture for Predicting Multiple Agent Trajectories | [arXiv 2106.08417](https://arxiv.org/abs/2106.08417) | 中，理解 agent interaction 建模。 |
| 简洁预测基线 | Wayformer: Motion Forecasting via Simple & Efficient Attention Networks | [arXiv 2207.05844](https://arxiv.org/abs/2207.05844) | 中，适合作为 motion 预测轻量基线。 |
| 世界模型 | DriveDreamer: Towards Real-world-driven World Models for Autonomous Driving | [arXiv 2309.09777](https://arxiv.org/abs/2309.09777) | 中，适合中长期数据闭环和生成式世界模型。 |
| 世界模型增强 | DriveDreamer-2: LLM-Enhanced World Models for Diverse Driving Video Generation | [arXiv 2403.06845](https://arxiv.org/abs/2403.06845) | 中，适合作为场景生成和 rare-case 合成观察对象。 |
| 生成式自治世界模型 | GAIA-1: A Generative World Model for Autonomous Driving | [arXiv 2309.17080](https://arxiv.org/abs/2309.17080) | 中，适合关注大模型化路线。 |
| 占用世界模型 | Driving in the Occupancy World: Vision-Centric 4D Occupancy Forecasting and Planning via World Models for Autonomous Driving | [arXiv 2408.14197](https://arxiv.org/abs/2408.14197) | 中高，适合把占用预测和 planning 接起来。 |
| 交互式真实模拟器 | Learning Interactive Real-World Simulators | [arXiv 2310.06114](https://arxiv.org/abs/2310.06114) | 中，适合中长期仿真和 policy training 观察。 |

## D. 规划控制与端到端驾驶

| 方向 | 论文 | 链接 | 当前贴合度 |
| --- | --- | --- | --- |
| 早期多模态 E2E | TransFuser: Imitation with Transformer-Based Sensor Fusion for Autonomous Driving | [arXiv 2205.15997](https://arxiv.org/abs/2205.15997) | 中高，适合理解 CARLA 路线和多模态 E2E 起点。 |
| 可解释安全 E2E | Safety-Enhanced Autonomous Driving Using Interpretable Sensor Fusion Transformer | [PMLR 205](https://proceedings.mlr.press/v205/shao23a.html) | 中高，适合理解安全与解释性。 |
| 控制预测 | Trajectory-guided Control Prediction for End-to-end Autonomous Driving: A Simple yet Strong Baseline | [arXiv 2206.08129](https://arxiv.org/abs/2206.08129) | 中，适合理解 trajectory-to-control 路线。 |
| 解码器增强 | Think Twice Before Driving: Towards Scalable Decoders for End-to-End Autonomous Driving | [CVPR 2023](https://openaccess.thecvf.com/content/CVPR2023/html/Jia_Think_Twice_Before_Driving_Towards_Scalable_Decoders_for_End-to-End_Autonomous_CVPR_2023_paper.html) | 中高，适合作为稳定性改进参考。 |
| Teacher-Student 解耦 | DriveAdapter: Breaking the Coupling Barrier of Perception and Planning in End-to-End Autonomous Driving | [arXiv 2308.00398](https://arxiv.org/abs/2308.00398) | 中高，适合理解 perception/planning 解耦。 |
| 规划导向一体化 | UniAD: Planning-Oriented Autonomous Driving | [arXiv 2212.10156](https://arxiv.org/abs/2212.10156) | 很高，当前公开道路 E2E 主参考。 |
| 向量化场景 | VAD: Vectorized Scene Representation for Efficient Autonomous Driving | [arXiv 2303.12077](https://arxiv.org/abs/2303.12077) | 很高，Shadow planner 关键对照。 |
| 概率规划 | VADv2: End-to-End Vectorized Autonomous Driving via Probabilistic Planning | [arXiv 2402.13243](https://arxiv.org/abs/2402.13243) | 很高，公开道路不确定性重点路线。 |
| open-loop/closed-loop 校准 | Is Ego Status All You Need for Open-Loop End-to-End Autonomous Driving? | [arXiv 2312.03031](https://arxiv.org/abs/2312.03031) | 高，适合校准评测口径。 |
| 多目标蒸馏 | Hydra-MDP: End-to-end Multimodal Planning with Multi-target Hydra-Distillation | [arXiv 2406.06978](https://arxiv.org/abs/2406.06978) | 高，适合从现有 expert planner 过渡。 |
| 闭环鲁棒性 | Hydra-NeXt: Robust Closed-Loop Driving with Open-Loop Training | [arXiv 2503.12030](https://arxiv.org/abs/2503.12030) | 高，适合后续提升 closed-loop 表现。 |
| 轨迹稳定性 | Don't Shake the Wheel: Momentum-Aware Planning in End-to-End Autonomous Driving | [arXiv 2503.03125](https://arxiv.org/abs/2503.03125) | 高，适合盲弯和遮挡场景。 |
| 生成式 planner | GenAD: Generative End-to-End Autonomous Driving | [arXiv 2402.11502](https://arxiv.org/abs/2402.11502) | 中，暂时观察。 |
| 稀疏场景路线 | SparseDrive: End-to-End Autonomous Driving via Sparse Scene Representation | [arXiv 2405.19620](https://arxiv.org/abs/2405.19620) | 中，和当前 BEVFusion 主线差异较大。 |

## E. 在线地图构建与结构化道路先验

| 方向 | 论文 | 链接 | 当前贴合度 |
| --- | --- | --- | --- |
| 地图学习入门 | HDMapNet: An Online HD Map Construction and Evaluation Framework | [arXiv 2107.06307](https://arxiv.org/abs/2107.06307) | 中高，适合理解 map learning 问题定义。 |
| 向量化地图 | VectorMapNet: End-to-end Vectorized HD Map Learning | [arXiv 2206.08920](https://arxiv.org/abs/2206.08920) | 中高，适合结构化道路资产。 |
| 在线地图构建 | MapTR: Structured Modeling and Learning for Online Vectorized HD Map Construction | [arXiv 2208.14437](https://arxiv.org/abs/2208.14437) | 高，适合和公开道路 lane/map 资产对齐。 |
| 地图构建增强 | MapTRv2: An End-to-End Framework for Online Vectorized HD Map Construction | [arXiv 2308.05736](https://arxiv.org/abs/2308.05736) | 高，适合作为后续升级参考。 |

## F. 三维重建与 Gaussian 路线

| 方向 | 论文 | 链接 | 当前贴合度 |
| --- | --- | --- | --- |
| 基础 3DGS | 3D Gaussian Splatting for Real-Time Radiance Field Rendering | [arXiv 2308.04079](https://arxiv.org/abs/2308.04079) | 高，统一基础术语。 |
| 几何精度 | 2D Gaussian Splatting for Geometrically Accurate Radiance Fields | [arXiv 2403.17888](https://arxiv.org/abs/2403.17888) | 很高，适合静态道路几何资产。 |
| 通用动态 GS | 4D Gaussian Splatting for Real-Time Dynamic Scene Rendering | [arXiv 2310.08528](https://arxiv.org/abs/2310.08528) | 中，作为通用动态基线。 |
| 动态驾驶场景 | DrivingGaussian: Composite Gaussian Splatting for Surrounding Dynamic Autonomous Driving Scenes | [arXiv 2312.07920](https://arxiv.org/abs/2312.07920) | 高，公开道路动态 actor 重建参考。 |
| 城市场景 | Street Gaussians: Modeling Dynamic Urban Scenes with Gaussian Splatting | [arXiv 2401.01339](https://arxiv.org/abs/2401.01339) | 高，城市公开道路动态重建基线。 |
| 自监督街景 | S3Gaussian: Self-Supervised Street Gaussians for Autonomous Driving | [arXiv 2405.20323](https://arxiv.org/abs/2405.20323) | 高，仓库已收录本地 PDF。 |
| 大规模静态重建 | CityGaussianV2: Efficient and Geometrically Accurate Reconstruction for Large-Scale Scenes | [arXiv 2411.00771](https://arxiv.org/abs/2411.00771) | 很高，适合地图刷新和静态资产。 |
| LiDAR 监督 GS | LiHi-GS: LiDAR-Supervised Gaussian Splatting for Highway Driving Scene Reconstruction | [arXiv 2412.15447](https://arxiv.org/abs/2412.15447) | 很高，适合车载多传感器场景。 |
| static/dynamic 分解 | DeSiRe-GS: 4D Street Gaussians for Static-Dynamic Decomposition and Surface Reconstruction for Urban Driving Scenes | [arXiv 2411.11921](https://arxiv.org/abs/2411.11921) | 很高，适合公开道路静/动态分解。 |
| 统一 Gaussian primitive | Hierarchy UGP: Hierarchy Unified Gaussian Primitive for Large-Scale Dynamic Scene Reconstruction | [ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/html/Sun_Hierarchy_UGP_Hierarchy_Unified_Gaussian_Primitive_for_Large-Scale_Dynamic_Scene_ICCV_2025_paper.html) | 高，仓库已收录本地 PDF。 |
| reconstruction 到 simulator | HUGSIM: A Real-Time, Photo-Realistic and Closed-Loop Simulator for Autonomous Driving | [arXiv 2412.01718](https://arxiv.org/abs/2412.01718) | 很高，适合未来高保真闭环。 |

## G. 仿真、场景生成与安全评测

| 方向 | 论文 | 链接 | 当前贴合度 |
| --- | --- | --- | --- |
| 基础仿真平台 | CARLA: An Open Urban Driving Simulator | [arXiv 1711.03938](https://arxiv.org/abs/1711.03938) | 很高，当前验证平台基础。 |
| 场景描述语言 | Scenic: A Language for Scenario Specification and Scene Generation | [arXiv 1809.09310](https://arxiv.org/abs/1809.09310) | 中高，适合后续 formal scenario 描述。 |
| 组合式仿真 | MetaDrive: Composing Diverse Driving Scenarios for Generalizable Reinforcement Learning | [arXiv 2109.12674](https://arxiv.org/abs/2109.12674) | 中，适合强化学习和大规模场景生成观察。 |
| 数据驱动场景平台 | ScenarioNet: Open-Source Platform for Large-Scale Traffic Scenario Simulation and Modeling | [arXiv 2306.12241](https://arxiv.org/abs/2306.12241) | 高，适合数据闭环和场景仓库化。 |
| 安全评测平台 | SafeBench: A Benchmarking Platform for Safety Evaluation of Autonomous Vehicles | [arXiv 2206.09682](https://arxiv.org/abs/2206.09682) | 高，适合后续安全评测框架。 |
| 安全场景综述 | A Survey on Safety-Critical Driving Scenario Generation -- A Methodological Perspective | [arXiv 2202.02215](https://arxiv.org/abs/2202.02215) | 高，适合规划 scenario generation 路线。 |

## H. 结合当前项目的推荐阅读顺序

### 第一层：立即相关

1. BEVFusion
2. UniAD
3. VAD
4. VADv2
5. nuPlan
6. Bench2Drive
7. 2D Gaussian Splatting
8. DrivingGaussian
9. Street Gaussians
10. CityGaussianV2

### 第二层：两周内补齐

1. BEVFormer
2. SurroundOcc
3. OccFormer
4. DriveAdapter
5. Hydra-MDP
6. Hydra-NeXt
7. MapTR
8. MapTRv2
9. LiHi-GS
10. DeSiRe-GS

### 第三层：中长期观察

1. DriveDreamer
2. DriveDreamer-2
3. GAIA-1
4. Drive-OccWorld
5. SparseDrive
6. GenAD
7. HUGSIM
8. ScenarioNet
9. SafeBench

## I. 整理规则

1. 仓库内优先整理“链接 + 分类 + 为什么相关”，不要默认把所有 PDF 都收进 Git。
2. 只有团队明确要共读、文件体积可接受的论文，才进入 `references/papers/`。
3. 新增论文时，至少同步更新：
   - 本文档
   - [PAPER_READING_MAP_CN.md](./PAPER_READING_MAP_CN.md)
   - 如有本地 PDF，再更新 [LOCAL_PDF_INDEX_CN.md](./LOCAL_PDF_INDEX_CN.md)
