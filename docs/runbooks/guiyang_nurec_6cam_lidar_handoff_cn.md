# 贵阳 NuRec 6 相机 + LiDAR 交付接入

## 定位

该成果进入超体计划的 `reconstruction_support / shadow` 线，用于记录同事已经完成的重建资产、视觉证据和后续质量门禁。它不替代 CARLA 0.9.15 稳定运行时，也不代表已经生成可驾驶 CARLA 地图。

稳定线边界保持不变：

`CARLA 0.9.15 可驾驶地图 = mesh + OpenDRIVE/XODR + collision proxy`

NuRec 当前交付：

`6 相机 + 1 LiDAR + 200 帧/位姿 -> 20k checkpoint/USDZ/PLY -> 预览图/视频 -> SHA256 交付清单`

## 证据入口

- 资产清单：`assets/manifests/nvidia_guiyang_nurec_6cam_lidar_20k.yaml`
- 影子场景：`scenarios/l2/reconstruction_guiyang_nurec_6cam_lidar_shadow_handoff.yaml`
- 质量门禁：`evaluation/kpi_gates/reconstruction_nurec_visual_handoff_gate.yaml`
- 主机交付目录：`/data/pix/reconstruction/handoffs/guiyang_nurec_6cam_lidar_20k_20260713`
- 本机评审缓存：`reports/colleague_nurec_review_20260713`

主机交付目录包含 17 个文件的路径、大小和 SHA256，以及 Instant-NuRec 的 source lock。`ARTIFACT_SHA256SUMS` 校验 17 个外部重建产物，`SHA256SUMS` 校验 4 个交付包元数据文件；大型 checkpoint、USDZ、PLY 和视频不进入 Git。

## 当前结论

已完成：

- 200 帧、6 相机、1 个合并 LiDAR、200 个位姿的输入链可追踪。
- 标准版与带目标物版均有 20k checkpoint 和 USDZ。
- 背景、道路、合并 Gaussian PLY 及多相机预览、20 秒视频已纳入清单。
- 17/17 交付文件都有 SHA256。

尚未通过正式提升门禁：

- 缺 PSNR、SSIM、LPIPS 等量化质量结果。
- Instant-NuRec 工作区有 5 个未提交修改，尚不能从干净源码锁复现。
- 缺 CARLA 0.9.15 所需 mesh、XODR 和 collision proxy，也未做 CARLA sandbox load smoke。

## 本地检查

```bash
PYTHONPATH=src python3 -m simctl.cli asset-check \
  --bundle nvidia_guiyang_nurec_6cam_lidar_20k

PYTHONPATH=src python3 -m unittest \
  tests.test_guiyang_nurec_handoff -v
```

`asset-check` 通过只代表清单结构和外部 URI 完整，不等于重建质量通过。

## 提升顺序

1. 固化并提交/补丁化同事的 5 个 Instant-NuRec 修改，重新生成 `source_lock.json`。
2. 对标准版和带目标物版生成 PSNR、SSIM、LPIPS 与多相机关键帧评审结果。
3. 在固定 NuRec 环境中完成 checkpoint replay，形成真实 runtime evidence。
4. 若要进入 CARLA 稳定线，另行生成 mesh、XODR、collision bundle，并通过 CARLA load、spawn、route smoke。

## 回滚

删除新增 manifest、scenario、gate、测试和本 runbook 即可。主机重建产物与同事工作区均不受影响。
