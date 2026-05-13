from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "build_reconstruction_retrain_plan.py"

spec = importlib.util.spec_from_file_location("build_reconstruction_retrain_plan", TOOL_PATH)
assert spec and spec.loader
retrain_plan = importlib.util.module_from_spec(spec)
sys.modules["build_reconstruction_retrain_plan"] = retrain_plan
spec.loader.exec_module(retrain_plan)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ReconstructionRetrainPlanTests(unittest.TestCase):
    def test_builds_prioritized_commands_from_quality_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            segment_manifest = root / "seg002" / "masked_lidar_gsplat_smoke_manifest.json"
            write_json(
                segment_manifest,
                {
                    "segment_dir": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_002_0500m_0750m",
                    "map_ply": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_002_0500m_0750m/lidar_seed/map.ply",
                    "out_dir": "/data/pix/reconstruction/runs/qiyu/results/qiyu82_gnss_seg_002_0500m_0750m_balanced",
                },
            )
            review_manifest = root / "seg001" / "masked_lidar_gsplat_smoke_manifest.json"
            write_json(
                review_manifest,
                {
                    "segment_dir": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_001_0250m_0500m",
                    "map_ply": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_001_0250m_0500m/lidar_seed/map.ply",
                    "out_dir": "/data/pix/reconstruction/runs/qiyu/results/qiyu82_gnss_seg_001_0250m_0500m_balanced",
                },
            )
            quality_gate = root / "quality_gate.json"
            write_json(
                quality_gate,
                {
                    "status": "needs_optimization",
                    "segments": {
                        "items": [
                            {
                                "segment_id": "qiyu82_gnss_seg_001_0250m_0500m_balanced",
                                "manifest": str(review_manifest),
                                "status": "review",
                                "psnr": 17.0,
                                "frame_count": 24,
                                "image_colorized_ratio": 0.99,
                                "reasons": ["psnr_below_18"],
                            },
                            {
                                "segment_id": "qiyu82_gnss_seg_002_0500m_0750m_balanced",
                                "manifest": str(segment_manifest),
                                "status": "fail",
                                "psnr": 13.9,
                                "frame_count": 24,
                                "image_colorized_ratio": 0.96,
                                "reasons": ["psnr_below_15"],
                            },
                        ]
                    },
                },
            )

            output_dir = root / "plan"
            plan = retrain_plan.build_retrain_plan(
                quality_gate_json=quality_gate,
                output_dir=output_dir,
                remote_output_root=Path("/data/pix/reconstruction/runs/qiyu/retrain_20260512"),
                max_jobs=0,
            )
            self.assertTrue((output_dir / "reconstruction_retrain_plan.json").exists())
            self.assertTrue((output_dir / "run_reconstruction_retrain_jobs.sh").exists())
            self.assertTrue((output_dir / "reconstruction_retrain_plan.md").exists())

        self.assertEqual(plan["job_count"], 2)
        self.assertEqual(plan["jobs"][0]["segment_id"], "qiyu82_gnss_seg_002_0500m_0750m_balanced")
        self.assertEqual(plan["jobs"][0]["profile"], "psnr_retrain_high_detail")
        self.assertIn("--iterations 360", plan["jobs"][0]["command"])
        self.assertIn("--lr-means 0.0001", plan["jobs"][0]["command"])
        self.assertEqual(plan["jobs"][1]["profile"], "review_refine")

    def test_low_colorized_ratio_uses_coverage_repair_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            segment_manifest = root / "seg007" / "masked_lidar_gsplat_smoke_manifest.json"
            write_json(
                segment_manifest,
                {
                    "segment_dir": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_007_1750m_2000m",
                    "map_ply": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_007_1750m_2000m/lidar_seed/map.ply",
                    "out_dir": "/data/pix/reconstruction/runs/qiyu/results/qiyu82_gnss_seg_007_1750m_2000m_balanced",
                },
            )
            quality_gate = root / "quality_gate.json"
            write_json(
                quality_gate,
                {
                    "status": "needs_optimization",
                    "segments": {
                        "items": [
                            {
                                "segment_id": "qiyu82_gnss_seg_007_1750m_2000m_balanced",
                                "manifest": str(segment_manifest),
                                "status": "fail",
                                "psnr": 16.5,
                                "frame_count": 24,
                                "image_colorized_ratio": 0.80,
                                "reasons": ["colorized_ratio_below_0_90"],
                            }
                        ]
                    },
                },
            )

            plan = retrain_plan.build_retrain_plan(
                quality_gate_json=quality_gate,
                output_dir=root / "plan",
                remote_output_root=Path("/data/pix/reconstruction/runs/qiyu/retrain_20260512"),
                max_jobs=0,
            )

        self.assertEqual(plan["jobs"][0]["profile"], "coverage_repair")
        self.assertIn("--crop-margin-xy 120", plan["jobs"][0]["command"])
        self.assertIn("Rebuild segment inputs with wider camera coverage", plan["jobs"][0]["notes"][0])

    def test_low_review_psnr_uses_high_detail_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            segment_manifest = root / "seg014" / "masked_lidar_gsplat_smoke_manifest.json"
            write_json(
                segment_manifest,
                {
                    "segment_dir": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_014_3500m_3750m",
                    "map_ply": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_014_3500m_3750m/lidar_seed/map.ply",
                    "out_dir": "/data/pix/reconstruction/runs/qiyu/results/qiyu82_gnss_seg_014_3500m_3750m_balanced",
                },
            )
            quality_gate = root / "quality_gate.json"
            write_json(
                quality_gate,
                {
                    "status": "needs_optimization",
                    "segments": {
                        "items": [
                            {
                                "segment_id": "qiyu82_gnss_seg_014_3500m_3750m_balanced",
                                "manifest": str(segment_manifest),
                                "status": "review",
                                "psnr": 15.8,
                                "frame_count": 32,
                                "image_colorized_ratio": 1.0,
                                "reasons": ["psnr_below_18"],
                            }
                        ]
                    },
                },
            )

            plan = retrain_plan.build_retrain_plan(
                quality_gate_json=quality_gate,
                output_dir=root / "plan",
                remote_output_root=Path("/data/pix/reconstruction/runs/qiyu/retrain_20260512"),
                max_jobs=0,
            )

        self.assertEqual(plan["jobs"][0]["profile"], "psnr_retrain_high_detail")
        self.assertIn("--iterations 360", plan["jobs"][0]["command"])

    def test_camera_ablation_plan_builds_one_job_per_camera_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            segment_manifest = root / "seg009" / "masked_lidar_gsplat_smoke_manifest.json"
            write_json(
                segment_manifest,
                {
                    "segment_dir": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_009_2250m_2500m",
                    "map_ply": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_009_2250m_2500m/lidar_seed/map.ply",
                    "out_dir": "/data/pix/reconstruction/runs/qiyu/results/qiyu82_gnss_seg_009_2250m_2500m_balanced",
                },
            )
            quality_gate = root / "quality_gate.json"
            write_json(
                quality_gate,
                {
                    "status": "needs_optimization",
                    "segments": {
                        "items": [
                            {
                                "segment_id": "qiyu82_gnss_seg_009_2250m_2500m_balanced",
                                "manifest": str(segment_manifest),
                                "status": "fail",
                                "psnr": 14.8,
                                "frame_count": 36,
                                "image_colorized_ratio": 0.90,
                                "reasons": ["psnr_below_15"],
                                "camera_psnr_median": {
                                    "front_3mm": 14.2,
                                    "front_left": 16.4,
                                    "front_right": 14.8,
                                },
                            }
                        ]
                    },
                },
            )

            plan = retrain_plan.build_camera_ablation_plan(
                quality_gate_json=quality_gate,
                output_dir=root / "ablation",
                remote_output_root=Path("/data/pix/reconstruction/runs/qiyu/camera_ablation"),
                camera_sets=["front_left", "front_3mm", "front_left,front_right"],
                max_segments=1,
            )

        self.assertEqual(plan["job_count"], 3)
        self.assertEqual(plan["jobs"][0]["camera_set"], "front_left")
        self.assertEqual(plan["jobs"][0]["profile"], "camera_ablation")
        self.assertIn("--cameras front_left", plan["jobs"][0]["command"])
        self.assertIn("qiyu82_gnss_seg_009_2250m_2500m_balanced_front_left_camera_ablation", plan["jobs"][0]["out_dir"])

    def test_quality_filter_camera_policy_drops_weak_cameras(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            segment_manifest = root / "seg011" / "masked_lidar_gsplat_smoke_manifest.json"
            write_json(
                segment_manifest,
                {
                    "segment_dir": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_011_2750m_3000m",
                    "map_ply": "/data/pix/reconstruction/runs/qiyu/segments/qiyu82_gnss_seg_011_2750m_3000m/lidar_seed/map.ply",
                    "out_dir": "/data/pix/reconstruction/runs/qiyu/results/qiyu82_gnss_seg_011_2750m_3000m_balanced",
                },
            )
            quality_gate = root / "quality_gate.json"
            write_json(
                quality_gate,
                {
                    "status": "needs_optimization",
                    "segments": {
                        "items": [
                            {
                                "segment_id": "qiyu82_gnss_seg_011_2750m_3000m_balanced",
                                "manifest": str(segment_manifest),
                                "status": "fail",
                                "psnr": 14.9,
                                "frame_count": 36,
                                "image_colorized_ratio": 0.98,
                                "reasons": ["psnr_below_15"],
                                "camera_psnr_median": {
                                    "front_3mm": 14.3,
                                    "front_left": 16.2,
                                    "front_right": 14.8,
                                },
                            }
                        ]
                    },
                },
            )

            plan = retrain_plan.build_retrain_plan(
                quality_gate_json=quality_gate,
                output_dir=root / "plan",
                remote_output_root=Path("/data/pix/reconstruction/runs/qiyu/quality_filtered"),
                max_jobs=0,
                colorize_cameras="front_3mm,front_left,front_right",
                camera_policy="quality-filter",
                min_camera_psnr=15.0,
            )

        self.assertEqual(plan["camera_policy"], "quality-filter")
        self.assertEqual(plan["jobs"][0]["camera_set"], "front_left")
        self.assertEqual(plan["jobs"][0]["colorize_camera_set"], "front_3mm,front_left,front_right")
        self.assertIn("--cameras front_left", plan["jobs"][0]["command"])
        self.assertIn("--colorize-cameras front_3mm,front_left,front_right", plan["jobs"][0]["command"])


if __name__ == "__main__":
    unittest.main()
