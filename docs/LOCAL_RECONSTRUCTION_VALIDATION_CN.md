# 本机三维重建验证手册

## 结论

这台 Windows 主机当前先承担 `3D reconstruction line` 的本机验证，不承担大规模训练主机职责。

当前优先级：

1. 确认奇遇环线地图资产可被识别、统计和追踪。
2. 先用现有 PCD tile 做点云地图静态重建 smoke。
3. 再补图像或视频，做 COLMAP sparse smoke。
4. 最后决定是否进入 Gaussian / NeRF。
5. 重建输出只进入 `outputs/` 或 `artifacts/`，不进入 Git。

## 1. 当前资产入口

当前完整资产束：

```text
site_gy_qyhx_gsh20260310
```

轻量 manifest：

```text
assets/manifests/site_gy_qyhx_gsh20260310.yaml
```

本地大文件和解压目录：

```text
gy_qyhx_gsh20260310_map(2).zip
artifacts/assets/site_gy_qyhx_gsh20260310/
```

这些内容由 `.gitignore` 排除，仓库只保存 manifest、脚本、场景和报告模板。

## 2. 本机工具自检

先刷新当前 PowerShell 的 PATH：

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
```

运行统一自检：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\check_local_env.ps1
```

输出：

```text
outputs/env/reconstruction_tool_check.json
outputs/env/reconstruction_tool_check.md
```

当前本机已验证的工具版本：

```text
GPU: NVIDIA GeForce RTX 5060 Ti, 8 GB VRAM
FFmpeg: 8.1 essentials build
COLMAP: 4.0.3 CUDA build
Python venv: .venv
Python modules: numpy, open3d, opencv-python, trimesh, pycolmap
```

如果换机器后缺依赖，按脚本输出的 `install_hint` 补齐。

## 3. 资产级验证

运行：

```powershell
python -m simctl asset-check --bundle site_gy_qyhx_gsh20260310
python .\tools\validate_reconstruction_assets.py --bundle site_gy_qyhx_gsh20260310
```

输出：

```text
outputs/reconstruction_validation/site_gy_qyhx_gsh20260310/asset_validation.json
outputs/reconstruction_validation/site_gy_qyhx_gsh20260310/asset_validation.md
```

验收重点：

- `lanelet2_map.osm` 可读
- `map_projector_info.yaml` 可读
- `pointcloud_map.pcd/` tile 数量与 metadata 一致
- PCD sample header 可读
- projector origin 可追踪

## 4. 场景级 Smoke

先用 mock result 验证控制平面是否能识别重建相关场景：

```powershell
python -m simctl run --scenario scenarios/l2/reconstruction_site_proxy_refresh.yaml --run-root outputs\reconstruction_runs --mock-result passed
python -m simctl run --scenario scenarios/l2/reconstruction_public_road_map_refresh.yaml --run-root outputs\reconstruction_runs --mock-result passed
```

这一步只说明：

- scenario YAML 可加载
- asset bundle 可解析
- reconstruction adapter 可解析
- `run_result.json` / KPI gate / replay 入口可生成

这一步不代表真实三维重建已经完成。

## 5. 点云地图静态重建 Smoke

可以先用现有 `pointcloud_map.pcd/` 做静态场景重建代理。这条线不需要图像，也不需要 COLMAP 相机位姿。

运行小样本：

```powershell
python .\tools\reconstruct_pointcloud_map.py --bundle site_gy_qyhx_gsh20260310 --max-tiles 16 --max-points 50000 --selection largest
```

输出：

```text
outputs/pointcloud_reconstruction/site_gy_qyhx_gsh20260310/pointcloud_smoke_sample.ply
outputs/pointcloud_reconstruction/site_gy_qyhx_gsh20260310/pointcloud_smoke.json
outputs/pointcloud_reconstruction/site_gy_qyhx_gsh20260310/pointcloud_smoke.md
```

如果只看地图中心附近：

```powershell
python .\tools\reconstruct_pointcloud_map.py --bundle site_gy_qyhx_gsh20260310 --selection center --max-tiles 32 --max-points 100000
```

如果只看指定 tile 坐标范围：

```powershell
python .\tools\reconstruct_pointcloud_map.py --bundle site_gy_qyhx_gsh20260310 --region -100,100,-100,100 --max-tiles 0 --max-points 150000
```

验收重点：

- PLY 能被 Open3D、CloudCompare 或 MeshLab 打开
- 点云尺度和坐标范围合理
- 路面、路缘、建筑或障碍结构没有明显断裂
- z 分布没有明显异常漂移
- 输出点数可控，不把本机内存打满

这一步的用途是生成 `site proxy` 的静态几何候选，不包含纹理、相机位姿、动态物体或真实视觉外观。

## 6. COLMAP Sparse Smoke

真实 COLMAP 需要图像序列或视频。当前地图资产是 lanelet2 + pointcloud，不等价于相机重建数据。

准备输入：

```powershell
New-Item -ItemType Directory -Force -Path data\raw\qiyu_loop\video | Out-Null
New-Item -ItemType Directory -Force -Path data\raw\qiyu_loop\images | Out-Null
```

如果有视频，先抽帧：

```powershell
ffmpeg -i data\raw\qiyu_loop\video\input.mp4 -vf "fps=2,scale=-1:1080" data\raw\qiyu_loop\images\frame_%06d.jpg
```

跑 sparse reconstruction：

```powershell
$workspace = "outputs\colmap_smoke\qiyu_loop"
New-Item -ItemType Directory -Force -Path "$workspace\sparse" | Out-Null

colmap feature_extractor --database_path "$workspace\database.db" --image_path "data\raw\qiyu_loop\images" --ImageReader.single_camera 1
colmap exhaustive_matcher --database_path "$workspace\database.db"
colmap mapper --database_path "$workspace\database.db" --image_path "data\raw\qiyu_loop\images" --output_path "$workspace\sparse"
colmap model_analyzer --path "$workspace\sparse\0"
```

验收指标：

- registered images 数量
- sparse points 数量
- 平均重投影误差
- 运行时间
- 是否能用 COLMAP GUI 或后续脚本打开模型

## 7. 后续 Gaussian / NeRF 入口

只有当 COLMAP sparse smoke 通过后，再进入 Gaussian / NeRF。

建议顺序：

1. 小片段静态场景 Gaussian Splatting。
2. 对比 COLMAP sparse、原始 pointcloud、Gaussian 输出的一致性。
3. 记录视觉缺陷：漂浮物、尺度错误、路面破碎、动态物体残影。
4. 再考虑服务 CARLA site proxy 或 corner case 场景资产。

## 8. 边界

这条线是 `3D reconstruction line`，不要和公司 Ubuntu 主机上的 `stable local validation line` 混在一起。

重建资产可以服务仿真验证，但不能阻塞 Autoware + CARLA 0.9.15 的稳定闭环主线。
