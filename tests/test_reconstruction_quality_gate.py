from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "build_reconstruction_quality_gate.py"

spec = importlib.util.spec_from_file_location("build_reconstruction_quality_gate", TOOL_PATH)
assert spec and spec.loader
reconstruction_quality_gate = importlib.util.module_from_spec(spec)
sys.modules["build_reconstruction_quality_gate"] = reconstruction_quality_gate
spec.loader.exec_module(reconstruction_quality_gate)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ReconstructionQualityGateTests(unittest.TestCase):
    def test_quality_gate_excludes_cross_source_pose_and_flags_weak_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_bag = "/bags/qiyu_0509/rosbag2"
            image_manifest = root / "image_manifest.json"
            pose_same = root / "gnss_0509.json"
            pose_cross = root / "fast_lio2_0430.json"
            segments = root / "segments"
            output = root / "out"

            write_json(
                image_manifest,
                {
                    "source_bag": source_bag,
                    "keyframe_count": 10,
                    "expected_image_count": 60,
                    "image_count": 60,
                    "missing_image_count": 0,
                    "camera_topics": {
                        f"/camera/{index}/image": {"image_count": 10, "missing_count": 0}
                        for index in range(6)
                    },
                    "masking": {
                        "mask_job_count": 60,
                        "projected_box_count": 32,
                        "camera_projection_status": {
                            f"/camera/{index}/image": "projected" for index in range(6)
                        },
                    },
                },
            )
            write_json(
                pose_same,
                {
                    "source_bag": source_bag,
                    "status": "ready",
                    "route": {
                        "keyframe_count": 10,
                        "dense_odom_count": 100,
                        "constrained_route_length_m": 123.4,
                    },
                    "xy_similarity": {"residual_p95_m": 0.42, "residual_median_m": 0.12},
                    "z_affine": {"residual_rmse_m": 0.08},
                },
            )
            write_json(
                pose_cross,
                {
                    "source_bag": "/bags/qiyu_0430/rosbag2",
                    "mode": "fast_lio2_offline_gnss_backend_residual_constraint",
                    "backend_constraint": {
                        "xy_error_m": {"rmse": 0.04, "p95": 0.06},
                        "z_abs_error_m": {"rmse": 0.01, "p95": 0.02},
                    },
                },
            )
            write_json(
                segments / "qiyu82_seg_000_0000m_0250m_balanced" / "masked_lidar_gsplat_smoke_manifest.json",
                {
                    "frame_count": 24,
                    "iterations": 120,
                    "final_metric": {"psnr": 18.2, "loss": 0.01, "valid_pixels": 100000},
                    "point_stats": {"image_colorized_ratio": 0.98, "points_used": 80000},
                    "dynamic_mask_policy": "masked pixels are excluded from static/background Gaussian training loss",
                },
            )
            write_json(
                segments / "qiyu82_seg_001_0250m_0500m_balanced" / "masked_lidar_gsplat_smoke_manifest.json",
                {
                    "frame_count": 24,
                    "iterations": 120,
                    "final_metric": {"psnr": 14.2, "loss": 0.04, "valid_pixels": 80000},
                    "final_eval": {
                        "psnr_median": 14.8,
                        "psnr_min": 12.0,
                        "psnr_max": 19.0,
                        "by_camera_psnr_median": {
                            "front_3mm": 14.1,
                            "front_left": 17.5,
                            "front_right": 14.8,
                        },
                    },
                    "point_stats": {"image_colorized_ratio": 0.96, "points_used": 80000},
                    "dynamic_mask_policy": "masked pixels are excluded from static/background Gaussian training loss",
                },
            )

            report = reconstruction_quality_gate.build_quality_gate(
                image_pack_manifest=image_manifest,
                pose_prior_specs=[f"gnss_0509={pose_same}", f"fast_lio2_0430={pose_cross}"],
                segment_results_dir=segments,
                output_dir=output,
            )
            self.assertTrue((output / "reconstruction_quality_gate.json").exists())
            self.assertTrue((output / "reconstruction_quality_gate.md").exists())

        self.assertEqual(report["status"], "needs_optimization")
        self.assertEqual(report["image_pack"]["status"], "pass")
        self.assertEqual(report["pose_priors"]["accepted"][0]["name"], "gnss_0509")
        self.assertEqual(report["pose_priors"]["excluded"][0]["reason"], "source_bag_mismatch")
        self.assertEqual(report["segments"]["status_counts"]["pass"], 1)
        self.assertEqual(report["segments"]["status_counts"]["fail"], 1)
        self.assertEqual(report["segments"]["items"][1]["psnr_source"], "final_eval.psnr_median")
        self.assertEqual(report["segments"]["items"][1]["worst_camera"], "front_3mm")
        self.assertEqual(report["segments"]["camera_diagnostics"]["worst_camera"], "front_3mm")
        self.assertEqual(report["segments"]["camera_diagnostics"]["items"]["front_3mm"]["weak_count"], 1)
        self.assertEqual(report["next_actions"][0], "Review or retrain failed/review 3DGS segments before CARLA visual handoff.")

    def test_quality_gate_marks_clean_inputs_ready_for_retrain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_bag = "/bags/qiyu_0509/rosbag2"
            image_manifest = root / "image_manifest.json"
            pose_same = root / "gnss_0509.json"
            segments = root / "segments"
            output = root / "out"

            write_json(
                image_manifest,
                {
                    "source_bag": source_bag,
                    "keyframe_count": 10,
                    "expected_image_count": 60,
                    "image_count": 60,
                    "missing_image_count": 0,
                    "camera_topics": {
                        f"/camera/{index}/image": {"image_count": 10, "missing_count": 0}
                        for index in range(6)
                    },
                    "masking": {
                        "mask_job_count": 60,
                        "projected_box_count": 32,
                        "camera_projection_status": {
                            f"/camera/{index}/image": "projected" for index in range(6)
                        },
                    },
                },
            )
            write_json(
                pose_same,
                {
                    "source_bag": source_bag,
                    "status": "ready",
                    "route": {
                        "keyframe_count": 10,
                        "dense_odom_count": 100,
                        "constrained_route_length_m": 123.4,
                    },
                    "xy_similarity": {"residual_p95_m": 0.42, "residual_median_m": 0.12},
                    "z_affine": {"residual_rmse_m": 0.08},
                },
            )
            write_json(
                segments / "qiyu82_seg_000_0000m_0250m_balanced" / "masked_lidar_gsplat_smoke_manifest.json",
                {
                    "frame_count": 24,
                    "iterations": 120,
                    "final_metric": {"psnr": 18.2, "loss": 0.01, "valid_pixels": 100000},
                    "point_stats": {"image_colorized_ratio": 0.98, "points_used": 80000},
                    "dynamic_mask_policy": "masked pixels are excluded from static/background Gaussian training loss",
                },
            )

            report = reconstruction_quality_gate.build_quality_gate(
                image_pack_manifest=image_manifest,
                pose_prior_specs=[f"gnss_0509={pose_same}"],
                segment_results_dir=segments,
                output_dir=output,
            )

        self.assertEqual(report["status"], "ready_for_retrain")
        self.assertEqual(report["next_actions"], [])


if __name__ == "__main__":
    unittest.main()
