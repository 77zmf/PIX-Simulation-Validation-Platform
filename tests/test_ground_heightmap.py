from __future__ import annotations

import importlib.util
import shutil
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "build_ground_heightmap.py"

spec = importlib.util.spec_from_file_location("build_ground_heightmap", TOOL_PATH)
assert spec and spec.loader
build_ground_heightmap = importlib.util.module_from_spec(spec)
sys.modules["build_ground_heightmap"] = build_ground_heightmap
spec.loader.exec_module(build_ground_heightmap)


class WorkspaceTempDir:
    def __enter__(self) -> Path:
        self.path = REPO_ROOT / ".tmp" / "test_ground_heightmap" / uuid.uuid4().hex
        self.path.mkdir(parents=True, exist_ok=False)
        return self.path

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class GroundHeightmapTests(unittest.TestCase):
    def test_build_heightmap_uses_cell_median(self) -> None:
        payload = build_ground_heightmap.build_heightmap(
            points=[
                (0.1, 0.1, 1.0),
                (0.2, 0.2, 3.0),
                (1.2, 0.1, 5.0),
                (10.0, 10.0, 99.0),
            ],
            cell_size=1.0,
            min_points_per_cell=2,
            height_stat="median",
        )

        self.assertEqual(payload["summary"]["input_points"], 4)
        self.assertEqual(payload["summary"]["raw_cells"], 3)
        self.assertEqual(payload["summary"]["populated_cells"], 1)
        self.assertEqual(payload["cells"][0]["z"], 2.0)
        self.assertEqual(payload["cells"][0]["count"], 2)

    def test_ascii_ply_reader_reads_xyz_fields(self) -> None:
        with WorkspaceTempDir() as tmp:
            path = tmp / "sample.ply"
            path.write_text(
                "ply\n"
                "format ascii 1.0\n"
                "element vertex 2\n"
                "property float x\n"
                "property float y\n"
                "property float z\n"
                "property uchar red\n"
                "property uchar green\n"
                "property uchar blue\n"
                "end_header\n"
                "1.0 2.0 3.0 10 20 30\n"
                "4.0 5.0 6.0 40 50 60\n",
                encoding="utf-8",
            )

            points = build_ground_heightmap.read_ascii_ply_points(path)

        self.assertEqual(points, [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)])

    def test_heightmap_csv_and_ply_are_written(self) -> None:
        with WorkspaceTempDir() as out:
            rows = [{"ix": 0, "iy": 0, "x": 0.5, "y": 0.5, "z": 1.0, "count": 3}]
            csv_path = out / "heightmap.csv"
            ply_path = out / "heightmap.ply"

            build_ground_heightmap.write_heightmap_csv(csv_path, rows)
            build_ground_heightmap.write_heightmap_ply(ply_path, rows)

            csv_text = csv_path.read_text(encoding="utf-8")
            ply_text = ply_path.read_text(encoding="utf-8")

        self.assertIn("ix,iy,x,y,z,count", csv_text)
        self.assertIn("element vertex 1", ply_text)

    def test_heightmap_png_is_written_without_matplotlib(self) -> None:
        with WorkspaceTempDir() as out:
            rows = [
                {"ix": 0, "iy": 0, "x": 0.5, "y": 0.5, "z": 1.0, "count": 3},
                {"ix": 1, "iy": 0, "x": 1.5, "y": 0.5, "z": 2.0, "count": 3},
            ]
            png_path = out / "heightmap.png"

            build_ground_heightmap.write_heightmap_png(png_path, rows)
            signature = png_path.read_bytes()[:8]

        self.assertEqual(signature, b"\x89PNG\r\n\x1a\n")

    def test_build_outputs_can_skip_png(self) -> None:
        with WorkspaceTempDir() as root:
            input_ply = root / "ground.ply"
            input_ply.write_text(
                "ply\n"
                "format ascii 1.0\n"
                "element vertex 2\n"
                "property float x\n"
                "property float y\n"
                "property float z\n"
                "end_header\n"
                "0.1 0.1 1.0\n"
                "0.2 0.2 2.0\n",
                encoding="utf-8",
            )

            report = build_ground_heightmap.build_outputs(
                input_ply=input_ply,
                output_dir=root / "heightmap",
                cell_size=1.0,
                min_points_per_cell=1,
                height_stat="median",
                render_png=False,
            )

            outputs = report["outputs"]
            csv_exists = Path(outputs["csv"]).exists()
            json_exists = Path(outputs["json"]).exists()
            ply_exists = Path(outputs["ply"]).exists()

        self.assertIn("csv", outputs)
        self.assertIn("json", outputs)
        self.assertIn("ply", outputs)
        self.assertNotIn("png", outputs)
        self.assertTrue(csv_exists)
        self.assertTrue(json_exists)
        self.assertTrue(ply_exists)


if __name__ == "__main__":
    unittest.main()
