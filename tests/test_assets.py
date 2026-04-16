from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from textwrap import dedent


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.assets import inspect_asset_bundle, load_asset_bundle


class AssetManifestTests(unittest.TestCase):
    def test_site_bundle_contains_origin_and_tiles(self) -> None:
        bundle = load_asset_bundle("site_gy_qyhx_gsh20260302", REPO_ROOT, REPO_ROOT / "artifacts" / "assets")
        self.assertEqual(bundle.site_id, "gy_qyhx_gsh")
        self.assertEqual(bundle.metadata["pointcloud_tiles"], 3215)
        self.assertAlmostEqual(bundle.metadata["map_origin"]["latitude"], 26.648465)

    def test_builtin_bundle_integrity_passes(self) -> None:
        bundle = load_asset_bundle("carla_town01", REPO_ROOT, REPO_ROOT / "artifacts" / "assets")
        report = inspect_asset_bundle(bundle)
        self.assertTrue(report["summary"]["passed"])
        self.assertEqual(report["maps"]["lanelet2"]["selected"]["origin"], "primary")
        self.assertEqual(report["maps"]["lanelet2"]["selected"]["kind"], "virtual")
        self.assertEqual(report["summary"]["warnings"], [])

    def test_local_archive_bundle_can_use_fallback_lanelet_and_archive_members(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            repo_root = root / "repo"
            asset_root = root / "assets"
            extract_dir = asset_root / "site_bundle"
            repo_root.mkdir()
            asset_root.mkdir()
            extract_dir.mkdir()
            (repo_root / "fallback_lanelet2_map.osm").write_text("lanelet", encoding="utf-8")
            (extract_dir / "map_projector_info.yaml").write_text("projector: local\n", encoding="utf-8")
            (extract_dir / "pointcloud_map.pcd").mkdir()

            archive_path = repo_root / "site_bundle.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("site_bundle/lanelet2_map.osm", "lanelet")
                archive.writestr("site_bundle/map_projector_info.yaml", "projector")
                archive.writestr("site_bundle/pointcloud_map.pcd/tile_0001.pcd", "pcd")

            manifest_path = repo_root / "site_bundle.yaml"
            manifest_path.write_text(
                dedent(
                    """\
                    bundle_id: site_bundle
                    site_id: demo_site
                    description: Temporary site bundle for integrity tests
                    source:
                      type: local_archive
                      archive_path: ${REPO_ROOT}/site_bundle.zip
                      preferred_extract_dir: ${SIM_ASSET_ROOT}/site_bundle
                      archive_members:
                        - site_bundle/lanelet2_map.osm
                        - site_bundle/map_projector_info.yaml
                        - site_bundle/pointcloud_map.pcd/tile_0001.pcd
                    maps:
                      lanelet2:
                        path: ${SIM_ASSET_ROOT}/site_bundle/lanelet2_map.osm
                        fallback_repo_path: ${REPO_ROOT}/fallback_lanelet2_map.osm
                      projector:
                        path: ${SIM_ASSET_ROOT}/site_bundle/map_projector_info.yaml
                      pointcloud_dir:
                        path: ${SIM_ASSET_ROOT}/site_bundle/pointcloud_map.pcd
                    metadata:
                      tags:
                        - site_proxy
                    """
                ),
                encoding="utf-8",
            )

            bundle = load_asset_bundle(str(manifest_path), repo_root, asset_root)
            report = inspect_asset_bundle(bundle)
            self.assertTrue(report["summary"]["passed"])
            self.assertEqual(report["maps"]["lanelet2"]["selected"]["origin"], "fallback")
            self.assertTrue(report["source"]["archive"]["exists"])
            self.assertTrue(report["source"]["archive_members_ready"])
            self.assertEqual(report["summary"]["warnings"], [])


if __name__ == "__main__":
    unittest.main()
