from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_PATH = REPO_ROOT / "infra" / "ubuntu" / "stable_run_preflight.py"

spec = importlib.util.spec_from_file_location("stable_run_preflight", PREFLIGHT_PATH)
stable_run_preflight = importlib.util.module_from_spec(spec)
sys.modules["stable_run_preflight"] = stable_run_preflight
assert spec.loader is not None
spec.loader.exec_module(stable_run_preflight)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# test\n", encoding="utf-8")


class StableRunPreflightTests(unittest.TestCase):
    def _args(self, root: Path, run_dir: Path) -> argparse.Namespace:
        carla_root = root / "CARLA_0.9.15"
        autoware_ws = root / "autoware"
        bridge_ws = root / "bridge"
        underlay_ws = root / "underlay"
        map_path = root / "map"
        map_path.mkdir(parents=True)
        _touch(carla_root / "CarlaUE4.sh")
        _touch(autoware_ws / "install" / "setup.bash")
        _touch(bridge_ws / "install" / "setup.bash")
        _touch(underlay_ws / "install" / "setup.bash")
        sensor_mapping = root / "robobus117th_sensor_mapping.yaml"
        sensor_calibration = root / "robobus117th_sensor_kit_calibration.yaml"
        objects_definition = root / "robobus117th_objects.json"
        _touch(sensor_mapping)
        _touch(sensor_calibration)
        objects_definition.write_text("{}", encoding="utf-8")
        return argparse.Namespace(
            run_dir=str(run_dir),
            scenario=str(root / "scenario.yaml"),
            carla_root=str(carla_root),
            carla_map="Town01",
            autoware_enabled="true",
            autoware_ws=str(autoware_ws),
            autoware_bridge_ws=str(bridge_ws),
            autoware_underlay_ws=str(underlay_ws),
            autoware_map_path=str(map_path),
            sensor_mapping_file=str(sensor_mapping),
            sensor_kit_calibration_file=str(sensor_calibration),
            objects_definition_file=str(objects_definition),
            carla_port="0",
            traffic_manager_port="0",
            sumo_enabled="false",
            sumo_traci_port="0",
            sumo_binary="sumo",
            sumo_config_file="",
            sumo_cosim_script="",
            min_disk_free_gb=0.0,
            min_mem_available_gb=0.0,
            min_swap_free_gb=0.0,
            strict="true",
        )

    def test_preflight_writes_report_and_host_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "run"
            args = self._args(root, run_dir)

            report = stable_run_preflight.run_preflight(args)

            self.assertTrue(report["passed"])
            self.assertTrue((run_dir / "host_bom.json").exists())
            self.assertTrue((run_dir / "preflight_report.json").exists())
            saved_report = json.loads((run_dir / "preflight_report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved_report["kind"], "stable_run_preflight")
            self.assertEqual(saved_report["summary"]["hard_failure_count"], 0)

    def test_preflight_fails_for_missing_required_runtime_path(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "run"
            args = self._args(root, run_dir)
            args.carla_root = str(root / "missing_carla")

            report = stable_run_preflight.run_preflight(args)

            self.assertFalse(report["passed"])
            failed_ids = {check["id"] for check in report["checks"] if not check["passed"]}
            self.assertIn("carla_root", failed_ids)
            self.assertIn("carla_launcher", failed_ids)

    def test_preflight_can_skip_autoware_paths_for_carla_only_import_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "run"
            args = self._args(root, run_dir)
            args.autoware_enabled = "false"
            args.autoware_ws = ""
            args.autoware_bridge_ws = ""
            args.autoware_underlay_ws = ""
            args.autoware_map_path = ""
            args.sensor_mapping_file = ""
            args.sensor_kit_calibration_file = ""
            args.objects_definition_file = ""

            report = stable_run_preflight.run_preflight(args)

            self.assertTrue(report["passed"])
            checks = {check["id"]: check for check in report["checks"]}
            self.assertTrue(checks["autoware_disabled"]["passed"])
            self.assertNotIn("autoware_ws_setup", checks)

    def test_sumo_enabled_resolves_default_carla_sumo_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "run"
            args = self._args(root, run_dir)
            args.sumo_enabled = "true"
            args.sumo_binary = "python3"
            args.sumo_config_file = ""
            _touch(Path(args.carla_root) / "Co-Simulation" / "Sumo" / "examples" / "Town01.sumocfg")
            _touch(Path(args.carla_root) / "Co-Simulation" / "Sumo" / "run_synchronization.py")

            report = stable_run_preflight.run_preflight(args)

            self.assertTrue(report["passed"])
            checks = {check["id"]: check for check in report["checks"]}
            self.assertTrue(checks["sumo_config_file"]["path"].endswith("Town01.sumocfg"))
            self.assertTrue(checks["sumo_cosim_script"]["path"].endswith("run_synchronization.py"))


if __name__ == "__main__":
    unittest.main()
