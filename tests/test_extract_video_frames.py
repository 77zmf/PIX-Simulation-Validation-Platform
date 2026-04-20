from __future__ import annotations

import importlib.util
import shutil
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "extract_video_frames.py"

spec = importlib.util.spec_from_file_location("extract_video_frames", TOOL_PATH)
assert spec and spec.loader
extract_video_frames = importlib.util.module_from_spec(spec)
sys.modules["extract_video_frames"] = extract_video_frames
spec.loader.exec_module(extract_video_frames)


class WorkspaceTempDir:
    def __enter__(self) -> Path:
        self.path = REPO_ROOT / ".tmp" / "test_extract_video_frames" / uuid.uuid4().hex
        self.path.mkdir(parents=True, exist_ok=False)
        return self.path

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class ExtractVideoFramesTests(unittest.TestCase):
    def test_missing_video_reports_error(self) -> None:
        with WorkspaceTempDir() as root:
            report = extract_video_frames.extract_frames(
                video_path=root / "missing.mp4",
                output_dir=root / "frames",
                fps=2.0,
                max_width=1920,
                overwrite=True,
            )

        self.assertFalse(report["passed"])
        self.assertIn("video not found", report["error"])


if __name__ == "__main__":
    unittest.main()
