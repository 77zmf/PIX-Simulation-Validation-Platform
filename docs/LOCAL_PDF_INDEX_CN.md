# 本地 PDF 索引

## 目标

这份文档只整理当前已经进入仓库版本管理的 PDF，避免论文附件继续散落在仓库根目录。

当前统一目录：

- `references/papers/`

## PDF 清单

| 文件 | 论文标题 | 分类 | 来源 | 说明 |
| --- | --- | --- | --- | --- |
| `references/papers/2405.20323v1.pdf` | S3Gaussian: Self-Supervised Street Gaussians for Autonomous Driving | 公开道路动态重建 | [arXiv 2405.20323](https://arxiv.org/abs/2405.20323) | 适合作为 driving-specific Gaussian 补充阅读。 |
| `references/papers/hierarchyugp_iccv.pdf` | Hierarchy UGP: Hierarchy Unified Gaussian Primitive for Large-Scale Dynamic Scene Reconstruction | 大规模动态场景重建 | [ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/html/Sun_Hierarchy_UGP_Hierarchy_Unified_Gaussian_Primitive_for_Large-Scale_Dynamic_Scene_ICCV_2025_paper.html) | 更偏大规模动态场景和统一 Gaussian primitive。 |

## 当前整理规则

1. 仓库只保留小规模、确实需要团队共读的 PDF。
2. 原始大文件、数据集论文附件和训练资产不要直接进 Git 历史。
3. 新增 PDF 时，至少同步更新：
   - 本文档
   - [PAPER_READING_MAP_CN.md](./PAPER_READING_MAP_CN.md) 里的阅读分类
4. 文件命名优先保留原始论文标识或会议简称，避免中文文件名。

## 后续建议

- 如果本地 PDF 数量继续增长，下一步应按方向拆目录：
  - `references/papers/perception/`
  - `references/papers/planning/`
  - `references/papers/reconstruction/`
- 如果论文只需要链接不需要仓库内分发，优先只保留链接，不保留 PDF 本体。
