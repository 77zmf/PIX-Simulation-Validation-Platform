from __future__ import annotations

import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "reconstruct_pointcloud_map.py"

spec = importlib.util.spec_from_file_location("reconstruct_pointcloud_map", TOOL_PATH)
assert spec and spec.loader
reconstruct_pointcloud_map = importlib.util.module_from_spec(spec)
sys.modules["reconstruct_pointcloud_map"] = reconstruct_pointcloud_map
spec.loader.exec_module(reconstruct_pointcloud_map)


def _rgb_uint(red: int, green: int, blue: int) -> int:
    return (red << 16) | (green << 8) | blue


class PointcloudReconstructionToolTests(unittest.TestCase):
    def test_binary_pcd_reader_decodes_xyz_and_rgb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pcd_path = Path(tmp) / "sample.pcd"
            header = (
                "# .PCD v0.7 - Point Cloud Data file format\n"
                "VERSION 0.7\n"
                "FIELDS x y z rgb\n"
                "SIZE 4 4 4 4\n"
                "TYPE F F F F\n"
                "COUNT 1 1 1 1\n"
                "WIDTH 2\n"
                "HEIGHT 1\n"
                "VIEWPOINT 0 0 0 1 0 0 0\n"
                "POINTS 2\n"
                "DATA binary\n"
            ).encode("utf-8")
            payload = b"".join(
                [
                    struct.pack("<fffI", 1.0, 2.0, 3.0, _rgb_uint(10, 20, 30)),
                    struct.pack("<fffI", 4.0, 5.0, 6.0, _rgb_uint(40, 50, 60)),
                ]
            )
            pcd_path.write_bytes(header + payload)

            pcd_header = reconstruct_pointcloud_map.read_pcd_header(pcd_path)
            points = list(reconstruct_pointcloud_map.iter_pcd_points(pcd_path))

        self.assertEqual(pcd_header.points, 2)
        self.assertEqual(pcd_header.data, "binary")
        self.assertEqual(points[0], (1.0, 2.0, 3.0, 10, 20, 30))
        self.assertEqual(points[1], (4.0, 5.0, 6.0, 40, 50, 60))

    def test_write_ascii_ply_contains_vertex_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ply_path = Path(tmp) / "sample.ply"
            reconstruct_pointcloud_map.write_ascii_ply(
                ply_path,
                [
                    (1.0, 2.0, 3.0, 10, 20, 30),
                    (4.0, 5.0, 6.0, 40, 50, 60),
                ],
            )
            text = ply_path.read_text(encoding="utf-8")

        self.assertIn("element vertex 2", text)
        self.assertIn("1.000000 2.000000 3.000000 10 20 30", text)


if __name__ == "__main__":
    unittest.main()
