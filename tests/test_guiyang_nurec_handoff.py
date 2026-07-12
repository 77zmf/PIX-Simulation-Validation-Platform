from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.assets import inspect_asset_bundle, load_asset_bundle
from simctl.config import load_yaml
from simctl.evaluation import evaluate_metrics, load_kpi_gate
from simctl.scenarios import load_scenario


class GuiyangNurecHandoffTests(unittest.TestCase):
    def test_asset_manifest_preserves_traceability_and_carla_boundary(self) -> None:
        bundle = load_asset_bundle("nvidia_guiyang_nurec_6cam_lidar_20k", REPO_ROOT)
        status = bundle.metadata["status"]
        source_lock = bundle.metadata["source_lock"]
        carla_contract = bundle.metadata["carla_import_contract"]

        self.assertEqual(bundle.site_id, "guiyang_nurec_6cam_lidar_20260709")
        self.assertEqual(status["frame_count"], 200)
        self.assertEqual(status["camera_count"], 6)
        self.assertEqual(status["pose_count"], 200)
        self.assertEqual(status["handoff_file_count"], 17)
        self.assertEqual(status["sha256_coverage_ratio"], 1.0)
        self.assertTrue(bundle.source["artifact_sha256_inventory"].endswith("/ARTIFACT_SHA256SUMS"))
        self.assertTrue(bundle.source["handoff_package_sha256_inventory"].endswith("/SHA256SUMS"))
        self.assertFalse(status["quality_metrics_present"])
        self.assertFalse(status["source_lock_clean"])
        self.assertFalse(source_lock["clean"])
        self.assertEqual(source_lock["head"], "24fc57154741f40ef2133121aa8a77de3aa81c65")
        self.assertEqual(carla_contract["decision"], "do_not_import_as_native_carla0915_map")
        self.assertEqual(
            bundle.maps["gaussian_merged_ply"]["sha256"],
            "83537af5abf65706a7464b6bc3b82a4cf0ead7b38b5a3683c8fa52b0eee8f05a",
        )

        inspection = inspect_asset_bundle(bundle)
        self.assertTrue(inspection["summary"]["all_required_present"])
        self.assertTrue(all(check["status"] == "virtual" for check in inspection["checks"]))

    def test_shadow_scenario_exposes_current_promotion_blockers(self) -> None:
        scenario_path = "scenarios/l2/reconstruction_guiyang_nurec_6cam_lidar_shadow_handoff.yaml"
        scenario = load_scenario(scenario_path, REPO_ROOT)
        payload = load_yaml(REPO_ROOT / scenario_path)
        gate = load_kpi_gate("reconstruction_nurec_visual_handoff_gate", REPO_ROOT)

        self.assertEqual(scenario.asset_bundle, "nvidia_guiyang_nurec_6cam_lidar_20k")
        self.assertEqual(scenario.kpi_gate, "reconstruction_nurec_visual_handoff_gate")
        self.assertEqual(payload["execution"]["mode"], "external")
        self.assertIn("shadow_comparison", scenario.labels)
        self.assertIn("blocked_quality_metrics", scenario.labels)
        self.assertIn("blocked_source_lock", scenario.labels)
        self.assertIn("does not imply CARLA 0.9.15 map acceptance", payload["metadata"]["acceptance_boundary"])
        self.assertEqual(gate.metrics["nurec_handoff_file_count"]["value"], 17)
        self.assertEqual(gate.metrics["nurec_camera_count"]["value"], 6)
        self.assertIn("nurec_quality_metrics_present", gate.metrics)
        self.assertIn("nurec_source_lock_clean", gate.metrics)

    def test_current_handoff_cannot_be_misreported_as_promoted(self) -> None:
        gate = load_kpi_gate("reconstruction_nurec_visual_handoff_gate", REPO_ROOT)
        result = evaluate_metrics(
            {
                "nurec_handoff_manifest_present": 1,
                "nurec_handoff_file_count": 17,
                "nurec_sha256_coverage_ratio": 1.0,
                "nurec_source_trace_complete": 1,
                "nurec_camera_count": 6,
                "nurec_pose_count": 200,
                "nurec_checkpoint_20k_present": 1,
                "nurec_visual_preview_present": 1,
                "nurec_quality_metrics_present": 0,
                "nurec_source_lock_clean": 0,
                "nurec_carla_import_boundary_declared": 1,
            },
            gate,
        )

        self.assertFalse(result["passed"])
        self.assertEqual(
            {violation["metric"] for violation in result["violations"]},
            {"nurec_quality_metrics_present", "nurec_source_lock_clean"},
        )


if __name__ == "__main__":
    unittest.main()
