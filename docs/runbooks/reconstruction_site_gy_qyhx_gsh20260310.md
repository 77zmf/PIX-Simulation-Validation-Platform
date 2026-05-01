# GY QYHX GSH20260310 Reconstruction Start

## Objective

Start the 3D reconstruction support line for `site_gy_qyhx_gsh20260310` without changing the stable closed-loop validation path.

This line is for:

- map refresh and localization-support asset checks
- pointcloud-map smoke reconstruction
- static Gaussian readiness after real image/video capture exists
- future dynamic Gaussian research after static geometry evidence is usable

It is not stable closed-loop acceptance. Stable acceptance still requires:

```text
run_result -> KPI gate -> report -> replay
```

## Current Asset Contract

Tracked manifest:

```text
assets/manifests/site_gy_qyhx_gsh20260310.yaml
```

Expected extracted asset root:

```text
artifacts/assets/site_gy_qyhx_gsh20260310/
  lanelet2_map.osm
  map_projector_info.yaml
  pointcloud_map.pcd/
  pointcloud_map_metadata.yaml
```

Expected source archive name:

```text
gy_qyhx_gsh20260310_map(2).zip
```

The manifest currently expects `3624` pointcloud tiles.

## Ubuntu Consumer Workspace

The company Ubuntu host has a dedicated data mount:

```text
/data/pix
```

Prepared reconstruction directories:

```text
/data/pix/reconstruction/inputs
/data/pix/reconstruction/outputs
/data/pix/reconstruction/handoffs
/data/pix/reconstruction/logs
/data/pix/reconstruction/manifests
/data/pix/reconstruction/tmp
/data/pix/assets/site_gy_qyhx_gsh20260310
/data/pix/assets/site_gy_qyhx_gsh20260302
```

Use `/data/pix/assets/site_gy_qyhx_gsh20260310` only as the synced asset-consumption path on the Ubuntu host. Heavy reconstruction production jobs should stay outside stable validation unless explicitly re-scoped.

## Start Commands

From the repository root, first check the tracked asset contract:

```bash
.venv/bin/python -m simctl asset-check --bundle site_gy_qyhx_gsh20260310
.venv/bin/python tools/validate_reconstruction_assets.py --bundle site_gy_qyhx_gsh20260310
```

After the real asset bundle is extracted under `artifacts/assets/site_gy_qyhx_gsh20260310`, run the first pointcloud smoke:

```bash
.venv/bin/python tools/reconstruct_pointcloud_map.py \
  --bundle site_gy_qyhx_gsh20260310 \
  --selection center \
  --max-tiles 16 \
  --max-points 50000 \
  --split-ground \
  --clean-ground \
  --run-name gsh20260310_pointcloud_smoke
```

Then build the heightmap and handoff manifest:

```bash
.venv/bin/python tools/build_ground_heightmap.py \
  --input-ply outputs/pointcloud_reconstruction/site_gy_qyhx_gsh20260310/gsh20260310_pointcloud_smoke/site_proxy_ground_clean.ply \
  --cell-size 1.0 \
  --min-points-per-cell 2

.venv/bin/python tools/build_reconstruction_handoff_manifest.py \
  --run-dir outputs/pointcloud_reconstruction/site_gy_qyhx_gsh20260310/gsh20260310_pointcloud_smoke \
  --site-id site_gy_qyhx_gsh20260310 \
  --handoff-root-uri /data/pix/reconstruction/handoffs/site_gy_qyhx_gsh20260310/gsh20260310_pointcloud_smoke
```

Scenario-level placeholder check:

```bash
.venv/bin/python -m simctl run \
  --scenario scenarios/l2/reconstruction_public_road_map_refresh.yaml \
  --run-root runs \
  --mock-result passed
```

This verifies the repo contract and KPI wiring only. It does not prove real reconstruction quality.

## Real Input Gate

Do not start COLMAP, static Gaussian, or dynamic Gaussian work until these inputs exist:

- extracted lanelet2 map and projector file
- `pointcloud_map.pcd/` with the manifest-declared tile count
- `pointcloud_map_metadata.yaml` matching the pointcloud directory
- calibrated camera images or video frames for COLMAP sparse reconstruction
- capture owner and source path

COLMAP is the first image-based smoke. Gaussian experiments only start after sparse reconstruction produces usable camera poses.

## Evidence To Keep

For every smoke run, keep:

- `asset_validation.json`
- `asset_validation.md`
- `pointcloud_smoke.json`
- `pointcloud_smoke.md`
- sampled or cleaned PLY outputs
- heightmap CSV/JSON/PNG when available
- `handoff_manifest.json`
- `handoff_manifest.md`

Large outputs stay under `outputs/`, `artifacts/`, or `/data/pix`; they are not committed to Git.

## Current Status

Started on 2026-04-28:

- Ubuntu consumer storage is ready at `/data/pix`.
- Reconstruction workspace directories exist under `/data/pix/reconstruction`.
- Repo scenario wiring for `reconstruction_public_road_map_refresh` can produce a mock `run_result.json`.
- Local asset validation is blocked because the real 20260310 archive or extracted pointcloud bundle is not present.

## Rollback

No stable runtime code is changed by this line.

To roll back local reconstruction outputs, remove:

```text
outputs/reconstruction_validation/site_gy_qyhx_gsh20260310
outputs/pointcloud_reconstruction/site_gy_qyhx_gsh20260310
```

To remove Ubuntu-side scratch data, remove only the reconstruction support directories under:

```text
/data/pix/reconstruction
```

Do not remove `/data/pix` itself; it is the mounted data disk.
