# 0509 Reconstruction Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable quality gate for the 0509 Qiyu reconstruction line so blurry 3DGS segments are traced to image readiness, dynamic masks, pose priors, or segment training metrics before retraining.

**Architecture:** Add a repo-local `tools/build_reconstruction_quality_gate.py` command that reads existing image-pack, pose-prior, and masked-gsplat segment manifests, then writes JSON and Markdown reports. Keep heavy images, checkpoints, splats, and bag data outside Git; the tool only records paths, readiness decisions, and optimization actions.

**Tech Stack:** Python 3 standard library, existing `tools/` script style, `unittest` tests imported from `tests/`.

---

### File Structure

- Create: `tools/build_reconstruction_quality_gate.py`
  - Reads `reconstruction_image_pack_manifest.json`.
  - Reads one or more pose-prior summaries from `--pose-prior name=path`.
  - Scans `--segment-results-dir` for `masked_lidar_gsplat_smoke_manifest.json`.
  - Writes `reconstruction_quality_gate.json` and `reconstruction_quality_gate.md`.
- Create: `tests/test_reconstruction_quality_gate.py`
  - Verifies same-source pose priors are accepted, cross-source priors are excluded, masks are required, and weak segment PSNR triggers `needs_optimization`.
- Create: `docs/superpowers/plans/2026-05-12-reconstruction-quality-gate.md`
  - Records this implementation plan and validation commands.

### Task 1: Test The Quality Gate Contract

**Files:**
- Create: `tests/test_reconstruction_quality_gate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_quality_gate_excludes_cross_source_pose_and_flags_weak_segments() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        image_manifest = root / "image_manifest.json"
        pose_same = root / "gnss_0509.json"
        pose_cross = root / "fast_lio2_0430.json"
        segments = root / "segments"
        output = root / "out"

        image_manifest.write_text(json.dumps({...}), encoding="utf-8")
        pose_same.write_text(json.dumps({...}), encoding="utf-8")
        pose_cross.write_text(json.dumps({...}), encoding="utf-8")
        (segments / "seg_good").mkdir(parents=True)
        (segments / "seg_good" / "masked_lidar_gsplat_smoke_manifest.json").write_text(json.dumps({...}), encoding="utf-8")
        (segments / "seg_weak").mkdir(parents=True)
        (segments / "seg_weak" / "masked_lidar_gsplat_smoke_manifest.json").write_text(json.dumps({...}), encoding="utf-8")

        report = reconstruction_quality_gate.build_quality_gate(
            image_pack_manifest=image_manifest,
            pose_prior_specs=[f"gnss_0509={pose_same}", f"fast_lio2_0430={pose_cross}"],
            segment_results_dir=segments,
            output_dir=output,
        )

    assert report["status"] == "needs_optimization"
    assert report["pose_priors"]["accepted"][0]["name"] == "gnss_0509"
    assert report["pose_priors"]["excluded"][0]["reason"] == "source_bag_mismatch"
    assert report["segments"]["status_counts"]["fail"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_reconstruction_quality_gate -v`

Expected: fails because `tools/build_reconstruction_quality_gate.py` does not exist yet.

### Task 2: Implement The Minimal Quality Gate

**Files:**
- Create: `tools/build_reconstruction_quality_gate.py`

- [ ] **Step 1: Implement manifest loading and image-pack checks**

```python
def summarize_image_pack(manifest: dict[str, Any]) -> dict[str, Any]:
    expected = int(manifest.get("expected_image_count") or 0)
    actual = int(manifest.get("image_count") or manifest.get("actual_image_count") or 0)
    missing = int(manifest.get("missing_image_count") or max(expected - actual, 0))
    mask_job_count = int((manifest.get("masking") or {}).get("mask_job_count") or 0)
    projected_box_count = int((manifest.get("masking") or {}).get("projected_box_count") or 0)
    return {"status": "pass" if expected and missing / expected <= 0.01 and mask_job_count >= actual else "fail", ...}
```

- [ ] **Step 2: Implement pose-prior extraction**

```python
def summarize_pose_prior(name: str, path: Path, source_bag: str | None) -> dict[str, Any]:
    data = read_json(path)
    prior_source = data.get("source_bag") or (data.get("inputs") or {}).get("source_bag")
    metrics = extract_pose_metrics(data)
    accepted = bool(prior_source and source_bag and str(prior_source) == source_bag)
    return {"name": name, "source_bag": prior_source, "accepted": accepted, "metrics": metrics}
```

- [ ] **Step 3: Implement segment scoring**

```python
def score_segment(manifest: dict[str, Any], segment_id: str) -> dict[str, Any]:
    psnr = float((manifest.get("final_metric") or {}).get("psnr") or 0.0)
    frame_count = int(manifest.get("frame_count") or 0)
    ratio = float((manifest.get("point_stats") or {}).get("image_colorized_ratio") or 0.0)
    status = "pass" if psnr >= 18.0 and frame_count >= 24 and ratio >= 0.95 else "review"
    if psnr < 15.0 or frame_count < 18 or ratio < 0.90:
        status = "fail"
    return {"segment_id": segment_id, "status": status, "psnr": psnr}
```

- [ ] **Step 4: Write JSON and Markdown reports**

Run: `python3 -m unittest tests.test_reconstruction_quality_gate -v`

Expected: PASS.

### Task 3: Validate On 0509 Existing Artifacts

**Files:**
- Use existing output artifacts under `outputs/reconstruction_precheck/`.

- [ ] **Step 1: Run the 0509 quality gate**

```bash
python3 tools/build_reconstruction_quality_gate.py \
  --image-pack-manifest outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_keyframe_image_pack/reconstruction_image_pack_manifest.json \
  --pose-prior gnss_0509=outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_carla_3dgs_handoff/gnss_constrained_rebuild_20260510/gnss_constraint_summary.json \
  --pose-prior fast_lio2_gnss_backend_0430=outputs/reconstruction_precheck/fast_lio2_gnss_backend_qiyu_20260430_20260512/fast_lio2_gnss_backend_metrics.json \
  --pose-prior lio_rf_gps_factor_0430=outputs/reconstruction_precheck/liorf_qiyu_20260430_full_20260512_112648/liorf_full_rtk_comparison.json \
  --segment-results-dir outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_gnss_constrained_lidar_segments_250m_fullroute_results_train80k \
  --output-dir outputs/reconstruction_precheck/qiyu_recon_82_core_20260509_151725_quality_gate_20260512
```

Expected: report marks `gnss_0509` accepted, 0430 priors excluded as source mismatches, and weak PSNR segments as optimization targets.

### Task 4: Roll Forward Decision

**Files:**
- No additional repo files unless the quality gate reveals a script defect.

- [ ] **Step 1: Report the next retraining target**

Use the Markdown report to identify:
- the accepted same-source pose prior,
- excluded cross-source priors,
- worst PSNR segments,
- whether mask overlay review is still required,
- whether the next step is same-source FAST-LIO2/LIO-RF rerun or segment retraining.

### Self-Review

- Spec coverage: A+B is covered by image/mask quality, segment quality, and pose-prior source gating.
- CARLA boundary: the plan keeps 3DGS as visual/research and does not claim CARLA 0.9.15 direct Gaussian import.
- Placeholder scan: implementation tasks name exact files, commands, and expected behavior.
- Runtime containment: generated reports stay under `outputs/`; heavy reconstruction artifacts remain outside Git.
