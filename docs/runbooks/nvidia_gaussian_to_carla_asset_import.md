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

