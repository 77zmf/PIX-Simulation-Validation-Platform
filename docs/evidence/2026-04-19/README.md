# 2026-04-19 Robobus / CARLA Evidence

This folder contains selected lightweight screenshots for the 2026-04-19 leader-facing progress report.

The original runtime artifacts remain under `artifacts/` and are intentionally not used as the long-term Git evidence path. These selected PNGs are small enough to keep in Git so GitHub issues can render them directly.

## Selected Screenshots

| File | Evidence purpose |
| --- | --- |
| `closed_loop_route_sync_frame.png` | Robobus closed-loop route synchronization visual evidence. |
| `multi_actor_overview_frame.png` | Multi-actor cut-in / lead-brake planning-control scenario overview. |
| `robobus_direct_actor_after_drive.png` | `vehicle.pixmoving.robobus` direct CARLA actor after-drive evidence. |
| `sensor_cam_front.png` | Front camera topic visual sample for Robobus sensor mapping. |
| `lidar_top_m1plus_bev.png` | Top M1Plus lidar BEV sample for Robobus sensor mapping. |

## Source Runtime Paths

- `artifacts/remote_runs/robobus117th_closed_loop_pix_throttle_20260419T110107Z/closed_loop_route_sync_frame.png`
- `artifacts/remote_runs/20260419T021437707113Z__stable_l2_planning_control_multi_actor_cut_in_lead_brake/pix_robobus_multi_actor_overview_20260419T022221Z.mp4.png`
- `artifacts/remote_runs/robobus_single_actor_visual_20260419T081239Z/pix_robobus_direct_after_drive.png`
- `artifacts/screenshots/sensor_visual_samples_20260418T191355/cam_front.png`
- `artifacts/screenshots/sensor_visual_samples_20260418T191355/lidar_top_m1plus_bev.png`

## Validation Boundary

These screenshots are visual evidence for reporting. Formal stable-line acceptance still requires the company Ubuntu host runtime chain:

`simctl campaign --config ops/test_campaigns/stable_perception_control.yaml --slot stable-slot-01 --execute`
