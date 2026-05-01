---
name: pix-nvidia-carla-reconstruction
description: Use when deciding or executing the NVIDIA reconstruction route for CARLA-importable public-road assets, including NuRec/Gaussian versus mesh, OpenUSD handoff, CARLA custom map import, and reconstruction evidence packaging.
---

# PIX NVIDIA CARLA Reconstruction

Use this skill for NVIDIA-route reconstruction work that may later become a CARLA asset. Keep it separate from stable closed-loop validation unless the user explicitly asks to run stable acceptance.

For portable repo-side workflows, also consult `ops/skills/nvidia-gaussian-carla-asset-handoff/SKILL.md`.

## Procedure

1. Identify the target CARLA lane:
   - `stable_carla0915`: current company host baseline; requires CARLA 0.9.15 / UE4.26 compatible map assets.
   - `nvidia_nurec_research`: NVIDIA neural rendering route; requires a separate NuRec-capable CARLA/NVIDIA stack.
2. Inspect source evidence first:
   - validated raw bag or image/video path
   - LiDAR pointcloud output and trajectory CSV
   - camera images/video and calibration availability
   - lanelet/OpenDRIVE/projector availability
3. Decide asset form:
   - choose `mesh + OpenDRIVE` when the asset must be imported into current CARLA as a drivable map with collision, navigation, and sensor interaction.
   - choose `Gaussian/NuRec` when the goal is NVIDIA neural rendering or photorealistic visual replay; keep it research/shadow unless a NuRec CARLA runtime is available.
   - choose `hybrid` when both are needed: mesh/OpenDRIVE for CARLA physics, Gaussian/NuRec for visual fidelity.
4. Keep outputs outside Git:
   - `/data/pix/reconstruction/runs/...`
   - `/data/pix/reconstruction/handoffs/...`
   - `outputs/` or `artifacts/`
5. Preserve traceability:
   - source bag/image paths
   - run summary and preview artifacts
   - handoff manifest with SHA256
   - CARLA runtime target and version

## Decision Rules

- Do not claim Gaussian splats are directly importable as a normal CARLA 0.9.15 map.
- Do not start static Gaussian work until camera frames and usable poses exist.
- Do not start dynamic Gaussian work until static background and actor masks/tracks exist.
- For CARLA 0.9.15 import, the practical route is mesh/FBX plus OpenDRIVE/XODR, then UE/CARLA packaging.
- For NVIDIA NuRec, treat the output as a research rendering asset until the NuRec runtime is installed and smoke-tested.

## Output Contract

Return:

1. target lane and objective
2. source assets and current evidence
3. Gaussian vs mesh decision
4. required toolchain and host gaps
5. exact next commands or artifacts to produce
6. CARLA import readiness criteria
7. rollback / containment notes
