from __future__ import annotations

import importlib.util
import shutil
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "build_reconstruction_handoff_manifest.py"

spec = importlib.util.spec_from_file_location("build_reconstruction_handoff_manifest", TOOL_PATH)
assert spec and spec.loader
build_reconstruction_handoff_manifest = importlib.util.module_from_spec(spec)
sys.modules["build_reconstruction_handoff_manifest"] = build_reconstruction_handoff_manifest
spec.loader.exec_module(build_reconstruction_handoff_manifest)


class WorkspaceTempDir:
    def __enter__(self) -> Path:
        self.path = REPO_ROOT / ".tmp" / "test_reconstruction_handoff_manifest" / uuid.uuid4().hex
        self.path.mkdir(parents=True, exist_ok=False)
        return self.path

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class ReconstructionHandoffManifestTests(unittest.TestCase):
    def test_manifest_collects_known_outputs_and_handoff_uri(self) -> None:
        with WorkspaceTempDir() as run_dir:
            (run_dir / "heightmap").mkdir()
            (run_dir / "site_proxy_ground_clean.ply").write_text("ply\n", encoding="utf-8")
            (run_dir / "heightmap" / "ground_heightmap.csv").write_text("ix,iy,x,y,z,count\n", encoding="utf-8")

            manifest = build_reconstruction_handoff_manifest.build_manifest(
                run_dir=run_dir,
                site_id="site_test",
                handoff_root_uri="smb://asset-share/site_test/center_run",
                hash_max_mb=1,
            )

        self.assertEqual(manifest["site_id"], "site_test")
        self.assertEqual(manifest["producer_host_role"], "home_windows_reconstruction_host")
        self.assertEqual(manifest["consumer_host_role"], "company_ubuntu_validation_host")
        self.assertEqual(manifest["file_count"], 2)
        roles = {item["role"] for item in manifest["files"]}
        self.assertEqual(roles, {"site_proxy_ground_clean", "ground_heightmap_csv"})
        self.assertTrue(all(item["handoff_uri"].startswith("smb://asset-share/site_test") for item in manifest["files"]))
        self.assertTrue(all(item["sha256"] for item in manifest["files"]))

    def test_markdown_manifest_is_written(self) -> None:
        with WorkspaceTempDir() as out:
            manifest = {
                "site_id": "site_test",
                "generated_at": "2026-04-19T00:00:00+00:00",
                "producer_host_role": "home_windows_reconstruction_host",
                "consumer_host_role": "company_ubuntu_validation_host",
                "run_dir": str(out),
                "handoff_root_uri": None,
                "handoff_policy": "policy",
                "files": [{"role": "ground", "relative_path": "ground.ply", "size_bytes": 4, "sha256": "abcd"}],
            }
            md_path = out / "handoff.md"

            build_reconstruction_handoff_manifest.write_markdown(md_path, manifest)
            text = md_path.read_text(encoding="utf-8")

        self.assertIn("Reconstruction Handoff Manifest", text)
        self.assertIn("company_ubuntu_validation_host", text)
        self.assertIn("ground.ply", text)


if __name__ == "__main__":
    unittest.main()
