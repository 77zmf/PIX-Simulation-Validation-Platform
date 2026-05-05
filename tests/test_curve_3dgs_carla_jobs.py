from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "build_curve_3dgs_carla_jobs.py"

spec = importlib.util.spec_from_file_location("build_curve_3dgs_carla_jobs", TOOL_PATH)
assert spec and spec.loader
build_curve_3dgs_carla_jobs = importlib.util.module_from_spec(spec)
sys.modules["build_curve_3dgs_carla_jobs"] = build_curve_3dgs_carla_jobs
spec.loader.exec_module(build_curve_3dgs_carla_jobs)


SAMPLE_XODR = """<?xml version="1.0" standalone="yes"?>
<OpenDRIVE>
  <road name="lanelet_1" length="30.0" id="1" junction="-1">
    <planView>
      <geometry s="0.0" x="0.0" y="0.0" hdg="0.0" length="10.0"><line /></geometry>
      <geometry s="10.0" x="10.0" y="0.0" hdg="0.34906585" length="10.0"><line /></geometry>
      <geometry s="20.0" x="19.396926" y="3.420201" hdg="0.78539816" length="10.0"><line /></geometry>
    </planView>
  </road>
  <road name="lanelet_2" length="10.0" id="2" junction="-1">
    <planView>
      <geometry s="0.0" x="100.0" y="0.0" hdg="0.0" length="10.0"><line /></geometry>
    </planView>
  </road>
</OpenDRIVE>
"""


SAMPLE_METADATA = """rosbag2_bagfile_information:
  topics_with_message_count:
    - topic_metadata:
        name: /camera/front/image_jpeg
        type: sensor_msgs/msg/CompressedImage
      message_count: 42
    - topic_metadata:
        name: /camera/front/camera_info
        type: sensor_msgs/msg/CameraInfo
      message_count: 43
"""


SAMPLE_PREFLIGHT = """local_frame:
  source_frame: map
  origin_map_xyz_from_input_manifest:
    - -100.0
    - -200.0
    - 3.0
"""


class Curve3dgsCarlaJobsTests(unittest.TestCase):
    def test_detect_curve_candidates_from_polyline_xodr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xodr = root / "map.xodr"
            xodr.write_text(SAMPLE_XODR, encoding="utf-8")

            candidates = build_curve_3dgs_carla_jobs.detect_curve_candidates(
                xodr,
                min_cumulative_turn_deg=25.0,
                min_length_m=5.0,
            )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].road_id, "1")
        self.assertGreater(candidates[0].cumulative_abs_turn_deg, 40.0)

    def test_build_jobs_records_hybrid_carla_contract_and_camera_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xodr = root / "map.xodr"
            metadata = root / "metadata.yaml"
            preflight = root / "preflight.yaml"
            output_dir = root / "out"
            xodr.write_text(SAMPLE_XODR, encoding="utf-8")
            metadata.write_text(SAMPLE_METADATA, encoding="utf-8")
            preflight.write_text(SAMPLE_PREFLIGHT, encoding="utf-8")

            manifest = build_curve_3dgs_carla_jobs.build_jobs(
                xodr_path=xodr,
                source_bag=root / "bag",
                metadata_path=metadata,
                pointcloud_ply=root / "map.ply",
                trajectory_csv=None,
                import_manifest=None,
                import_preflight_report=preflight,
                output_dir=output_dir,
                min_cumulative_turn_deg=25.0,
                min_length_m=5.0,
                cluster_radius_m=30.0,
                crop_margin_m=35.0,
                carla_runtime="CARLA 0.9.15 / UE4.26",
                map_package="qiyu",
            )

        self.assertEqual(manifest["status"], "ready_for_frame_pose_extraction")
        self.assertEqual(manifest["summary"]["curve_cluster_count"], 1)
        self.assertEqual(manifest["summary"]["camera_image_message_count"], 42)
        self.assertIsNotNone(manifest["jobs"][0]["source_map_crop_bbox_xy_m"])
        self.assertEqual(manifest["jobs"][0]["carla_import_contract"]["drivable_import_asset"], "mesh_plus_opendrive")
        self.assertEqual(manifest["jobs"][0]["carla_import_contract"]["visual_research_asset"], "static_3dgs_or_nurec_layer")


if __name__ == "__main__":
    unittest.main()
