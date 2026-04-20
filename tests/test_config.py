from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.config import to_wsl_path


class ConfigTests(unittest.TestCase):
    def test_to_wsl_path_converts_windows_drive_paths(self) -> None:
        self.assertEqual(to_wsl_path(r"G:\maps\run_001"), "/mnt/g/maps/run_001")

    def test_to_wsl_path_keeps_posix_paths_native(self) -> None:
        self.assertEqual(to_wsl_path("/tmp/run_001"), "/tmp/run_001")


if __name__ == "__main__":
    unittest.main()
