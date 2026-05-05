# NVIDIA Gaussian To CARLA Asset Import

This runbook is the execution-facing companion to:

```text
docs/runbooks/nvidia_carla_reconstruction_route.md
ops/skills/nvidia-gaussian-carla-asset-handoff/SKILL.md
```

## Current Decision

Use the hybrid route, staged as:

1. `mesh + OpenDRIVE` for current CARLA 0.9.15 import readiness
2. `NuRec / Gaussian` for NVIDIA visual-replay research after camera frames and poses exist

## Why Mesh First

The current stable CARLA target needs map assets that support:

- drivable roads
- collision
- lane and route alignment
- sensor interaction
- UE4.26 / CARLA 0.9.15 packaging

Gaussian or NuRec output is valuable for appearance and neural rendering, but it should not be treated as the default CARLA 0.9.15 map format.

## Current Input

Validated source bag:

```text
/data/pix/road_tests/qiyu_loop_20260430_second_lap/raw/perception_data_20260430105120
```

LiDAR reconstruction output:

```text
/data/pix/reconstruction/runs/qiyu_loop_20260430_105120_lidar_map_smoke/full_map_base_link_complete_sample3s
```

## Next Executable Milestone

Produce a mesh-readiness package from the LiDAR PLY:

```text
/data/pix/reconstruction/runs/qiyu_loop_20260430_105120_lidar_mesh_candidate/
  source_manifest.json
  road_surface_points.ply
  static_scene_points.ply
  mesh_candidate.obj
  mesh_readiness_report.json
  mesh_readiness_report.md
```

The mesh candidate is not a CARLA import until it has an aligned OpenDRIVE/XODR file and a sandbox CARLA load smoke.

## CARLA Import Readiness Criteria

- mesh scale and axes are documented
- drivable surface is separated from non-road clutter
- OpenDRIVE route aligns with the mesh
- collision proxy exists or is generated
- import is tested in a non-stable CARLA sandbox
- generated package and logs are referenced by a handoff manifest

## NuRec / Gaussian Gate

Do not start the NVIDIA visual route until these are available:

- camera frames or video
- camera intrinsics and extrinsics
- pose prior or sparse reconstruction
- clear target runtime: NuRec-capable CARLA/NVIDIA stack versus offline visual demo

## Curve-First 3DGS Handoff

For Qiyu loop turns, generate one reconstruction job per detected curve cluster before running any heavy trainer:

```bash
python tools/build_curve_3dgs_carla_jobs.py \
  --xodr /data/pix/reconstruction/runs/qiyu_loop_20260430_105120_carla_import_bundle/qiyu_loop_20260430_105120.xodr \
  --source-bag /data/pix/road_tests/qiyu_loop_20260430_second_lap/raw/perception_data_20260430105120 \
  --metadata /data/pix/road_tests/qiyu_loop_20260430_second_lap/raw/perception_data_20260430105120/metadata.yaml \
  --pointcloud-ply /data/pix/reconstruction/runs/qiyu_loop_20260430_105120_lidar_map_smoke/full_map_base_link_complete_sample3s/qiyu_loop_20260430_105120_lidar_map_base_link_complete_sample3s.ply \
  --trajectory-csv /data/pix/reconstruction/runs/qiyu_loop_20260430_105120_lidar_map_smoke/full_map_base_link_complete_sample3s/trajectory_samples.csv \
  --import-manifest /data/pix/reconstruction/runs/qiyu_loop_20260430_105120_carla_import_bundle/carla_import_bundle_manifest.json \
  --import-preflight-report /data/pix/reconstruction/runs/qiyu_loop_20260430_105120_carla_import_prep/carla_import_preflight_report.json \
  --output-dir /data/pix/reconstruction/runs/qiyu_loop_20260430_105120_curve_3dgs_jobs
```

This produces:

- `curve_3dgs_carla_jobs.json`
- `curve_3dgs_carla_jobs.md`
- per-curve expected output paths under `jobs/qiyu_curve_*`
- per-curve CARLA-local crop bboxes and, when the import preflight report is provided, source-map crop bboxes for MCAP frame/pose extraction

Each curve job keeps the stable CARLA import contract explicit:

- `3DGS / NuRec`: visual reconstruction layer
- `mesh + OpenDRIVE + collision proxy`: CARLA 0.9.15 drivable import path

Do not publish a curve as CARLA-importable until the handoff manifest references the mesh/XODR/collision proxy and a sandbox CARLA load or route smoke.
