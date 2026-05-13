# Qiyu 0509 Reconstruction Quality Gate

## Objective

Use the 0509 Qiyu same-source image pack, dynamic masks, and pose priors to decide whether static/background 3DGS segments are ready for retraining or need targeted optimization.

This does not replace CARLA stable map import. For CARLA 0.9.15 / UE4.26, the drivable asset target remains `mesh + OpenDRIVE + collision proxy`; Gaussian output is a visual/research layer until a NuRec-capable runtime is installed and smoke-tested.

## Scope

Inputs stay outside Git:

- image pack: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_keyframe_image_pack/reconstruction_image_pack_manifest.json`
- same-source pose prior: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_carla_3dgs_handoff/gnss_constrained_rebuild_20260510/gnss_constraint_summary.json`
- current segment results: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_gnss_constrained_lidar_segments_250m_fullroute_results_train80k`
- report output: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_quality_gate_20260512`

Cross-source 0430 FAST-LIO2 / LIO-RF outputs can be passed as comparison evidence, but the gate excludes them from 0509 training decisions when their `source_bag` does not match the image pack.

## Command

```bash
python3 tools/build_reconstruction_quality_gate.py \
  --image-pack-manifest outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_keyframe_image_pack/reconstruction_image_pack_manifest.json \
  --pose-prior gnss_0509=outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_carla_3dgs_handoff/gnss_constrained_rebuild_20260510/gnss_constraint_summary.json \
  --pose-prior fast_lio2_gnss_backend_0430=outputs/reconstruction_precheck/fast_lio2_gnss_backend_qiyu_20260430_20260512/fast_lio2_gnss_backend_metrics.json \
  --pose-prior lio_rf_gps_factor_0430=outputs/reconstruction_precheck/liorf_qiyu_20260430_full_20260512_112648/liorf_full_rtk_comparison.json \
  --segment-results-dir outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_gnss_constrained_lidar_segments_250m_fullroute_results_train80k \
  --output-dir outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_quality_gate_20260512
```

## Current Result

Generated on 2026-05-12:

- gate status: `needs_optimization`
- image pack: `pass`, 5612 / 5616 images, missing ratio `0.000712`
- dynamic masks: `pass`, 25887 projected boxes
- accepted pose prior: `gnss_0509`, quality `pass`
- excluded pose priors: `fast_lio2_gnss_backend_0430`, `lio_rf_gps_factor_0430`, both due to `source_bag_mismatch`
- segments: 19 total, 9 `fail`, 9 `review`, 1 `pass`
- PSNR: min `13.913`, median `15.741`, max `19.036`

Worst segments:

| segment | status | psnr | reason |
| --- | --- | ---: | --- |
| `qiyu82_gnss_seg_002_0500m_0750m_balanced` | `fail` | 13.913 | `psnr_below_15` |
| `qiyu82_gnss_seg_009_2250m_2500m_balanced` | `fail` | 14.046 | `psnr_below_15` |
| `qiyu82_gnss_seg_008_2000m_2250m_balanced` | `fail` | 14.138 | `psnr_below_15` |
| `qiyu82_gnss_seg_013_3250m_3500m_balanced` | `fail` | 14.277 | `psnr_below_15` |
| `qiyu82_gnss_seg_012_3000m_3250m_balanced` | `fail` | 14.665 | `psnr_below_15` |

## Decision

The 0509 image and mask pipeline is not the current blocker. The next optimization should focus on failed/review 3DGS segments and on rerunning FAST-LIO2 + GNSS backend / LIO-RF GPS factor on the same 0509 source if a stronger pose-prior comparison is needed.

## Evalfix Retrain Pass

The first retrain pass generated an 18-job plan from the quality gate:

```bash
python3 tools/build_reconstruction_retrain_plan.py \
  --quality-gate-json outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_quality_gate_20260512/reconstruction_quality_gate.json \
  --output-dir outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_retrain_plan_evalfix_20260512 \
  --remote-output-root /data/pix/reconstruction/runs/qiyu_recon_82_core_20260509_151725/gnss_constrained_lidar_segments_250m_retrain_evalfix_20260512
```

The runner was updated to write aggregate final evaluation metrics across all sampled frames. The quality gate now prefers `final_eval.psnr_median` over the historical last-frame `final_metric.psnr` when present.

Generated result:

- output root: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_retrain_evalfix_results_20260512`
- quality gate: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_retrain_evalfix_quality_gate_20260512/reconstruction_quality_gate.md`
- gate status: `needs_optimization`
- segments: 18 targeted, 2 `fail`, 16 `review`
- median PSNR: `16.200`
- worst remaining segments:
  - `qiyu82_gnss_seg_009_2250m_2500m_balanced_psnr_retrain_high_detail`: `fail`, PSNR `14.827`
  - `qiyu82_gnss_seg_011_2750m_3000m_balanced_review_refine`: `fail`, PSNR `14.994`
  - `qiyu82_gnss_seg_010_2500m_2750m_balanced_psnr_retrain_high_detail`: `review`, PSNR `15.349`
  - `qiyu82_gnss_seg_013_3250m_3500m_balanced_psnr_retrain_high_detail`: `review`, PSNR `15.435`
  - `qiyu82_gnss_seg_012_3000m_3250m_balanced_psnr_retrain_high_detail`: `review`, PSNR `15.451`

Interpretation:

- The previous last-frame metric was too noisy for segment acceptance.
- Higher point count and iteration budget moved the targeted set from 9 fail / 9 review to 2 fail / 16 review under aggregate evaluation.
- The remaining weak segments are dominated by per-camera quality imbalance, especially `front_right` and `front_3mm` in several ranges.
- The next optimization should add camera-aware scoring or per-camera filtering before another full pass.

## Camera Ablation

The remaining two failed segments were rerun with camera-set ablations. These runs use the same masked LiDAR 3DGS runner and aggregate `final_eval.psnr_median` over sampled frames.

Segment `009`, 2250m-2500m:

| rank | camera set | PSNR median | note |
| ---: | --- | ---: | --- |
| 1 | `front_left` | 15.947 | best single camera, moves out of fail range |
| 2 | `front_left,front_right` | 14.732 | `front_right` pulls the median back below 15 |
| 3 | `front_right` | 14.617 | weak |
| 4 | `front_3mm,front_left` | 14.449 | `front_3mm` pulls the pair below 15 |
| 5 | `front_3mm` | 14.194 | weakest |

Segment `011`, 2750m-3000m:

| rank | camera set | PSNR median | note |
| ---: | --- | ---: | --- |
| 1 | `front_left` | 16.292 | best single camera, moves out of fail range |
| 2 | `front_left,front_right` | 15.563 | usable but lower than `front_left` alone |
| 3 | `front_3mm,front_left` | 14.664 | `front_3mm` pulls the pair below 15 |
| 4 | `front_right` | 14.652 | weak |
| 5 | `front_3mm` | 14.366 | weakest |

Camera ablation artifacts:

- segment 009: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_camera_ablation_results_20260512/camera_ablation_summary.md`
- segment 011: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_camera_ablation_seg011_results_20260512/camera_ablation_summary.md`
- visual comparison sheet: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_camera_ablation_comparison_20260512.jpg`

Frame-level diagnostics:

```bash
python3 tools/build_reconstruction_camera_diagnostics.py \
  --frame-index-csv outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_keyframe_image_pack/keyframe_image_index.csv \
  --segment-manifest outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_retrain_evalfix_results_20260512/qiyu82_gnss_seg_009_2250m_2500m_balanced_psnr_retrain_high_detail/masked_lidar_gsplat_smoke_manifest.json \
  --segment-manifest outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_retrain_evalfix_results_20260512/qiyu82_gnss_seg_011_2750m_3000m_balanced_review_refine/masked_lidar_gsplat_smoke_manifest.json \
  --output-dir outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_camera_diagnostics_20260512
```

Diagnostic output:

- `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_camera_diagnostics_20260512/reconstruction_camera_diagnostics.md`
- aggregate worst camera: `front_3mm`
- aggregate low-PSNR cameras: `front_3mm`, `front_right`
- all three front cameras show sampled timestamp offsets above `0.08s` in at least one weak segment, so timestamp alignment still needs review before the next all-camera pass.

Decision:

- Do not run the next optimization as all-camera training by default on weak ranges.
- Treat `front_left` as the current static-background quality anchor for failed ranges.
- Inspect `front_3mm` and `front_right` calibration, timestamp alignment, and view coverage before using them as positive training views. Current blur/exposure proxies do not explain the failure by themselves.
- For CARLA import preparation, keep the formal path as `mesh + OpenDRIVE + collision proxy`. The Gaussian result remains a visual layer until the weak-camera issue is resolved and a NuRec-capable runtime is available.

## Quality-Filtered Retrain Pass

The retrain planner now supports `--camera-policy quality-filter`. This keeps cameras whose prior per-camera median PSNR is at least `15.0`; if no camera passes, it keeps only the best camera for that segment.

```bash
python3 tools/build_reconstruction_retrain_plan.py \
  --quality-gate-json outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_retrain_evalfix_quality_gate_20260512/reconstruction_quality_gate.json \
  --output-dir outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_quality_filtered_retrain_plan_20260512 \
  --remote-output-root /data/pix/reconstruction/runs/qiyu_recon_82_core_20260509_151725/quality_filtered_retrain_20260512 \
  --camera-policy quality-filter \
  --min-camera-psnr 15.0
```

Generated artifacts:

- plan: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_quality_filtered_retrain_plan_20260512/reconstruction_retrain_plan.md`
- result mirror: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_quality_filtered_retrain_results_20260512`
- quality gate: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_quality_filtered_quality_gate_20260512/reconstruction_quality_gate.md`
- comparison: `outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_quality_filtered_comparison_20260512.md`

Result:

- PSNR min improved from `14.827` to `15.629`
- PSNR median improved from `16.200` to `16.365`
- cameras below PSNR 15 were cleared in the final quality gate
- gate status remains `needs_optimization`
- status counts changed from `2 fail / 16 review` to `6 fail / 12 review`
- the new failures are driven by `colorized_ratio_below_0_90`, not PSNR below 15

Interpretation:

- Camera filtering is useful as a diagnostic and for recovering low-PSNR segments.
- Camera filtering is not a final full-route solution because single/pair camera training reduces image-colorized LiDAR coverage on several segments.
- The next root-cause path is not more blind retraining. It should check camera pose/extrinsic consistency, dynamic-mask projection, and multi-view coverage for `front_3mm` and `front_right`, then rerun multi-camera training.

## Validation

```bash
python3 -m unittest tests.test_reconstruction_quality_gate tests.test_reconstruction_retrain_plan tests.test_reconstruction_camera_diagnostics tests.test_curve_3dgs_carla_jobs tests.test_reconstruction_handoff_manifest -v
```

Expected: all tests pass.

## Rollback

Remove the quality gate report directory under `outputs/reconstruction_precheck/` to discard generated reports. Remove `tools/build_reconstruction_quality_gate.py`, `tests/test_reconstruction_quality_gate.py`, and this runbook to roll back the repo-side workflow.
