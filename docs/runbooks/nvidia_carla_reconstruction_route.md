# NVIDIA CARLA Reconstruction Route

## Objective

Use the NVIDIA reconstruction line for the Qiyu loop data while keeping the current CARLA 0.9.15 stable baseline protected.

This runbook is for deciding and preparing the asset form before CARLA import. It does not import anything into CARLA by itself.

## Current Evidence

Validated source bag on the company Ubuntu host:

```text
/data/pix/road_tests/qiyu_loop_20260430_second_lap/raw/perception_data_20260430105120
```

First LiDAR reconstruction output:

```text
/data/pix/reconstruction/runs/qiyu_loop_20260430_105120_lidar_map_smoke/full_map_base_link_complete_sample3s
```

Important generated files:

```text
qiyu_loop_20260430_105120_lidar_map_base_link_complete_sample3s.ply
trajectory_samples.csv
previews/sample_topdown.png
previews/z_histogram.png
handoff_manifest.json
```

## Decision

Use a hybrid route, but stage it in this order:

1. mesh plus OpenDRIVE for CARLA import
2. NVIDIA NuRec / Gaussian as a research visual layer after camera frames and poses exist

Reason:

- CARLA 0.9.15 / UE4.26 needs normal map assets for driving, collision, navigation, and sensor interaction.
- Gaussian or NuRec output is useful for NVIDIA neural rendering and appearance, but it is not the normal stable CARLA 0.9.15 import format.
- The current bag has LiDAR, TF, GNSS/IMU, and limited camera JPEG topics. It does not yet prove that calibrated dense camera frames and COLMAP-quality poses are available.

## Route A: CARLA Importable Mesh

Minimum asset targets:

```text
road_surface_mesh.fbx or road_surface_mesh.obj
static_scene_mesh.fbx or static_scene_mesh.obj
map.xodr
material/textures if available
import_manifest.json
```

Validation before import:

- mesh has sane scale and axes
- XODR route aligns with the mesh
- drivable road surface exists
- collision proxy exists or can be generated
- CARLA map package can be loaded in a non-stable sandbox

## Route B: NVIDIA NuRec / Gaussian

Minimum asset targets:

```text
camera_frames/
camera_intrinsics_extrinsics.json
trajectory_or_pose_prior.csv
static_gaussian_or_nurec_output/
nurec_manifest.json
```

Validation before NuRec/Gaussian:

- camera frames are present and time-aligned
- calibration is known
- sparse reconstruction or pose prior is usable
- output is labeled research/shadow unless a NuRec-capable CARLA runtime is installed

## Next Milestone

Before CARLA import, produce a mesh readiness package from the LiDAR reconstruction:

```text
/data/pix/reconstruction/runs/qiyu_loop_20260430_105120_lidar_mesh_candidate/
  source_manifest.json
  ground_or_road_surface.ply
  static_scene_sample.ply
  mesh_candidate.obj
  mesh_readiness_report.json
  mesh_readiness_report.md
```

If camera frames are later confirmed, run a separate NuRec/Gaussian readiness package instead of mixing it into the stable CARLA import path.

## Rollback

Remove only the reconstruction run directories under:

```text
/data/pix/reconstruction/runs/
```

Do not remove the source bag or `/data/pix` mount.
