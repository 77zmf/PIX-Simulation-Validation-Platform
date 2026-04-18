# 本机三维重建验证手册

## 结论

当前这台电脑先承担 `reconstruction asset validation` 和小规模 smoke test，不直接作为大规模 3DGS / NeRF 训练主机。

第一阶段目标是确认完整地图资产束可用：

- lanelet2 地图可读
- projector 信息可读
- pointcloud tile 数量和 metadata 一致
- PCD 文件头可读
- 本机工具链状态明确
- `simctl run` 能生成 reconstruction 场景的 `run_result.json`

## 1. 当前资产入口

当前完整资产束：

```text
site_gy_qyhx_gsh20260310
```

轻量 manifest：

```text
assets/manifests/site_gy_qyhx_gsh20260310.yaml
```

本地大文件，不进入 Git：

```text
gy_qyhx_gsh20260310_map(2).zip
artifacts/assets/site_gy_qyhx_gsh20260310/
```

## 2. 资产级验证

先运行：

```powershell
python -m simctl asset-check --bundle site_gy_qyhx_gsh20260310
```

再运行本机三维重建资产验证：

```powershell
python .\tools\validate_reconstruction_assets.py --bundle site_gy_qyhx_gsh20260310
```

输出：

```text
outputs/reconstruction_validation/site_gy_qyhx_gsh20260310/asset_validation.json
outputs/reconstruction_validation/site_gy_qyhx_gsh20260310/asset_validation.md
```

## 3. 场景级 smoke

先用 mock result 验证控制面是否能识别完整资产束：

```powershell
python -m simctl run --scenario scenarios/l2/reconstruction_site_proxy_refresh.yaml --run-root outputs/reconstruction_runs --mock-result passed
python -m simctl run --scenario scenarios/l2/reconstruction_public_road_map_refresh.yaml --run-root outputs/reconstruction_runs --mock-result passed
```

这一步不代表真实重建已经完成，只代表：

- scenario YAML 可加载
- asset bundle 可解析
- sensor profile 可解析
- reconstruction adapter 可解析
- run_result / KPI gate / replay 入口可生成

## 4. 真正重建前的工具要求

资产级验证通过后，再准备真实重建工具：

- `ffmpeg`：视频抽帧
- `colmap`：SfM / camera pose / sparse point cloud
- `open3d`：点云可视化和基本统计
- 可选：Gaussian Splatting / Nerfstudio-style 工具

当前建议顺序：

1. 资产级验证
2. COLMAP sparse smoke
3. Open3D 点云抽样检查
4. 小片段 Gaussian / NeRF 对比
5. 形成可服务 CARLA / site proxy 的重建资产候选

## 5. 验收标准

第一阶段通过条件：

- `asset-check` 的 `all_required_present=true`
- pointcloud tile count 和 metadata 均为 `3624`
- PCD sample headers 可读
- projector 有 map origin
- reconstruction 场景能生成 `run_result.json`

第二阶段通过条件：

- COLMAP 可以从采集图片或视频抽帧中注册相机
- sparse model 可视化可打开
- 能记录注册率、稀疏点数量、运行时间和失败分类

## 6. 边界

这条线属于 `reconstruction line`。

不要把本机三维重建 smoke test 和公司 Ubuntu 主机上的 stable closed-loop 验收混在一起。重建资产可以服务仿真验证，但不能阻塞 stable 主线。
