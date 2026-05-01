from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = REPO_ROOT / "ops" / "runtime_probes" / "carla_custom_map_load_probe.py"

spec = importlib.util.spec_from_file_location("carla_custom_map_load_probe", PROBE_PATH)
carla_custom_map_load_probe = importlib.util.module_from_spec(spec)
sys.modules["carla_custom_map_load_probe"] = carla_custom_map_load_probe
assert spec.loader is not None
spec.loader.exec_module(carla_custom_map_load_probe)


class CarlaCustomMapLoadProbeTests(unittest.TestCase):
    def test_map_matches_full_game_path_and_loaded_name_tail(self) -> None:
        requested = "/Game/qiyu_loop_20260430_105120/Maps/qiyu_loop_20260430_105120/qiyu_loop_20260430_105120"
        loaded = "qiyu_loop_20260430_105120/Maps/qiyu_loop_20260430_105120/qiyu_loop_20260430_105120"

        self.assertTrue(carla_custom_map_load_probe.map_matches(requested, requested))
        self.assertTrue(carla_custom_map_load_probe.map_matches(loaded, requested))
        self.assertFalse(carla_custom_map_load_probe.map_matches("/Game/Carla/Maps/Town01", requested))

    def test_build_metrics_and_overall_passed_include_alignment_threshold(self) -> None:
        metrics = carla_custom_map_load_probe.build_metrics(
            available=True,
            load_passed=True,
            current_match=True,
            actor_count=1,
            expected_alignment_iou=0.9504276622995398,
        )

        self.assertEqual(metrics["carla_custom_map_available"], 1.0)
        self.assertEqual(metrics["carla_custom_map_load_passed"], 1.0)
        self.assertEqual(metrics["carla_custom_map_actor_count"], 1.0)
        self.assertTrue(
            carla_custom_map_load_probe.overall_passed(
                metrics,
                min_actors=1,
                min_alignment_iou=0.90,
            )
        )
        self.assertFalse(
            carla_custom_map_load_probe.overall_passed(
                metrics,
                min_actors=2,
                min_alignment_iou=0.90,
            )
        )

    def test_write_payload_uses_metric_probe_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir)
            output = carla_custom_map_load_probe.write_payload(
                run_dir,
                {
                    "kind": carla_custom_map_load_probe.PROBE_ID,
                    "profile": "unit",
                    "overall_passed": True,
                    "metrics": {"carla_custom_map_load_passed": 1.0},
                },
            )

            self.assertTrue(output.exists())
            self.assertEqual(output.parent.name, carla_custom_map_load_probe.PROBE_ID)

    def test_available_maps_retry_recovers_after_first_timeout(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls = 0

            def get_available_maps(self) -> list[str]:
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("not ready")
                return ["/Game/qiyu_loop_20260430_105120/Maps/qiyu_loop_20260430_105120/qiyu_loop_20260430_105120"]

        client = FakeClient()
        maps, errors = carla_custom_map_load_probe.get_available_maps_with_retries(
            lambda: client,
            attempts=2,
            retry_sleep_sec=0.0,
        )

        self.assertEqual(len(errors), 1)
        self.assertEqual(client.calls, 2)
        self.assertTrue(maps)


if __name__ == "__main__":
    unittest.main()
