# LSX GSH0302 Reconstruction Intake

## Objective

Start the local 3D reconstruction line from the LSX public-road map at `lsx/lsx-gsh0302map` without putting large map or pointcloud files in Git.

## Asset Contract

Tracked bundle: `site_gy_qyhx_gsh20260302`

Expected local directory:

```text
lsx/lsx-gsh0302map/
  lanelet2_map.osm
  map_projector_info.yaml
  pointcloud_map.pcd/
  pointcloud_map_metadata.yaml
```

The bundle also keeps the previous archive path as a fallback source contract:

```text
gy_qyhx_gsh20260302_map.zip
```

## Local Validation

Run from the repository root after the LSX directory exists:

```bash
simctl asset-check --bundle site_gy_qyhx_gsh20260302
python tools/validate_reconstruction_assets.py --bundle site_gy_qyhx_gsh20260302
```

Run the pointcloud-map smoke on the local reconstruction producer:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\bootstrap_local_reconstruction.ps1 -Bundle site_gy_qyhx_gsh20260302 -RunAssetValidation -RunPointcloudSmoke -RunName lsx_gsh0302_pointcloud_smoke -HandoffRootUri "<shared-path-or-object-store-prefix>"
```

Direct smoke command:

```powershell
python .\tools\reconstruct_pointcloud_map.py --bundle site_gy_qyhx_gsh20260302 --selection center --max-tiles 16 --max-points 50000 --split-ground --clean-ground --run-name lsx_gsh0302_pointcloud_smoke
```

## Scenario Entry

Use the repo-side scenario contract:

```text
scenarios/l2/reconstruction_lsx_gsh0302_map_refresh.yaml
```

This is a reconstruction-support scenario, not stable closed-loop acceptance. It can produce reconstruction handoff assets for the company Ubuntu host to consume later, but it does not replace the stable validation chain:

```text
run_result -> KPI gate -> report -> replay
```

## Missing Inputs

- Real image/video capture is still required before COLMAP or Gaussian validation can start.
- The company Ubuntu host should consume synced handoff manifests and derived assets; it should not rerun reconstruction jobs in this phase.
- `dynamic Gaussian` remains future work until map refresh and static geometry smoke have usable evidence.

## Rollback

Remove `lsx/lsx-gsh0302map` locally or switch commands back to `site_gy_qyhx_gsh20260310`. No large artifacts are tracked by Git.
