from __future__ import annotations

import importlib.util
import shutil
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "run_pycolmap_sparse_smoke.py"

spec = importlib.util.spec_from_file_location("run_pycolmap_sparse_smoke", TOOL_PATH)
assert spec and spec.loader
run_pycolmap_sparse_smoke = importlib.util.module_from_spec(spec)
sys.modules["run_pycolmap_sparse_smoke"] = run_pycolmap_sparse_smoke
spec.loader.exec_module(run_pycolmap_sparse_smoke)


class WorkspaceTempDir:
    def __enter__(self) -> Path:
        self.path = REPO_ROOT / ".tmp" / "test_pycolmap_sparse_smoke" / uuid.uuid4().hex
        self.path.mkdir(parents=True, exist_ok=False)
        return self.path

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class PycolmapSparseSmokeTests(unittest.TestCase):
    def test_collect_images_filters_supported_extensions(self) -> None:
        with WorkspaceTempDir() as root:
            (root / "a.jpg").write_text("x", encoding="utf-8")
            (root / "b.PNG").write_text("x", encoding="utf-8")
            (root / "c.txt").write_text("x", encoding="utf-8")

            images = run_pycolmap_sparse_smoke.collect_images(root)

        self.assertEqual([path.name for path in images], ["a.jpg", "b.PNG"])

    def test_sparse_smoke_reports_insufficient_images(self) -> None:
        with WorkspaceTempDir() as root:
            image_dir = root / "images"
            output_dir = root / "out"
            image_dir.mkdir()

            report = run_pycolmap_sparse_smoke.run_sparse_smoke(
                image_dir=image_dir,
                output_dir=output_dir,
                min_images=8,
                matcher="exhaustive",
                device_name="auto",
                camera_mode_name="AUTO",
            )

        self.assertFalse(report["passed"])
        self.assertEqual(report["status"], "insufficient_images")
        self.assertEqual(report["image_count"], 0)


if __name__ == "__main__":
    unittest.main()
