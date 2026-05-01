---
name: nvidia-gaussian-carla-asset-handoff
description: Use this skill when NVIDIA-route Gaussian, NuRec, LiDAR, mesh, OpenUSD, or pointcloud reconstruction outputs must be prepared as CARLA-importable public-road assets or reviewed for CARLA import readiness.
---

# Purpose

Convert NVIDIA-route reconstruction evidence into a CARLA asset handoff plan without confusing research rendering outputs with stable CARLA map assets.

# When to use

- deciding Gaussian / NuRec versus mesh for a CARLA import target
- preparing a LiDAR or Gaussian reconstruction result for CARLA map import
- checking whether source bags, camera frames, calibration, OpenDRIVE, mesh, or textures are sufficient
- building an asset handoff manifest for a non-Git reconstruction output
- planning CARLA 0.9.15 / UE4.26 import, cook, package, and sandbox validation

# Decision rules

- For current stable CARLA 0.9.15, prefer `mesh + OpenDRIVE` as the import target.
- Treat Gaussian / NuRec as NVIDIA research or visual-rendering assets unless a NuRec-capable CARLA runtime is installed and smoke-tested.
- Use a hybrid route when both are needed: mesh/OpenDRIVE for driving, collision, navigation, and sensors; Gaussian/NuRec for photorealistic visual replay.
- Do not start static Gaussian work until camera frames and usable poses exist.
- Do not start dynamic Gaussian work until static background, actor masks/tracks, and temporal consistency checks exist.
- Keep heavy outputs, checkpoints, cooked packages, and splats outside Git.

# Required checks

1. source evidence path and capture time
2. reconstruction output path and manifest
3. coordinate frame, scale, and axis convention
4. camera frame / calibration availability
5. lanelet / OpenDRIVE availability
6. CARLA runtime target and version
7. importable artifact target: FBX/OBJ/USD/XODR/texture/package
8. validation command or sandbox smoke
9. rollback / containment path

# Required output

1. target lane and objective
2. source assets and evidence
3. Gaussian vs mesh decision
4. missing inputs and blockers
5. next executable milestone
6. CARLA import readiness criteria
7. rollback note

# Companion agents

- Use `ops/subagents/gaussian_reconstruction_explorer.yaml` for the first repo scan.
- Use `ops/subagents/nvidia_carla_reconstruction_explorer.yaml` only when the question is specifically about NVIDIA NuRec/Gaussian versus CARLA import readiness.

