from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.assets import inspect_asset_bundle, load_asset_bundle


class AssetManifestTests(unittest.TestCase):
    def test_site_bundle_contains_origin_and_tiles(self) -> None:
        bundle = load_asset_bundle("site_gy_qyhx_gsh20260302", REPO_ROOT, REPO_ROOT / "artifacts" / "assets")
        self.assertEqual(bundle.site_id, "gy_qyhx_gsh")
        self.assertEqual(bundle.metadata["pointcloud_tiles"], 3215)
        self.assertAlmostEqual(bundle.metadata["map_origin"]["latitude"], 26.648465)
        self.assertEqual(
            Path(bundle.maps["pointcloud_metadata"]["path"]),
            REPO_ROOT / "artifacts" / "assets" / "site_gy_qyhx_gsh20260302" / "pointcloud_map_metadata.yaml",
        )

    def test_inspect_asset_bundle_reports_tile_count_mismatch(self) -> None:
        asset_root = REPO_ROOT / ".tmp" / "test_asset_bundle_inspect"
        bundle_root = asset_root / "site_gy_qyhx_gsh20260302"
        shutil.rmtree(asset_root, ignore_errors=True)
        try:
            pointcloud_dir = bundle_root / "pointcloud_map.pcd"
            pointcloud_dir.mkdir(parents=True)
            (bundle_root / "lanelet2_map.osm").write_text("<osm/>", encoding="utf-8")
            (bundle_root / "map_projector_info.yaml").write_text(
                "projector_type: LocalCartesianUTM\n",
                encoding="utf-8",
            )
            (pointcloud_dir / "tile_a.pcd").write_text("pcd", encoding="utf-8")
            (pointcloud_dir / "tile_b.pcd").write_text("pcd", encoding="utf-8")
            (bundle_root / "pointcloud_map_metadata.yaml").write_text(
                "x_resolution: 20\n"
                "y_resolution: 20\n"
                "tile_a.pcd: [0, 0]\n"
                "tile_b.pcd: [20, 0]\n",
                encoding="utf-8",
            )

            bundle = load_asset_bundle("site_gy_qyhx_gsh20260302", REPO_ROOT, asset_root)
            inspection = inspect_asset_bundle(bundle)
        finally:
            shutil.rmtree(asset_root, ignore_errors=True)

        self.assertTrue(inspection["summary"]["all_required_present"])
        self.assertEqual(inspection["summary"]["pointcloud_tiles_actual"], 2)
        self.assertEqual(inspection["summary"]["pointcloud_metadata_tiles"], 2)
        self.assertFalse(inspection["summary"]["pointcloud_tiles_match"])
        self.assertFalse(inspection["summary"]["pointcloud_metadata_matches_manifest"])
        self.assertTrue(inspection["summary"]["pointcloud_metadata_matches_directory"])


if __name__ == "__main__":
    unittest.main()
