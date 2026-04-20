# Lanelet2 转 CARLA OpenDRIVE 稳定推进记录

## 目标

把 `site_gy_qyhx_gsh20260310` 的 Lanelet2 地图先转换成 CARLA 可以加载的 OpenDRIVE `.xodr` 文件，用作公开道路 `site proxy` 的第一版可导入地图。

这一步属于稳定线资产标准化，不替代后续 UE4 地图包、道路网拓扑精修、交通灯/标线语义补齐，也不阻塞当前 Autoware + CARLA 0.9.15 主线。

## 输入资产

当前推荐输入：

```text
G:\Carla\gy_qyhx_gsh20260310_map\lanelet2_map.osm
G:\Carla\gy_qyhx_gsh20260310_map\map_projector_info.yaml
```

配套资产仍按公开道路 bundle 管理：

```text
lanelet2_map.osm
map_projector_info.yaml
pointcloud_map.pcd\
pointcloud_map_metadata.yaml
```

大文件、原始地图、点云和生成出的 `.xodr` 不进 Git。仓库只记录转换工具、文档、轻量 manifest 和可复现命令。

## 生成命令

在 Windows 仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m simctl lanelet-to-opendrive `
  --lanelet G:\Carla\gy_qyhx_gsh20260310_map\lanelet2_map.osm `
  --projector G:\Carla\gy_qyhx_gsh20260310_map\map_projector_info.yaml `
  --output-dir outputs\carla_maps\site_gy_qyhx_gsh20260310 `
  --map-name site_gy_qyhx_gsh20260310
```

如果只想快速看前几段 road 是否能被 CARLA 解析：

```powershell
.\.venv\Scripts\python.exe -m simctl lanelet-to-opendrive `
  --lanelet G:\Carla\gy_qyhx_gsh20260310_map\lanelet2_map.osm `
  --projector G:\Carla\gy_qyhx_gsh20260310_map\map_projector_info.yaml `
  --output-dir outputs\carla_maps\site_gy_qyhx_gsh20260310_smoke `
  --map-name site_gy_qyhx_gsh20260310_smoke `
  --max-lanelets 20
```

默认用 Lanelet2 的 `left` 边界作为 OpenDRIVE reference line，右侧生成一条 `driving` lane。若 CARLA smoke 后发现地图左右镜像，再加 `--flip-y` 生成对照版本。

`tools\convert_lanelet2_to_opendrive.py` 保留为兼容入口，但团队日常优先使用 `simctl lanelet-to-opendrive`，方便后续纳入资产标准流程。

## 输出

默认输出目录：

```text
outputs\carla_maps\site_gy_qyhx_gsh20260310\
```

文件：

```text
site_gy_qyhx_gsh20260310.xodr
conversion_report.json
conversion_report.md
```

`conversion_report.json` 记录输入节点/way/lanelet 数量、输出 road 数量、跳过原因样例、坐标边界、projector 信息和已知限制，后续回填 issue 时可作为轻量证据。

## CARLA 0.9.15 导入 Smoke

正式验收放到公司 Ubuntu 22.04 稳定运行主机上，确保 CARLA 0.9.15 server 已启动，再用 Python client 加载：

```python
from pathlib import Path

import carla


client = carla.Client("127.0.0.1", 2000)
client.set_timeout(60.0)

xodr_text = Path("outputs/carla_maps/site_gy_qyhx_gsh20260310/site_gy_qyhx_gsh20260310.xodr").read_text()
params = carla.OpendriveGenerationParameters(
    vertex_distance=2.0,
    max_road_length=500.0,
    wall_height=0.0,
    additional_width=0.6,
    smooth_junctions=True,
    enable_mesh_visibility=True,
)
world = client.generate_opendrive_world(xodr_text, params)
print(world.get_map().name)
```

Smoke 成功信号：

- CARLA 不因 OpenDRIVE 解析失败退出。
- world 可以生成并返回 map。
- 车辆可在至少一段生成 road 上 spawn 或手动设置 transform。
- 地图朝向未明显镜像；若镜像，用 `--flip-y` 生成第二版对照。

## 当前限制

- junction 拓扑暂未连接，复杂路口先按多条 road 输出。
- traffic light、stop line、crosswalk、lane-change 细节暂未完整映射。
- 只生成 OpenDRIVE 道路网，不生成 UE4 视觉地图包、terrain、建筑或点云 mesh。
- Lanelet2 边界被转成 OpenDRIVE line geometry，曲率会由短线段近似。

## 下一步

1. 在 Windows 上生成完整 `.xodr` 与报告。
2. 把 `.xodr` 同步到公司 Ubuntu/CARLA 0.9.15 主机。
3. 做 `generate_opendrive_world` smoke，记录是否能加载、是否镜像、是否可 spawn。
4. 选 1 条公开道路 corner case 的起点和终点，补入 L0/L1 级 site proxy 场景。
5. 若 CARLA 能加载但道路连接差，下一轮再补 junction/link/traffic-control 映射。
