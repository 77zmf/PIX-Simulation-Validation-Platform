from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.assets import load_asset_bundle


class AssetManifestTests(unittest.TestCase):
    def test_site_bundle_contains_origin_and_tiles(self) -> None:
        bundle = load_asset_bundle("site_gy_qyhx_gsh20260302", REPO_ROOT, REPO_ROOT / "artifacts" / "assets")
        self.assertEqual(bundle.site_id, "gy_qyhx_gsh")
        self.assertEqual(bundle.metadata["pointcloud_tiles"], 3215)
        self.assertAlmostEqual(bundle.metadata["map_origin"]["latitude"], 26.648465)


if __name__ == "__main__":
    unittest.main()
