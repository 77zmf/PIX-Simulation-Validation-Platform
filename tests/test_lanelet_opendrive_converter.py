from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl import lanelet_opendrive
from simctl.cli import main


class LaneletOpenDriveConverterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = REPO_ROOT / ".tmp" / "test_lanelet_opendrive_converter"
        shutil.rmtree(self.tmp_root, ignore_errors=True)
        self.tmp_root.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _write_minimal_lanelet_map(self) -> tuple[Path, Path]:
        lanelet_path = self.tmp_root / "lanelet2_map.osm"
        lanelet_path.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1"><tag k="local_x" v="0.0"/><tag k="local_y" v="0.0"/><tag k="ele" v="100.0"/></node>
  <node id="2"><tag k="local_x" v="20.0"/><tag k="local_y" v="0.0"/><tag k="ele" v="100.2"/></node>
  <node id="3"><tag k="local_x" v="0.0"/><tag k="local_y" v="-3.5"/><tag k="ele" v="99.9"/></node>
  <node id="4"><tag k="local_x" v="20.0"/><tag k="local_y" v="-3.5"/><tag k="ele" v="100.1"/></node>
  <way id="10">
    <nd ref="1"/>
    <nd ref="2"/>
    <tag k="type" v="line_thin"/>
  </way>
  <way id="11">
    <nd ref="3"/>
    <nd ref="4"/>
    <tag k="type" v="line_thin"/>
  </way>
  <relation id="100">
    <member type="way" ref="10" role="left"/>
    <member type="way" ref="11" role="right"/>
    <tag k="type" v="lanelet"/>
    <tag k="subtype" v="road"/>
    <tag k="speed_limit" v="40"/>
    <tag k="one_way" v="yes"/>
  </relation>
</osm>
""",
            encoding="utf-8",
        )

        projector_path = self.tmp_root / "map_projector_info.yaml"
        projector_path.write_text(
            "projector_type: LocalCartesianUTM\n"
            "vertical_datum: WGS84\n"
            "map_origin:\n"
            "  latitude: 26.648465\n"
            "  longitude: 106.620033\n"
            "  altitude: 1263.969482005\n",
            encoding="utf-8",
        )
        return lanelet_path, projector_path

    def test_converter_writes_opendrive_and_reports_counts(self) -> None:
        lanelet_path, projector_path = self._write_minimal_lanelet_map()

        result = lanelet_opendrive.convert_lanelet_to_opendrive(
            lanelet_path=lanelet_path,
            projector_path=projector_path,
            output_dir=self.tmp_root / "out",
            map_name="unit_test_site",
            reference_line_mode="left",
            lane_type="driving",
        )

        xodr_path = Path(result["xodr"])
        json_path = Path(result["json"])
        markdown_path = Path(result["markdown"])
        self.assertTrue(xodr_path.exists())
        self.assertTrue(json_path.exists())
        self.assertTrue(markdown_path.exists())

        report = result["report"]
        self.assertEqual(report["input_counts"]["nodes"], 4)
        self.assertEqual(report["input_counts"]["ways"], 2)
        self.assertEqual(report["input_counts"]["lanelet_relations"], 1)
        self.assertEqual(report["output_counts"]["roads"], 1)
        self.assertEqual(report["output_counts"]["skipped_lanelets"], 0)
        self.assertAlmostEqual(report["roads_sample"][0]["lane_width_m"], 3.5)

        root = ET.parse(xodr_path).getroot()
        self.assertEqual(root.tag, "OpenDRIVE")
        road = root.find("road")
        self.assertIsNotNone(road)
        assert road is not None
        self.assertEqual(road.attrib["name"], "lanelet_100")
        self.assertEqual(road.attrib["id"], "100")
        self.assertEqual(road.find("type/speed").attrib["max"], "40")
        self.assertIsNotNone(road.find("lanes/laneSection/right/lane[@id='-1']"))
        self.assertIn("+lat_0=26.648465", root.find("header/geoReference").text)

    def test_simctl_lanelet_to_opendrive_command(self) -> None:
        lanelet_path, projector_path = self._write_minimal_lanelet_map()
        stream = io.StringIO()

        with redirect_stdout(stream):
            rc = main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "lanelet-to-opendrive",
                    "--lanelet",
                    str(lanelet_path),
                    "--projector",
                    str(projector_path),
                    "--output-dir",
                    str(self.tmp_root / "cli_out"),
                    "--map-name",
                    "unit_test_cli_site",
                    "--max-lanelets",
                    "1",
                ]
            )

        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["summary"], {"roads": 1, "skipped_lanelets": 0})
        self.assertTrue(Path(payload["xodr"]).exists())


if __name__ == "__main__":
    unittest.main()
