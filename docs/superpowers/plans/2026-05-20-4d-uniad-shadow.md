# 4D-UniAD Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first repo-side `4D scene evidence pack -> UniAD-style shadow input pack -> reportable shadow comparison` path without changing stable control behavior.

**Architecture:** Add one focused adapter module that validates a 4D scene evidence pack and emits the existing UniAD-style shadow input contract. Runtime evidence folds the adapter summary into `run_result.json`, and reporting renders 4D input quality separately from UniAD shadow KPI results.

**Tech Stack:** Python 3 standard library, existing `simctl` config/reporting/runtime evidence helpers, YAML/JSON artifacts, `unittest`.

---

## File Structure

- Create: `src/simctl/four_d_uniad.py`
  - Owns schema validation, quality metric extraction, and `uniad_shadow_input_pack.json` generation.
  - No CARLA, ROS, or model inference dependency.
- Create: `tools/build_4d_uniad_shadow_input.py`
  - CLI wrapper around `simctl.four_d_uniad`.
  - Writes adapter artifacts under a provided output directory, usually `<run_dir>/runtime_verification/4d_uniad_shadow/`.
- Create: `tests/test_four_d_uniad.py`
  - Unit tests for valid conversion, missing required fields, and quality metrics.
- Modify: `src/simctl/runtime_evidence.py`
  - Discover adapter summaries under `runtime_verification/4d_uniad_shadow*/summary.json`.
  - Fold input-quality metrics into `runtime_evidence.metrics` with source `runtime_4d_uniad_adapter`.
- Modify: `src/simctl/reporting.py`
  - Add a `four_d_input_quality` aggregate summary.
  - Render a separate report section so 4D input quality is not confused with UniAD shadow planner KPIs.
- Modify: `tests/test_runtime_evidence.py`
  - Verify adapter artifacts are folded into runtime evidence.
- Modify: `tests/test_reporting.py`
  - Verify 4D input quality appears separately from `Shadow Comparison`.
- Modify: `tests/test_research_configs.py`
  - Verify the adapter contract stays aligned with `e2e_bevfusion_uniad_shadow`.
- Deliberately excluded from this plan: new scenario YAML, runbook publication, UniAD model runtime, and 4DGS training changes. Those require a separate approved plan after the adapter/report chain is green.

## Task 1: 4D-UniAD Adapter Module

**Files:**
- Create: `src/simctl/four_d_uniad.py`
- Test: `tests/test_four_d_uniad.py`

- [ ] **Step 1: Write the valid conversion test**

Append this test file:

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.four_d_uniad import build_uniad_shadow_input_pack


class FourDUniADAdapterTests(unittest.TestCase):
    def test_build_uniad_shadow_input_pack_from_complete_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            evidence = root / "4d_scene_evidence.json"
            output_dir = root / "runtime_verification" / "4d_uniad_shadow"
            evidence.write_text(
                json.dumps(
                    {
                        "schema_version": "2026q2-4d-uniad-shadow-v1",
                        "scene_id": "qiyu_4d_uniad_shadow_sample_001",
                        "source": {
                            "source_bag": "/data/pix/road_tests/qiyu_recon/sample",
                            "capture_manifest": "/data/pix/road_tests/qiyu_recon/sample/capture_manifest.json",
                            "calibration": "/data/pix/road_tests/qiyu_recon/sample/calibration",
                            "route_reference": "assets/routes/qiyu_sample.csv",
                        },
                        "time_window": {"start_sec": 0.0, "end_sec": 20.0, "tick_hz": 10},
                        "coordinate_frames": {
                            "target_frame": "map",
                            "ego_frame": "base_link",
                            "max_sensor_skew_ms": 82,
                        },
                        "scene_layers": {
                            "static_background": "static_background_manifest.json",
                            "dynamic_tracks": "dynamic_tracks.jsonl",
                            "occupancy": "occupancy_grid.jsonl",
                            "ego_history": "ego_history.jsonl",
                            "lane_graph": "lane_graph.json",
                        },
                        "quality": {
                            "dynamic_track_coverage": 0.91,
                            "occupancy_query_coverage": 0.88,
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = build_uniad_shadow_input_pack(evidence, output_dir)

            self.assertTrue(result["overall_passed"])
            self.assertEqual(result["scene_id"], "qiyu_4d_uniad_shadow_sample_001")
            self.assertEqual(result["metrics"]["time_alignment_passed"], 1.0)
            self.assertEqual(result["metrics"]["frame_alignment_passed"], 1.0)
            self.assertEqual(result["metrics"]["required_input_completeness"], 1.0)
            self.assertEqual(result["metrics"]["dynamic_track_coverage"], 0.91)
            self.assertEqual(result["metrics"]["occupancy_query_coverage"], 0.88)
            self.assertEqual(result["missing_required_inputs"], [])
            self.assertTrue((output_dir / "uniad_shadow_input_pack.json").exists())
            self.assertTrue((output_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_four_d_uniad -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'simctl.four_d_uniad'`.

- [ ] **Step 3: Implement the adapter module**

Create `src/simctl/four_d_uniad.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import dump_json, utc_now


SCHEMA_VERSION = "2026q2-4d-uniad-shadow-v1"
CONTRACT_VERSION = "2026q2-shadow-v1"
PROFILE_ID = "e2e_bevfusion_uniad_shadow"
REQUIRED_EVIDENCE_KEYS = [
    "schema_version",
    "scene_id",
    "source",
    "time_window",
    "coordinate_frames",
    "scene_layers",
]
REQUIRED_SOURCE_KEYS = ["source_bag", "capture_manifest", "calibration", "route_reference"]
REQUIRED_SCENE_LAYERS = ["dynamic_tracks", "occupancy", "ego_history", "lane_graph"]
UNIAD_REQUIRED_INPUTS = [
    "object_queries",
    "lane_graph_features",
    "occupancy_queries",
    "ego_history",
    "route_reference",
]


class FourDUniADValidationError(ValueError):
    def __init__(self, missing_required_inputs: list[str]) -> None:
        self.missing_required_inputs = missing_required_inputs
        super().__init__("Missing required 4D-UniAD inputs: " + ", ".join(missing_required_inputs))


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _missing_inputs(evidence: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_EVIDENCE_KEYS:
        if key not in evidence:
            missing.append(key)
    source = evidence.get("source") if isinstance(evidence.get("source"), dict) else {}
    for key in REQUIRED_SOURCE_KEYS:
        if key not in source:
            missing.append(f"source.{key}")
    layers = evidence.get("scene_layers") if isinstance(evidence.get("scene_layers"), dict) else {}
    for key in REQUIRED_SCENE_LAYERS:
        if key not in layers:
            missing.append(f"scene_layers.{key}")
    frames = evidence.get("coordinate_frames") if isinstance(evidence.get("coordinate_frames"), dict) else {}
    if frames.get("target_frame") != "map":
        missing.append("coordinate_frames.target_frame=map")
    return missing


def _quality_metrics(evidence: dict[str, Any], missing: list[str]) -> dict[str, float]:
    frames = evidence.get("coordinate_frames") if isinstance(evidence.get("coordinate_frames"), dict) else {}
    quality = evidence.get("quality") if isinstance(evidence.get("quality"), dict) else {}
    max_skew_ms = _as_float(frames.get("max_sensor_skew_ms"), 999999.0)
    return {
        "time_alignment_passed": 1.0 if max_skew_ms <= 100.0 else 0.0,
        "frame_alignment_passed": 1.0 if frames.get("target_frame") == "map" else 0.0,
        "required_input_completeness": 1.0 if not missing else 0.0,
        "dynamic_track_coverage": _as_float(quality.get("dynamic_track_coverage"), 0.0),
        "occupancy_query_coverage": _as_float(quality.get("occupancy_query_coverage"), 0.0),
    }


def _input_pack(evidence: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    layers = evidence.get("scene_layers") if isinstance(evidence.get("scene_layers"), dict) else {}
    source = evidence.get("source") if isinstance(evidence.get("source"), dict) else {}
    frames = evidence.get("coordinate_frames") if isinstance(evidence.get("coordinate_frames"), dict) else {}
    time_window = evidence.get("time_window") if isinstance(evidence.get("time_window"), dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "scene_id": str(evidence.get("scene_id", "")),
        "profile": PROFILE_ID,
        "contract_version": CONTRACT_VERSION,
        "target_frame": "map",
        "planning_tick_hz": int(time_window.get("tick_hz") or 10),
        "inputs": {
            "object_queries": str(layers.get("dynamic_tracks", "")),
            "lane_graph_features": str(layers.get("lane_graph", "")),
            "occupancy_queries": str(layers.get("occupancy", "")),
            "ego_history": str(layers.get("ego_history", "")),
            "route_reference": str(source.get("route_reference", "")),
        },
        "quality": {
            "max_perception_age_ms": int(_as_float(frames.get("max_sensor_skew_ms"), 0.0)),
            "time_alignment_passed": _as_float(frames.get("max_sensor_skew_ms"), 999999.0) <= 100.0,
            "frame_alignment_passed": frames.get("target_frame") == "map",
            "missing_required_inputs": missing,
        },
    }


def build_uniad_shadow_input_pack(evidence_path: Path, output_dir: Path) -> dict[str, Any]:
    evidence = _load_json(evidence_path)
    missing = _missing_inputs(evidence)
    metrics = _quality_metrics(evidence, missing)
    output_dir.mkdir(parents=True, exist_ok=True)
    pack = _input_pack(evidence, missing)
    input_pack_path = output_dir / "uniad_shadow_input_pack.json"
    dump_json(input_pack_path, pack)
    summary = {
        "kind": "4d_uniad_shadow_adapter",
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "scene_id": str(evidence.get("scene_id", "")),
        "profile": PROFILE_ID,
        "contract_version": CONTRACT_VERSION,
        "overall_passed": not missing and all(
            metrics[name] >= 1.0
            for name in ("time_alignment_passed", "frame_alignment_passed", "required_input_completeness")
        ),
        "missing_required_inputs": missing,
        "metrics": metrics,
        "artifacts": {
            "evidence": str(evidence_path),
            "uniad_shadow_input_pack": str(input_pack_path),
        },
    }
    dump_json(output_dir / "summary.json", summary)
    return summary
```

- [ ] **Step 4: Run the test and verify it passes**

Run:

```bash
python3 -m unittest tests.test_four_d_uniad -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/simctl/four_d_uniad.py tests/test_four_d_uniad.py
git commit -m "feat: add 4d uniad shadow adapter"
```

## Task 2: Adapter Failure Semantics

**Files:**
- Modify: `tests/test_four_d_uniad.py`
- Modify: `src/simctl/four_d_uniad.py`

- [ ] **Step 1: Add missing-field and bad-frame tests**

Insert these methods into `FourDUniADAdapterTests`:

```python
    def test_missing_required_inputs_are_reported_without_silent_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            evidence = root / "4d_scene_evidence.json"
            output_dir = root / "runtime_verification" / "4d_uniad_shadow"
            evidence.write_text(
                json.dumps(
                    {
                        "schema_version": "2026q2-4d-uniad-shadow-v1",
                        "scene_id": "qiyu_missing_lane_graph",
                        "source": {
                            "source_bag": "/data/pix/road_tests/qiyu_recon/sample",
                            "capture_manifest": "/data/pix/road_tests/qiyu_recon/sample/capture_manifest.json",
                            "calibration": "/data/pix/road_tests/qiyu_recon/sample/calibration",
                            "route_reference": "assets/routes/qiyu_sample.csv",
                        },
                        "time_window": {"start_sec": 0.0, "end_sec": 20.0, "tick_hz": 10},
                        "coordinate_frames": {
                            "target_frame": "map",
                            "ego_frame": "base_link",
                            "max_sensor_skew_ms": 120,
                        },
                        "scene_layers": {
                            "dynamic_tracks": "dynamic_tracks.jsonl",
                            "occupancy": "occupancy_grid.jsonl",
                            "ego_history": "ego_history.jsonl",
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = build_uniad_shadow_input_pack(evidence, output_dir)

            self.assertFalse(result["overall_passed"])
            self.assertIn("scene_layers.lane_graph", result["missing_required_inputs"])
            self.assertEqual(result["metrics"]["time_alignment_passed"], 0.0)
            self.assertEqual(result["metrics"]["required_input_completeness"], 0.0)
            input_pack = json.loads((output_dir / "uniad_shadow_input_pack.json").read_text(encoding="utf-8"))
            self.assertIn("scene_layers.lane_graph", input_pack["quality"]["missing_required_inputs"])
```

- [ ] **Step 2: Run the new test**

Run:

```bash
python3 -m unittest tests.test_four_d_uniad -v
```

Expected: PASS if Task 1 implementation already reports missing fields and skew. If it fails, the failure should name `missing_required_inputs` or `time_alignment_passed`.

- [ ] **Step 3: Keep `_input_pack` numeric conversion robust**

Confirm `_input_pack` in `src/simctl/four_d_uniad.py` uses this exact quality block:

```python
        "quality": {
            "max_perception_age_ms": int(_as_float(frames.get("max_sensor_skew_ms"), 0.0)),
            "time_alignment_passed": _as_float(frames.get("max_sensor_skew_ms"), 999999.0) <= 100.0,
            "frame_alignment_passed": frames.get("target_frame") == "map",
            "missing_required_inputs": missing,
        },
```

- [ ] **Step 4: Run the adapter tests again**

Run:

```bash
python3 -m unittest tests.test_four_d_uniad -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/simctl/four_d_uniad.py tests/test_four_d_uniad.py
git commit -m "test: lock 4d uniad adapter failure semantics"
```

## Task 3: Adapter CLI

**Files:**
- Create: `tools/build_4d_uniad_shadow_input.py`
- Modify: `tests/test_four_d_uniad.py`

- [ ] **Step 1: Add CLI smoke test**

Add imports at the top of `tests/test_four_d_uniad.py`:

```python
import subprocess
```

Add this method:

```python
    def test_cli_writes_summary_and_input_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            evidence = root / "4d_scene_evidence.json"
            output_dir = root / "runtime_verification" / "4d_uniad_shadow"
            evidence.write_text(
                json.dumps(
                    {
                        "schema_version": "2026q2-4d-uniad-shadow-v1",
                        "scene_id": "qiyu_cli_sample",
                        "source": {
                            "source_bag": "/data/pix/road_tests/qiyu_recon/sample",
                            "capture_manifest": "/data/pix/road_tests/qiyu_recon/sample/capture_manifest.json",
                            "calibration": "/data/pix/road_tests/qiyu_recon/sample/calibration",
                            "route_reference": "assets/routes/qiyu_sample.csv",
                        },
                        "time_window": {"start_sec": 0.0, "end_sec": 10.0, "tick_hz": 10},
                        "coordinate_frames": {
                            "target_frame": "map",
                            "ego_frame": "base_link",
                            "max_sensor_skew_ms": 65,
                        },
                        "scene_layers": {
                            "static_background": "static_background_manifest.json",
                            "dynamic_tracks": "dynamic_tracks.jsonl",
                            "occupancy": "occupancy_grid.jsonl",
                            "ego_history": "ego_history.jsonl",
                            "lane_graph": "lane_graph.json",
                        },
                    }
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "build_4d_uniad_shadow_input.py"),
                    "--evidence",
                    str(evidence),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output_dir / "summary.json").exists())
            self.assertTrue((output_dir / "uniad_shadow_input_pack.json").exists())
            self.assertIn('"overall_passed": true', completed.stdout)
```

- [ ] **Step 2: Run the CLI test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_four_d_uniad.FourDUniADAdapterTests.test_cli_writes_summary_and_input_pack -v
```

Expected: FAIL because `tools/build_4d_uniad_shadow_input.py` does not exist.

- [ ] **Step 3: Create the CLI wrapper**

Create `tools/build_4d_uniad_shadow_input.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.four_d_uniad import build_uniad_shadow_input_pack


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a UniAD-style shadow input pack from 4D scene evidence.")
    parser.add_argument("--evidence", required=True, help="Path to 4D scene evidence JSON")
    parser.add_argument("--output-dir", required=True, help="Directory for summary.json and uniad_shadow_input_pack.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_uniad_shadow_input_pack(Path(args.evidence), Path(args.output_dir))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("overall_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run adapter tests**

Run:

```bash
python3 -m unittest tests.test_four_d_uniad -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/build_4d_uniad_shadow_input.py tests/test_four_d_uniad.py
git commit -m "feat: add 4d uniad adapter cli"
```

## Task 4: Runtime Evidence Folding

**Files:**
- Modify: `src/simctl/runtime_evidence.py`
- Modify: `tests/test_runtime_evidence.py`

- [ ] **Step 1: Add runtime evidence test**

Append this method to `RuntimeEvidenceTests`:

```python
    def test_4d_uniad_adapter_summary_is_folded_into_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_4d_uniad"
            adapter_dir = run_dir / "runtime_verification" / "4d_uniad_shadow"
            adapter_dir.mkdir(parents=True)
            (adapter_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "kind": "4d_uniad_shadow_adapter",
                        "scene_id": "qiyu_4d_uniad_shadow_sample_001",
                        "profile": "e2e_bevfusion_uniad_shadow",
                        "overall_passed": True,
                        "missing_required_inputs": [],
                        "metrics": {
                            "time_alignment_passed": 1.0,
                            "frame_alignment_passed": 1.0,
                            "required_input_completeness": 1.0,
                            "dynamic_track_coverage": 0.91,
                            "occupancy_query_coverage": 0.88,
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = collect_runtime_evidence(run_dir, {"scenario_params": {"traffic_profile": {}}})

            self.assertEqual(summary["four_d_uniad_attempt_count"], 1)
            self.assertEqual(summary["successful_four_d_uniad_count"], 1)
            self.assertEqual(summary["metrics"]["time_alignment_passed"], 1.0)
            self.assertEqual(summary["metrics"]["dynamic_track_coverage"], 0.91)
            self.assertEqual(summary["metric_sources"]["occupancy_query_coverage"], "runtime_4d_uniad_adapter")
            self.assertEqual(summary["four_d_uniad_attempts"][0]["scene_id"], "qiyu_4d_uniad_shadow_sample_001")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_runtime_evidence.RuntimeEvidenceTests.test_4d_uniad_adapter_summary_is_folded_into_runtime_evidence -v
```

Expected: FAIL with missing `four_d_uniad_attempt_count`.

- [ ] **Step 3: Add artifact discovery and attempt parsing**

In `src/simctl/runtime_evidence.py`, add after `_camera_fiducial_artifacts`:

```python
def _four_d_uniad_artifacts(runtime_dir: Path) -> list[Path]:
    paths: set[Path] = set()
    paths.update(runtime_dir.glob("4d_uniad_shadow*/summary.json"))
    return sorted(paths)


def _four_d_uniad_attempt(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("kind") != "4d_uniad_shadow_adapter":
        return None
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return None
    return {
        "path": str(path),
        "scene_id": str(payload.get("scene_id") or "unknown"),
        "profile": str(payload.get("profile") or "unknown"),
        "overall_passed": bool(payload.get("overall_passed")),
        "missing_required_inputs": [
            str(item) for item in (payload.get("missing_required_inputs") or [])
        ],
        "metrics": {
            str(name): _as_float(value)
            for name, value in metrics.items()
            if isinstance(value, (int, float))
        },
    }
```

- [ ] **Step 4: Wire collection into `collect_runtime_evidence`**

In `collect_runtime_evidence`, add artifact list near the other artifact lists:

```python
    four_d_uniad_artifacts = _four_d_uniad_artifacts(runtime_dir) if runtime_dir.exists() else []
```

Add state lists near the other attempt lists:

```python
    four_d_uniad_attempts: list[dict[str, Any]] = []
    ignored_four_d_uniad: list[dict[str, Any]] = []
```

Add a parsing loop after camera fiducial parsing:

```python
    for path in four_d_uniad_artifacts:
        payload = _load_json(path)
        if payload is None:
            ignored_four_d_uniad.append({"path": str(path), "reason": "unreadable_json"})
            continue
        attempt = _four_d_uniad_attempt(path, payload)
        if attempt is None:
            ignored_four_d_uniad.append({"path": str(path), "reason": "not_4d_uniad_artifact"})
            continue
        four_d_uniad_attempts.append(attempt)
```

Add success list near other success lists:

```python
    successful_four_d_uniad = [item for item in four_d_uniad_attempts if item["overall_passed"]]
```

Add metric folding before the final return:

```python
    if four_d_uniad_attempts:
        latest_four_d_uniad = sorted(four_d_uniad_attempts, key=lambda item: str(item.get("path") or ""))[-1]
        for name, value in latest_four_d_uniad["metrics"].items():
            metrics[name] = value
            metric_sources[name] = "runtime_4d_uniad_adapter"
```

Add return fields:

```python
        "four_d_uniad_attempt_count": len(four_d_uniad_attempts),
        "successful_four_d_uniad_count": len(successful_four_d_uniad),
        "ignored_four_d_uniad_attempts": ignored_four_d_uniad,
        "four_d_uniad_attempts": four_d_uniad_attempts,
```

- [ ] **Step 5: Run the focused test**

Run:

```bash
python3 -m unittest tests.test_runtime_evidence.RuntimeEvidenceTests.test_4d_uniad_adapter_summary_is_folded_into_runtime_evidence -v
```

Expected: PASS.

- [ ] **Step 6: Run runtime evidence tests**

Run:

```bash
python3 -m unittest tests.test_runtime_evidence -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/simctl/runtime_evidence.py tests/test_runtime_evidence.py
git commit -m "feat: fold 4d uniad input quality into runtime evidence"
```

## Task 5: Report 4D Input Quality Separately

**Files:**
- Modify: `src/simctl/reporting.py`
- Modify: `tests/test_reporting.py`

- [ ] **Step 1: Add reporting helper fixture**

In `tests/test_reporting.py`, add this helper after `_shadow_run_result`:

```python
def _four_d_uniad_run_result() -> dict[str, object]:
    result = _shadow_run_result(
        run_id="run-4d-uniad",
        scenario_id="carla0915_public_road_bevfusion_uniad_unprotected_left",
        profile_id="e2e_bevfusion_uniad_shadow",
        gate_id="e2e_bevfusion_uniad_shadow_gate",
        kpis={
            "route_completion": 1.0,
            "collision_count": 0.0,
            "trajectory_divergence_m": 0.42,
            "min_ttc_sec": 2.1,
            "planner_disengagement_triggers": 0.0,
            "comfort_cost": 0.21,
            "time_alignment_passed": 1.0,
            "frame_alignment_passed": 1.0,
            "required_input_completeness": 1.0,
            "dynamic_track_coverage": 0.91,
            "occupancy_query_coverage": 0.88,
        },
        profile_specific=["comfort_cost"],
    )
    result["runtime_evidence"] = {
        "four_d_uniad_attempt_count": 1,
        "successful_four_d_uniad_count": 1,
        "four_d_uniad_attempts": [
            {
                "scene_id": "qiyu_4d_uniad_shadow_sample_001",
                "profile": "e2e_bevfusion_uniad_shadow",
                "overall_passed": True,
                "missing_required_inputs": [],
                "metrics": {
                    "time_alignment_passed": 1.0,
                    "frame_alignment_passed": 1.0,
                    "required_input_completeness": 1.0,
                    "dynamic_track_coverage": 0.91,
                    "occupancy_query_coverage": 0.88,
                },
            }
        ],
    }
    return result
```

- [ ] **Step 2: Add aggregate and markdown tests**

Add these tests to `ReportingTests`:

```python
    def test_aggregate_run_results_builds_4d_input_quality_summary(self) -> None:
        summary = aggregate_run_results([_four_d_uniad_run_result()])

        quality = summary["four_d_input_quality"]

        self.assertEqual(quality["run_count"], 1)
        self.assertEqual(quality["successful_runs"], 1)
        self.assertEqual(quality["metrics"]["dynamic_track_coverage"]["avg"], 0.91)
        self.assertEqual(quality["metrics"]["occupancy_query_coverage"]["avg"], 0.88)
        self.assertEqual(quality["gaps"], [])

    def test_render_markdown_includes_4d_input_quality_separate_from_shadow(self) -> None:
        summary = aggregate_run_results([_four_d_uniad_run_result()])

        markdown = render_markdown(summary)

        self.assertIn("## 4D Input Quality", markdown)
        self.assertIn("`dynamic_track_coverage`", markdown)
        self.assertIn("## Shadow Comparison", markdown)
        self.assertLess(markdown.index("## 4D Input Quality"), markdown.index("## Shadow Comparison"))
```

- [ ] **Step 3: Run focused reporting tests and verify failure**

Run:

```bash
python3 -m unittest tests.test_reporting.ReportingTests.test_aggregate_run_results_builds_4d_input_quality_summary tests.test_reporting.ReportingTests.test_render_markdown_includes_4d_input_quality_separate_from_shadow -v
```

Expected: FAIL with missing `four_d_input_quality`.

- [ ] **Step 4: Add aggregate helper in `src/simctl/reporting.py`**

Add near `summarize_shadow_comparison`:

```python
FOUR_D_INPUT_QUALITY_METRICS = [
    "time_alignment_passed",
    "frame_alignment_passed",
    "required_input_completeness",
    "dynamic_track_coverage",
    "occupancy_query_coverage",
]


def summarize_4d_input_quality(run_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    runs: list[dict[str, Any]] = []
    metric_values: dict[str, list[float]] = {name: [] for name in FOUR_D_INPUT_QUALITY_METRICS}
    gaps: list[dict[str, Any]] = []
    successful_runs = 0

    for result in run_results:
        runtime_evidence = result.get("runtime_evidence")
        if not isinstance(runtime_evidence, dict):
            continue
        attempts = runtime_evidence.get("four_d_uniad_attempts")
        if not isinstance(attempts, list) or not attempts:
            continue
        latest = attempts[-1]
        if not isinstance(latest, dict):
            continue
        metrics = latest.get("metrics")
        if not isinstance(metrics, dict):
            continue
        run_id = str(result.get("run_id", "unknown"))
        scene_id = str(latest.get("scene_id", "unknown"))
        missing_metrics: list[str] = []
        for metric in FOUR_D_INPUT_QUALITY_METRICS:
            value = metrics.get(metric)
            if isinstance(value, (int, float)):
                metric_values[metric].append(float(value))
            else:
                missing_metrics.append(metric)
        if latest.get("overall_passed"):
            successful_runs += 1
        runs.append(
            {
                "run_id": run_id,
                "scene_id": scene_id,
                "overall_passed": bool(latest.get("overall_passed")),
                "missing_required_inputs": latest.get("missing_required_inputs") or [],
            }
        )
        if missing_metrics or latest.get("missing_required_inputs"):
            gaps.append(
                {
                    "run_id": run_id,
                    "scene_id": scene_id,
                    "missing_metrics": missing_metrics,
                    "missing_required_inputs": latest.get("missing_required_inputs") or [],
                }
            )

    if not runs:
        return None

    return {
        "run_count": len(runs),
        "successful_runs": successful_runs,
        "metrics": {
            name: _metric_stats(values)
            for name, values in metric_values.items()
            if values
        },
        "runs": runs,
        "gaps": gaps,
    }
```

Update `aggregate_run_results` return payload:

```python
        "four_d_input_quality": summarize_4d_input_quality(run_results),
```

- [ ] **Step 5: Render markdown section**

In `render_markdown`, before the existing `Shadow Comparison` section, add:

```python
    four_d_quality = summary.get("four_d_input_quality")
    if four_d_quality:
        lines.extend(
            [
                "",
                "## 4D Input Quality",
                "",
                f"- Runs with 4D-UniAD adapter evidence: `{four_d_quality['run_count']}`",
                f"- Successful adapter runs: `{four_d_quality['successful_runs']}`",
                "",
                "| Metric | Avg | Min | Max | Count |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for metric, stats in sorted(four_d_quality.get("metrics", {}).items()):
            lines.append(
                f"| `{metric}` | {stats['avg']} | {stats['min']} | {stats['max']} | {stats['count']} |"
            )
        lines.extend(["", "### 4D Input Gaps", ""])
        gaps = list(four_d_quality.get("gaps", []))
        if not gaps:
            lines.append("- None")
        else:
            for gap in gaps:
                missing_inputs = ", ".join(f"`{item}`" for item in gap.get("missing_required_inputs", [])) or "`none`"
                missing_metrics = ", ".join(f"`{item}`" for item in gap.get("missing_metrics", [])) or "`none`"
                lines.append(
                    f"- `{gap['run_id']}` / `{gap['scene_id']}` missing inputs: {missing_inputs}; missing metrics: {missing_metrics}"
                )
```

If `render_markdown` currently builds `lines` lower in the function, insert this block after the run table section and before the `shadow_comparison = summary.get("shadow_comparison")` block.

- [ ] **Step 6: Run reporting tests**

Run:

```bash
python3 -m unittest tests.test_reporting -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/simctl/reporting.py tests/test_reporting.py
git commit -m "feat: report 4d input quality separately"
```

## Task 6: Contract Alignment Tests

**Files:**
- Modify: `tests/test_research_configs.py`

- [ ] **Step 1: Add a test tying 4D-UniAD schema to UniAD required inputs**

Add this method near the existing UniAD shadow tests:

```python
    def test_4d_uniad_shadow_adapter_contract_matches_uniad_required_inputs(self) -> None:
        profile = load_algorithm_profile("e2e_bevfusion_uniad_shadow", REPO_ROOT)
        contract = profile.payload["interface_contract"]
        minimal_inputs = contract["minimal_inputs"]

        required_inputs = {
            name
            for name, entry in minimal_inputs.items()
            if isinstance(entry, dict) and entry.get("required")
        }

        self.assertEqual(
            required_inputs,
            {
                "object_queries",
                "lane_graph_features",
                "occupancy_queries",
                "ego_history",
                "route_reference",
            },
        )
        self.assertTrue(contract["outputs"]["shadow_control"]["observation_only"])
```

- [ ] **Step 2: Run the focused config tests**

Run:

```bash
python3 -m unittest tests.test_research_configs.ResearchConfigTests.test_4d_uniad_shadow_adapter_contract_matches_uniad_required_inputs -v
```

Expected: PASS.

- [ ] **Step 3: Run the related research config tests**

Run:

```bash
python3 -m unittest tests.test_research_configs.ResearchConfigTests.test_uniad_shadow_scenario_loads tests.test_research_configs.ResearchConfigTests.test_uniad_shadow_profile_declares_shared_contract tests.test_research_configs.ResearchConfigTests.test_uniad_and_vadv2_shadow_gates_share_core_metrics tests.test_research_configs.ResearchConfigTests.test_4d_uniad_shadow_adapter_contract_matches_uniad_required_inputs -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_research_configs.py
git commit -m "test: pin 4d uniad shadow contract alignment"
```

## Task 7: End-to-End Local Artifact Test

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add finalize/report fixture test**

Add a test near the existing finalize runtime evidence tests in `tests/test_cli.py`:

```python
    def test_finalize_and_report_include_4d_uniad_input_quality(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_root = Path(tempdir) / "runs"
            run_dir = run_root / "run_4d_uniad"
            runtime_dir = run_dir / "runtime_verification" / "4d_uniad_shadow"
            runtime_dir.mkdir(parents=True)
            run_result = {
                "run_id": "run_4d_uniad",
                "scenario_id": "carla0915_public_road_bevfusion_uniad_unprotected_left",
                "scenario_path": str(REPO_ROOT / "scenarios" / "e2e" / "carla0915_bevfusion_uniad_unprotected_left.yaml"),
                "stack": "stable",
                "status": "launch_submitted",
                "kpis": {},
                "gate": {"gate_id": "e2e_bevfusion_uniad_shadow_gate", "passed": False, "violations": []},
                "scenario_params": {
                    "algorithm_profile": "e2e_bevfusion_uniad_shadow",
                    "traffic_profile": {"mode": "public_road_unprotected_left", "vehicles": 12, "pedestrians": 6},
                },
                "resolved_profiles": {
                    "algorithm": {
                        "profile_id": "e2e_bevfusion_uniad_shadow",
                        "interface_contract": {
                            "comparison_metrics": {
                                "common": [
                                    "route_completion",
                                    "collision_count",
                                    "trajectory_divergence_m",
                                    "min_ttc_sec",
                                    "planner_disengagement_triggers",
                                ],
                                "profile_specific": [
                                    "comfort_cost",
                                    "red_light_violations",
                                    "unprotected_left_yield_failures",
                                ],
                            }
                        },
                    }
                },
            }
            (run_dir / "run_result.json").write_text(json.dumps(run_result), encoding="utf-8")
            (runtime_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "kind": "4d_uniad_shadow_adapter",
                        "scene_id": "qiyu_4d_uniad_shadow_sample_001",
                        "profile": "e2e_bevfusion_uniad_shadow",
                        "overall_passed": True,
                        "missing_required_inputs": [],
                        "metrics": {
                            "time_alignment_passed": 1.0,
                            "frame_alignment_passed": 1.0,
                            "required_input_completeness": 1.0,
                            "dynamic_track_coverage": 0.91,
                            "occupancy_query_coverage": 0.88,
                            "route_completion": 1.0,
                            "collision_count": 0.0,
                            "trajectory_divergence_m": 0.42,
                            "min_ttc_sec": 2.1,
                            "planner_disengagement_triggers": 0.0,
                            "comfort_cost": 0.21,
                            "red_light_violations": 0.0,
                            "unprotected_left_yield_failures": 0.0,
                        },
                    }
                ),
                encoding="utf-8",
            )

            finalize_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "simctl.cli",
                    "--repo-root",
                    str(REPO_ROOT),
                    "finalize",
                    "--run-dir",
                    str(run_dir),
                ],
                cwd=str(REPO_ROOT),
                env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
                capture_output=True,
                text=True,
            )
            self.assertEqual(finalize_completed.returncode, 0, finalize_completed.stderr)

            report_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "simctl.cli",
                    "--repo-root",
                    str(REPO_ROOT),
                    "report",
                    "--run-root",
                    str(run_root),
                ],
                cwd=str(REPO_ROOT),
                env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
                capture_output=True,
                text=True,
            )
            self.assertEqual(report_completed.returncode, 0, report_completed.stderr)

            summary = json.loads((run_root / "report" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["four_d_input_quality"]["successful_runs"], 1)
            report_md = (run_root / "report" / "report.md").read_text(encoding="utf-8")
            self.assertIn("## 4D Input Quality", report_md)
            self.assertIn("## Shadow Comparison", report_md)
```

If `tests/test_cli.py` lacks imports, add:

```python
import os
import subprocess
```

- [ ] **Step 2: Run the focused CLI test**

Run:

```bash
python3 -m unittest tests.test_cli.CliTests.test_finalize_and_report_include_4d_uniad_input_quality -v
```

Expected: PASS after Tasks 4 and 5 are complete.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: verify 4d uniad finalize report chain"
```

## Task 8: Verification Batch

**Files:**
- No file changes expected.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
python3 -m unittest tests.test_four_d_uniad tests.test_runtime_evidence tests.test_reporting -v
```

Expected: PASS.

- [ ] **Step 2: Run focused research config and CLI tests**

Run:

```bash
python3 -m unittest \
  tests.test_research_configs.ResearchConfigTests.test_uniad_shadow_scenario_loads \
  tests.test_research_configs.ResearchConfigTests.test_uniad_shadow_profile_declares_shared_contract \
  tests.test_research_configs.ResearchConfigTests.test_uniad_and_vadv2_shadow_gates_share_core_metrics \
  tests.test_research_configs.ResearchConfigTests.test_4d_uniad_shadow_adapter_contract_matches_uniad_required_inputs \
  tests.test_cli.CliTests.test_finalize_and_report_include_4d_uniad_input_quality \
  -v
```

Expected: PASS.

- [ ] **Step 3: Confirm Git scope**

Run:

```bash
git status --short --branch
git diff --stat HEAD~5..HEAD
```

Expected: only the planned implementation files appear in the new commits. Pre-existing dirty files may still appear in worktree status and must not be staged unless they are part of this implementation.

## Task 9: Remote Host Handoff Commands

**Files:**
- Modify: `docs/superpowers/specs/2026-05-20-4d-uniad-shadow-design.md` only if the implemented command differs from the spec.

- [ ] **Step 1: Prepare adapter command for host use**

Use this template after a 4D evidence JSON exists:

```bash
RUN_ROOT=/data/pix/sim_runs/4d_uniad_shadow_probe
RUN_DIR="${RUN_ROOT}/<run_id>"

python3 tools/build_4d_uniad_shadow_input.py \
  --evidence /data/pix/reconstruction/runs/<case>/4d_scene_evidence.json \
  --output-dir "${RUN_DIR}/runtime_verification/4d_uniad_shadow"
```

Expected: writes:

```text
${RUN_DIR}/runtime_verification/4d_uniad_shadow/summary.json
${RUN_DIR}/runtime_verification/4d_uniad_shadow/uniad_shadow_input_pack.json
```

- [ ] **Step 2: Run existing UniAD shadow chain**

Run on the company Ubuntu host:

```bash
simctl run \
  --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml \
  --run-root "${RUN_ROOT}" \
  --slot stable-slot-01 \
  --execute
```

Expected: a run directory with `run_result.json`. This is still shadow evidence, not stable acceptance.

- [ ] **Step 3: Finalize and report**

Run:

```bash
simctl validate \
  --run-dir "${RUN_DIR}" \
  --execute \
  --finalize \
  --report
```

Expected: `run_result.json` includes `runtime_evidence.four_d_uniad_attempt_count`, and report includes both `4D Input Quality` and `Shadow Comparison`.

- [ ] **Step 4: Document actual remote artifact paths**

If remote execution is performed, add the exact `RUN_ROOT`, `RUN_DIR`, `summary.json`, and `report.md` paths to the final handoff message. Do not claim host success unless those files exist.
