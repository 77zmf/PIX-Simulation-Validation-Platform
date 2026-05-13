from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "build_reconstruction_camera_diagnostics.py"

spec = importlib.util.spec_from_file_location("build_reconstruction_camera_diagnostics", TOOL_PATH)
assert spec and spec.loader
camera_diagnostics = importlib.util.module_from_spec(spec)
sys.modules["build_reconstruction_camera_diagnostics"] = camera_diagnostics
spec.loader.exec_module(camera_diagnostics)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ReconstructionCameraDiagnosticsTests(unittest.TestCase):
    def test_summarizes_camera_frame_quality_and_flags_sync_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame_index = root / "keyframe_image_index.csv"
            rows = [
                {
                    "topic": "/electronic_rearview_mirror/front_3mm/camera_image_jpeg",
                    "image_path": "/images/front_3mm/kf_00001.jpg",
                    "mask_path": "",
                    "dt_sec": "0.120",
                    "laplacian_variance": "3000.0",
                    "brightness_mean": "112.0",
                    "nearest_dynamic_distance_m": "5.0",
                    "dynamic_mask_candidate_count": "12",
                },
                {
                    "topic": "/electronic_rearview_mirror/front_3mm/camera_image_jpeg",
                    "image_path": "/images/front_3mm/kf_00002.jpg",
                    "mask_path": "",
                    "dt_sec": "0.020",
                    "laplacian_variance": "3200.0",
                    "brightness_mean": "113.0",
                    "nearest_dynamic_distance_m": "6.0",
                    "dynamic_mask_candidate_count": "10",
                },
                {
                    "topic": "/electronic_rearview_mirror/front_left/camera_image_jpeg",
                    "image_path": "/images/front_left/kf_00001.jpg",
                    "mask_path": "",
                    "dt_sec": "0.010",
                    "laplacian_variance": "2800.0",
                    "brightness_mean": "116.0",
                    "nearest_dynamic_distance_m": "4.0",
                    "dynamic_mask_candidate_count": "8",
                },
            ]
            with frame_index.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

            segment_manifest = root / "seg009" / "masked_lidar_gsplat_smoke_manifest.json"
            write_json(
                segment_manifest,
                {
                    "final_eval": {
                        "items": [
                            {"camera": "front_3mm", "image": "front_3mm/kf_00001.jpg", "psnr": 14.0},
                            {"camera": "front_3mm", "image": "front_3mm/kf_00002.jpg", "psnr": 14.4},
                            {"camera": "front_left", "image": "front_left/kf_00001.jpg", "psnr": 16.2},
                        ]
                    }
                },
            )

            report = camera_diagnostics.build_camera_diagnostics(
                frame_index_csv=frame_index,
                segment_manifests=[segment_manifest],
                output_dir=root / "out",
            )

            self.assertTrue((root / "out" / "reconstruction_camera_diagnostics.json").exists())
            self.assertTrue((root / "out" / "reconstruction_camera_diagnostics.md").exists())

        self.assertEqual(report["aggregate"]["worst_camera"], "front_3mm")
        front_3mm = report["segments"][0]["camera_summary"]["front_3mm"]
        self.assertEqual(front_3mm["stats"]["psnr"]["median"], 14.2)
        self.assertIn("low_psnr", front_3mm["warnings"])
        self.assertIn("sync_offset_review", front_3mm["warnings"])


if __name__ == "__main__":
    unittest.main()
