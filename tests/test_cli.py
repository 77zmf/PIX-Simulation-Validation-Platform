from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from simctl.cli import main
from simctl.slots import load_slot_catalog, read_slot_lock


class CliTests(unittest.TestCase):
    def test_bootstrap_renders_stable_plan(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(["--repo-root", str(REPO_ROOT), "bootstrap", "--stack", "stable"])
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["stack_id"], "stable")
        self.assertEqual(payload["action"], "bootstrap")
        self.assertEqual(payload["steps"][0]["runner"], "bash")
        self.assertIn("infra/ubuntu/bootstrap_host.sh", payload["steps"][0]["command"])
        self.assertNotIn("wsl.exe", payload["steps"][0]["command"].lower())

    def test_asset_check_reports_virtual_paths_for_builtin_bundle(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(["--repo-root", str(REPO_ROOT), "asset-check", "--bundle", "carla_town01"])
        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["bundle_id"], "carla-town01")
        self.assertTrue(payload["summary"]["all_required_present"])
        statuses = {entry["name"]: entry["status"] for entry in payload["checks"]}
        self.assertEqual(statuses["lanelet2"], "virtual")
        self.assertEqual(statuses["projector"], "virtual")
        self.assertEqual(statuses["pointcloud_dir"], "virtual")

    def test_replay_renders_plan_from_run_result(self) -> None:
        temp_root = REPO_ROOT / ".tmp" / "test_replay_plan"
        shutil.rmtree(temp_root, ignore_errors=True)
        run_dir = temp_root / "run_001"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_result_path = run_dir / "run_result.json"
        run_result_path.write_text(
            json.dumps(
                {
                    "run_id": "run_001",
                    "scenario_id": "stable_l2_reconstruction_public_road_map_refresh",
                    "stack": "stable",
                    "scenario_path": str(REPO_ROOT / "scenarios" / "l2" / "reconstruction_public_road_map_refresh.yaml"),
                    "scenario_params": {
                        "asset_bundle": "site_gy_qyhx_gsh20260302",
                        "sensor_profile": "reconstruction_capture",
                        "algorithm_profile": "reconstruction_public_road_map_refresh",
                    },
                    "resolved_profiles": {
                        "sensor": {"profile_id": "reconstruction_capture"},
                        "algorithm": {"profile_id": "reconstruction_public_road_map_refresh"},
                    },
                    "artifacts": {
                        "run_dir": str(run_dir),
                        "rosbag2": str(run_dir / "rosbags" / "capture"),
                        "carla_recorder": str(run_dir / "carla" / "capture.log"),
                    },
                }
            ),
            encoding="utf-8",
        )
        try:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "replay",
                        "--run-result",
                        str(run_result_path),
                    ]
                )
            self.assertEqual(rc, 0)
            payload = json.loads(stream.getvalue())
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

        self.assertEqual(payload["action"], "replay")
        self.assertEqual(len(payload["steps"]), 2)
        self.assertIn("ros2 bag play", payload["steps"][0]["command"])
        self.assertNotIn("{rosbag_path}", payload["steps"][0]["command"])
        self.assertIn("rosbags/capture", payload["steps"][0]["command"])
        self.assertIn("capture.log", payload["steps"][1]["command"])

    def test_run_creates_passed_stub_result(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "run",
                        "--scenario",
                        "scenarios/l0/smoke_stub.yaml",
                        "--run-root",
                        tempdir,
                        "--slot",
                        "stable-slot-02",
                    ]
                )
            self.assertEqual(rc, 0)
            run_dirs = list(Path(tempdir).iterdir())
            self.assertEqual(len(run_dirs), 1)
            result = json.loads((run_dirs[0] / "run_result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["gate"]["passed"])
            self.assertEqual(result["slot_id"], "stable-slot-02")
            self.assertEqual(result["carla_rpc_port"], 2010)
            self.assertEqual(result["ros_domain_id"], 22)
            self.assertEqual(result["resolved_profiles"]["sensor"]["profile_id"], "ground_truth_control_baseline")
            self.assertEqual(result["resolved_profiles"]["algorithm"]["profile_id"], "planning_control_baseline")
            self.assertTrue(Path(result["artifacts"]["sensor_profile_snapshot"]).exists())
            self.assertTrue(Path(result["artifacts"]["algorithm_profile_snapshot"]).exists())

    def test_up_renders_private_host_runtime_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "up",
                        "--stack",
                        "stable",
                        "--scenario",
                        "scenarios/l0/robobus117th_town01_closed_loop.yaml",
                        "--run-dir",
                        tempdir,
                        "--slot",
                        "stable-slot-01",
                    ]
                )
            self.assertEqual(rc, 0)
            plan_path = Path(stream.getvalue().strip())
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            carla_command = plan["steps"][0]["command"]
            wait_command = plan["steps"][1]["command"]
            bridge_command = plan["steps"][2]["command"]
            autoware_command = plan["steps"][3]["command"]
            localization_bridge_command = plan["steps"][4]["command"]
            actor_object_bridge_command = plan["steps"][5]["command"]
            screenshot_command = plan["steps"][6]["command"]
            self.assertIn("--carla-map 'Town01'", carla_command)
            self.assertIn("--render-mode 'offscreen'", carla_command)
            self.assertIn("wait_for_carla_rpc.py", wait_command)
            self.assertIn("--timeout-sec '90'", wait_command)
            self.assertIn(
                "--autoware-ws '/home/pixmoving/zmf_ws/projects/autoware_universe/autoware'",
                bridge_command,
            )
            self.assertIn(
                "--autoware-underlay-ws '/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware'",
                bridge_command,
            )
            self.assertIn("--vehicle-type 'vehicle.pixmoving.robobus'", bridge_command)
            self.assertIn("--spawn-point '229.7817,2.0201,-0.5,0,0,0'", bridge_command)
            self.assertIn("--rmw-implementation 'rmw_cyclonedds_cpp'", bridge_command)
            self.assertIn("--sensor-kit-name 'robobus_sensor_kit_description'", bridge_command)
            self.assertIn(
                "--sensor-mapping-file '/home/pixmoving/PIX-Simulation-Validation-Platform/assets/sensors/carla/robobus117th_sensor_mapping.yaml'",
                bridge_command,
            )
            self.assertIn(
                "--sensor-kit-calibration-file '/home/pixmoving/PIX-Simulation-Validation-Platform/assets/sensors/carla/robobus117th_sensor_kit_calibration.yaml'",
                bridge_command,
            )
            self.assertIn(
                "--autoware-ws '/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware'",
                autoware_command,
            )
            self.assertIn("--map-path '/home/pixmoving/autoware_map/Town01'", autoware_command)
            self.assertIn("--vehicle-model 'robobus'", autoware_command)
            self.assertIn("--rmw-implementation 'rmw_cyclonedds_cpp'", autoware_command)
            self.assertIn("--sensor-model 'robobus_sensor_kit'", autoware_command)
            self.assertIn("--lidar-type 'robosense'", autoware_command)
            self.assertIn("start_carla_localization_bridge_host.sh", localization_bridge_command)
            self.assertIn(
                "--autoware-ws '/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware'",
                localization_bridge_command,
            )
            self.assertIn("--kill-simple-sim 'true'", localization_bridge_command)
            self.assertIn("start_carla_actor_object_bridge_host.sh", actor_object_bridge_command)
            self.assertIn("--enabled 'false'", actor_object_bridge_command)
            self.assertIn("--include-walkers 'true'", actor_object_bridge_command)
            self.assertIn("capture_visual_screenshot_host.sh", screenshot_command)
            self.assertIn("--render-mode 'offscreen'", screenshot_command)
            self.assertIn("--rviz 'false'", screenshot_command)

    def test_up_allows_explicit_runtime_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with patch.dict(
                os.environ,
                {
                    "SIMCTL_CARLA_RENDER_MODE": "visual",
                    "SIMCTL_CARLA_DISPLAY": ":0",
                    "SIMCTL_CARLA_XAUTHORITY": "/run/user/1000/gdm/Xauthority",
                },
                clear=False,
            ):
                with redirect_stdout(stream):
                    rc = main(
                        [
                            "--repo-root",
                            str(REPO_ROOT),
                            "up",
                            "--stack",
                            "stable",
                            "--scenario",
                            "scenarios/l0/robobus117th_town01_closed_loop.yaml",
                            "--run-dir",
                            tempdir,
                            "--slot",
                            "stable-slot-01",
                        ]
                    )
            self.assertEqual(rc, 0)
            plan = json.loads(Path(stream.getvalue().strip()).read_text(encoding="utf-8"))
            carla_command = plan["steps"][0]["command"]
            screenshot_command = plan["steps"][6]["command"]
            self.assertIn("--render-mode 'visual'", carla_command)
            self.assertIn("--display ':0'", carla_command)
            self.assertIn("--xauthority '/run/user/1000/gdm/Xauthority'", carla_command)
            self.assertIn("--render-mode 'visual'", screenshot_command)
            self.assertIn("--display ':0'", screenshot_command)
            self.assertIn("--xauthority '/run/user/1000/gdm/Xauthority'", screenshot_command)

    def test_up_renders_sumo_step_only_for_sumo_enabled_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "up",
                        "--stack",
                        "stable",
                        "--scenario",
                        "scenarios/l1/sumo_town01_traffic_smoke.yaml",
                        "--run-dir",
                        tempdir,
                        "--slot",
                        "stable-slot-01",
                    ]
                )
            self.assertEqual(rc, 0)
            plan = json.loads(Path(stream.getvalue().strip()).read_text(encoding="utf-8"))
            step_names = [step["name"] for step in plan["steps"]]
            self.assertEqual(step_names[0:4], ["start-carla-server", "wait-carla-rpc", "start-sumo-cosim", "start-autoware-bridge"])
            sumo_command = plan["steps"][2]["command"]
            stop_plan_path = Path(tempdir) / "down_plan.json"
            self.assertIn("start_sumo_cosim_host.sh", sumo_command)
            self.assertIn("--sumo-enabled 'true'", sumo_command)
            self.assertIn("--sumo-traci-port '9000'", sumo_command)
            self.assertIn("Town01.sumocfg", sumo_command)
            self.assertFalse(stop_plan_path.exists())

    def test_up_passes_scenario_carla_root_for_pix_robobus_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "up",
                        "--stack",
                        "stable",
                        "--scenario",
                        "scenarios/l2/planning_control_multi_actor_cut_in_lead_brake.yaml",
                        "--run-dir",
                        tempdir,
                        "--slot",
                        "stable-slot-01",
                    ]
                )
            self.assertEqual(rc, 0)
            plan = json.loads(Path(stream.getvalue().strip()).read_text(encoding="utf-8"))
            carla_step = plan["steps"][0]
            wait_step = plan["steps"][1]
            bridge_command = plan["steps"][2]["command"]
            self.assertEqual(
                carla_step["env"]["CARLA_0915_ROOT"],
                "/home/pixmoving/CARLA_0.9.15",
            )
            self.assertEqual(
                wait_step["env"]["CARLA_0915_ROOT"],
                "/home/pixmoving/CARLA_0.9.15",
            )
            self.assertIn("--carla-root '/home/pixmoving/CARLA_0.9.15'", wait_step["command"])
            self.assertIn("--vehicle-type 'vehicle.pixmoving.robobus'", bridge_command)
            self.assertIn("--spawn-point '229.7817,2.0201,-0.5,0,0,0'", bridge_command)
            self.assertIn("robobus117th_sensor_kit_calibration.yaml", bridge_command)

    def test_run_fails_fast_for_missing_algorithm_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            scenario_path = Path(tempdir) / "invalid_profile.yaml"
            scenario_path.write_text(
                dedent(
                    """\
                    scenario_id: invalid_algorithm_profile
                    stack: stable
                    map_id: Town01
                    asset_bundle: carla_town01
                    ego_init:
                      spawn_point: Town01/1
                    goal:
                      route_id: Town01/simple_loop
                    traffic_profile:
                      mode: background_light
                      vehicles: 1
                      pedestrians: 0
                    weather_profile:
                      preset: ClearNoon
                    sensor_profile: ground_truth_control_baseline
                    algorithm_profile: missing_algorithm_profile
                    seed: 1
                    recording:
                      rosbag2:
                        enabled: false
                      carla_recorder:
                        enabled: false
                    kpi_gate: planning_control_smoke
                    execution:
                      mode: stub
                      stub_outcome: passed
                    """
                ),
                encoding="utf-8",
            )
            with self.assertRaises(FileNotFoundError):
                main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "run",
                        "--scenario",
                        str(scenario_path),
                        "--run-root",
                        tempdir,
                    ]
                )

    def test_run_static_reconstruction_outputs_algorithm_execution_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "run",
                        "--scenario",
                        "scenarios/l2/reconstruction_static_public_road_gaussian_base.yaml",
                        "--run-root",
                        tempdir,
                        "--mock-result",
                        "passed",
                    ]
                )
            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["algorithm_execution"]["family"], "static_gaussians")
            self.assertEqual(result["algorithm_execution"]["stage"], "geometry_base")
            self.assertIn("static_gaussians", result["algorithm_execution"]["artifacts"])

    def test_run_dynamic_reconstruction_outputs_algorithm_execution_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "run",
                        "--scenario",
                        "scenarios/l3/reconstruction_dynamic_public_road_gaussian_replay.yaml",
                        "--run-root",
                        tempdir,
                        "--mock-result",
                        "passed",
                    ]
                )
            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["algorithm_execution"]["family"], "dynamic_gaussians")
            self.assertEqual(result["algorithm_execution"]["stage"], "actor_aware_replay")
            self.assertIn("dynamic_tracks", result["algorithm_execution"]["artifacts"])

    def test_run_execute_marks_launch_failed_when_execution_step_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            slot_id = "stable-slot-03"
            lock_path = REPO_ROOT / "artifacts" / "slot_locks" / "stable" / f"{slot_id}.json"
            previous_lock = lock_path.read_text(encoding="utf-8") if lock_path.exists() else None
            try:
                lock_path.unlink(missing_ok=True)
                with patch(
                    "simctl.cli.execute_plan",
                    return_value=[
                        {
                            "step": "start-carla-server",
                            "status": "failed",
                            "returncode": 2,
                            "log_path": str(Path(tempdir) / "start-carla-server.log"),
                        }
                    ],
                ):
                    with redirect_stdout(stream):
                        rc = main(
                            [
                                "--repo-root",
                                str(REPO_ROOT),
                                "run",
                                "--scenario",
                                "scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml",
                                "--run-root",
                                tempdir,
                                "--slot",
                                slot_id,
                                "--execute",
                            ]
                        )
            finally:
                if previous_lock is None:
                    lock_path.unlink(missing_ok=True)
                else:
                    lock_path.write_text(previous_lock, encoding="utf-8")
            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"], "launch_failed")
            self.assertEqual(result["gate"]["violations"][0]["reason"], "launch_step_failed")
            self.assertEqual(result["gate"]["violations"][0]["returncode"], 2)
            self.assertIsNone(result["runtime_health"])

    def test_run_execute_marks_launch_failed_when_health_probe_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            slot_id = "stable-slot-04"
            lock_path = REPO_ROOT / "artifacts" / "slot_locks" / "stable" / f"{slot_id}.json"
            previous_lock = lock_path.read_text(encoding="utf-8") if lock_path.exists() else None
            try:
                lock_path.unlink(missing_ok=True)
                with (
                    patch(
                        "simctl.cli.execute_plan",
                        return_value=[
                            {
                                "step": "start-carla-server",
                                "status": "started",
                                "pid": 1001,
                                "pid_file": str(Path(tempdir) / "carla.pid"),
                                "log_path": str(Path(tempdir) / "start-carla-server.log"),
                            },
                            {
                                "step": "start-autoware-bridge",
                                "status": "started",
                                "pid": 1002,
                                "pid_file": str(Path(tempdir) / "bridge.pid"),
                                "log_path": str(Path(tempdir) / "start-autoware-bridge.log"),
                            },
                            {
                                "step": "start-autoware-stack",
                                "status": "started",
                                "pid": 1003,
                                "pid_file": str(Path(tempdir) / "autoware.pid"),
                                "log_path": str(Path(tempdir) / "start-autoware-stack.log"),
                            },
                        ],
                    ),
                    patch(
                        "simctl.cli.probe_runtime_health",
                        return_value={
                            "passed": False,
                            "failed_checks": ["carla_rpc_port"],
                            "report_path": str(Path(tempdir) / "health.json"),
                        },
                    ),
                ):
                    with redirect_stdout(stream):
                        rc = main(
                            [
                                "--repo-root",
                                str(REPO_ROOT),
                                "run",
                                "--scenario",
                                "scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml",
                                "--run-root",
                                tempdir,
                                "--slot",
                                slot_id,
                                "--execute",
                            ]
                        )
            finally:
                if previous_lock is None:
                    lock_path.unlink(missing_ok=True)
                else:
                    lock_path.write_text(previous_lock, encoding="utf-8")
            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"], "launch_failed")
            self.assertEqual(result["gate"]["violations"][0]["reason"], "runtime_health_check_failed")
            self.assertEqual(result["gate"]["violations"][0]["failed_checks"], ["carla_rpc_port"])
            self.assertFalse(result["runtime_health"]["passed"])

    def test_run_execute_marks_launch_submitted_when_health_probe_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            slot_id = "stable-slot-01"
            lock_path = REPO_ROOT / "artifacts" / "slot_locks" / "stable" / f"{slot_id}.json"
            previous_lock = lock_path.read_text(encoding="utf-8") if lock_path.exists() else None
            try:
                lock_path.unlink(missing_ok=True)
                with (
                    patch(
                        "simctl.cli.execute_plan",
                        return_value=[
                            {
                                "step": "start-carla-server",
                                "status": "started",
                                "pid": 1001,
                                "pid_file": str(Path(tempdir) / "carla.pid"),
                                "log_path": str(Path(tempdir) / "start-carla-server.log"),
                            },
                            {
                                "step": "start-autoware-bridge",
                                "status": "started",
                                "pid": 1002,
                                "pid_file": str(Path(tempdir) / "bridge.pid"),
                                "log_path": str(Path(tempdir) / "start-autoware-bridge.log"),
                            },
                            {
                                "step": "start-autoware-stack",
                                "status": "started",
                                "pid": 1003,
                                "pid_file": str(Path(tempdir) / "autoware.pid"),
                                "log_path": str(Path(tempdir) / "start-autoware-stack.log"),
                            },
                        ],
                    ),
                    patch(
                        "simctl.cli.probe_runtime_health",
                        return_value={
                            "passed": True,
                            "failed_checks": [],
                            "report_path": str(Path(tempdir) / "health.json"),
                        },
                    ),
                ):
                    with redirect_stdout(stream):
                        rc = main(
                            [
                                "--repo-root",
                                str(REPO_ROOT),
                                "run",
                                "--scenario",
                                "scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml",
                                "--run-root",
                                tempdir,
                                "--slot",
                                slot_id,
                                "--execute",
                            ]
                        )
            finally:
                if previous_lock is None:
                    lock_path.unlink(missing_ok=True)
                else:
                    lock_path.write_text(previous_lock, encoding="utf-8")
            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"], "launch_submitted")
            self.assertEqual(result["gate"]["violations"][0]["reason"], "awaiting_runtime_results")
            self.assertTrue(result["runtime_health"]["passed"])

    def test_finalize_folds_runtime_evidence_into_run_result(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_001"
            runtime_dir = run_dir / "runtime_verification"
            runtime_dir.mkdir(parents=True)
            run_result_path = run_dir / "run_result.json"
            run_result_path.write_text(
                json.dumps(
                    {
                        "run_id": "run_001",
                        "scenario_id": "robobus117th_town01_closed_loop",
                        "stack": "stable",
                        "status": "launch_submitted",
                        "scenario_path": str(REPO_ROOT / "scenarios" / "l0" / "robobus117th_town01_closed_loop.yaml"),
                        "scenario_params": {
                            "traffic_profile": {"mode": "empty_smoke", "vehicles": 0, "pedestrians": 0}
                        },
                        "kpis": {},
                        "gate": {
                            "gate_id": "planning_control_smoke",
                            "passed": False,
                            "violations": [{"metric": "execution", "reason": "awaiting_runtime_results"}],
                        },
                        "failure_labels": [],
                        "runtime_health": {"passed": True, "failed_checks": []},
                        "artifacts": {
                            "run_dir": str(run_dir),
                            "rosbag2": str(run_dir / "rosbags" / "missing"),
                            "carla_recorder": str(run_dir / "carla" / "missing.log"),
                        },
                    }
                ),
                encoding="utf-8",
            )
            (runtime_dir / "closed_loop_shell_error.json").write_text(
                json.dumps(
                    {
                        "service_calls": [{"step": "set_route", "returncode": 2}],
                        "summary": {"moved": False, "total_delta_m": 0.0, "sample_count": 10},
                    }
                ),
                encoding="utf-8",
            )
            (runtime_dir / "closed_loop_route_sync.json").write_text(
                json.dumps(
                    {
                        "goal": {"x": 314.0, "y": -2.0},
                        "service_calls": [{"step": "set_route", "returncode": 0}],
                        "summary": {
                            "moved": True,
                            "total_delta_m": 84.0,
                            "max_speed_mps": 5.2,
                            "lateral_error_m": 0.12,
                            "longitudinal_error_m": 0.2,
                            "jerk_mps3": 1.1,
                            "sample_count": 75,
                            "last_location": {"x": 313.8, "y": 1.8},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "host_bom.json").write_text(json.dumps({"host": "ubuntu-runtime"}), encoding="utf-8")
            (run_dir / "preflight_report.json").write_text(json.dumps({"passed": True}), encoding="utf-8")

            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(["--repo-root", str(REPO_ROOT), "finalize", "--run-dir", str(run_dir)])

            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["gate"]["passed"])
            self.assertEqual(result["kpis"]["route_completion"], 1.0)
            self.assertEqual(result["kpis"]["collision_count"], 0.0)
            self.assertEqual(result["kpis"]["min_ttc_sec"], 999.0)
            self.assertEqual(result["kpis"]["lateral_error_m"], 0.12)
            self.assertEqual(result["kpis"]["longitudinal_error_m"], 0.2)
            self.assertEqual(result["kpis"]["jerk_mps3"], 1.1)
            self.assertEqual(result["runtime_evidence"]["attempt_count"], 1)
            self.assertEqual(result["runtime_evidence"]["successful_attempt_count"], 1)
            self.assertEqual(result["runtime_evidence"]["ignored_attempts"][0]["reason"], "service_call_failed")
            self.assertEqual(result["runtime_evidence_path"], result["artifacts"]["runtime_evidence_summary"])
            self.assertEqual(result["goal_status"], "reached")
            self.assertEqual(result["termination_reason"], "kpi_gate_passed")
            self.assertEqual(result["finalized_by"], "simctl finalize")
            self.assertEqual(result["finalized_at"], result["finished_at"])
            self.assertEqual(result["host_bom_path"], str((run_dir / "host_bom.json").resolve()))
            self.assertEqual(result["preflight_report_path"], str((run_dir / "preflight_report.json").resolve()))
            self.assertTrue(Path(result["artifacts"]["runtime_evidence_summary"]).exists())
            self.assertEqual(
                result["artifact_completeness"]["present"]["runtime_evidence_summary"],
                result["artifacts"]["runtime_evidence_summary"],
            )
            self.assertEqual(
                result["artifact_completeness"]["present"]["host_bom"],
                str((run_dir / "host_bom.json").resolve()),
            )
            self.assertEqual(
                result["artifact_completeness"]["present"]["preflight_report"],
                str((run_dir / "preflight_report.json").resolve()),
            )
            self.assertNotIn("rosbag2", result["artifacts"])
            self.assertNotIn("carla_recorder", result["artifacts"])
            self.assertIn("rosbag2", result["missing_artifacts"])
            self.assertIn("rosbag2", result["artifact_completeness"]["missing"])
            self.assertIn("carla_recorder", result["artifact_completeness"]["missing"])

    def test_finalize_folds_dynamic_actor_probe_into_run_result(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_l2"
            runtime_dir = run_dir / "runtime_verification"
            probe_dir = runtime_dir / "l2_close_cut_in_actor_bridge_20260418T222010"
            old_probe_dir = runtime_dir / "l2_close_cut_in_actor_bridge_20260418T221500"
            stale_probe_dir = runtime_dir / "l2_close_cut_in_dummy_injection_20260418T221000"
            old_sensor_probe_dir = runtime_dir / "sensor_topics_20260418T222010"
            sensor_probe_dir = runtime_dir / "sensor_topics_20260418T222020"
            probe_dir.mkdir(parents=True)
            old_probe_dir.mkdir(parents=True)
            stale_probe_dir.mkdir(parents=True)
            old_sensor_probe_dir.mkdir(parents=True)
            sensor_probe_dir.mkdir(parents=True)
            (run_dir / "run_result.json").write_text(
                json.dumps(
                    {
                        "run_id": "run_l2",
                        "scenario_id": "robobus117th_town01_close_cut_in_actor_bridge",
                        "stack": "stable",
                        "status": "launch_submitted",
                        "scenario_path": str(
                            REPO_ROOT / "scenarios" / "l2" / "robobus117th_town01_close_cut_in_actor_bridge.yaml"
                        ),
                        "scenario_params": {
                            "traffic_profile": {
                                "mode": "carla_actor_bridge_close_cut_in",
                                "vehicles": 1,
                                "pedestrians": 0,
                            }
                        },
                        "kpis": {},
                        "gate": {
                            "gate_id": "planning_control_smoke",
                            "passed": False,
                            "violations": [{"metric": "execution", "reason": "awaiting_runtime_results"}],
                        },
                        "failure_labels": [],
                        "runtime_health": {"passed": True, "failed_checks": []},
                        "artifacts": {"run_dir": str(run_dir)},
                    }
                ),
                encoding="utf-8",
            )
            dynamic_payload = {
                "classification": "l2_close_cut_in_with_dummy_perception_injection:actor_bridge",
                "service_calls": [{"step": "set_route_points", "returncode": 0}],
                "summary": {
                    "sample_count": 177,
                    "moved": True,
                    "collision_count": 0,
                    "min_distance_m": 14.7,
                    "min_ttc_sec": 6.2,
                    "autoware_reacted": True,
                    "reaction_reason": "speed_reduction_ratio",
                    "target_in_lane": True,
                    "max_speed_mps": 4.0,
                    "total_delta_m": 34.0,
                },
                "object_pipeline": {
                    "perception_source": "actor_bridge",
                    "dummy_object_injected": False,
                    "objects_topic_nonempty_after_injection": True,
                },
                "recording": {
                    "rosbag_dir": str(probe_dir / "rosbag_l2_close_cut_in_20260418T222010"),
                    "carla_recorder": str(probe_dir / "carla_l2_close_cut_in_20260418T222010.log"),
                },
                "verdict": {
                    "overall_passed": True,
                    "safety_passed": True,
                    "autoware_dynamic_actor_response_passed": True,
                },
            }
            (probe_dir / "l2_close_cut_in_actor_bridge_20260418T222010.json").write_text(
                json.dumps(dynamic_payload),
                encoding="utf-8",
            )
            old_dynamic_payload = {
                **dynamic_payload,
                "summary": {
                    **dynamic_payload["summary"],
                    "actor_count_observed": 1,
                    "total_delta_m": 1.2,
                },
                "verdict": {
                    "overall_passed": False,
                    "safety_passed": True,
                    "autoware_dynamic_actor_response_passed": False,
                },
            }
            (old_probe_dir / "l2_close_cut_in_actor_bridge_20260418T221500.json").write_text(
                json.dumps(old_dynamic_payload),
                encoding="utf-8",
            )
            stale_payload = {
                **dynamic_payload,
                "object_pipeline": {**dynamic_payload["object_pipeline"], "perception_source": "dummy_injection"},
            }
            (stale_probe_dir / "l2_close_cut_in_dummy_injection_20260418T221000.json").write_text(
                json.dumps(stale_payload),
                encoding="utf-8",
            )
            (old_sensor_probe_dir / "sensor_topics_20260418T222010.json").write_text(
                json.dumps(
                    {
                        "overall_passed": False,
                        "profile": "robobus117th",
                        "summary": {
                            "required_topic_count": 4,
                            "passing_topic_count": 3,
                            "sample_required_topic_count": 3,
                            "sample_received_count": 2,
                            "missing_topics": [],
                            "sample_missing_topics": ["/control/command/control_cmd"],
                            "groups": {},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (sensor_probe_dir / "sensor_topics_20260418T222020.json").write_text(
                json.dumps(
                    {
                        "overall_passed": True,
                        "profile": "robobus117th",
                        "summary": {
                            "required_topic_count": 4,
                            "passing_topic_count": 4,
                            "sample_required_topic_count": 3,
                            "sample_received_count": 3,
                            "missing_topics": [],
                            "sample_missing_topics": [],
                            "groups": {
                                "camera": {
                                    "required": 1,
                                    "passed": 1,
                                    "sample_required": 1,
                                    "sampled": 1,
                                }
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(["--repo-root", str(REPO_ROOT), "finalize", "--run-dir", str(run_dir)])

            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["gate"]["passed"])
            self.assertEqual(result["kpis"]["route_completion"], 1.0)
            self.assertEqual(result["kpis"]["collision_count"], 0.0)
            self.assertEqual(result["kpis"]["min_ttc_sec"], 6.2)
            self.assertEqual(result["kpis"]["dynamic_actor_response"], 1.0)
            self.assertEqual(result["runtime_evidence"]["dynamic_probe_attempt_count"], 1)
            self.assertEqual(result["runtime_evidence"]["successful_dynamic_probe_count"], 1)
            self.assertEqual(
                result["runtime_evidence"]["metric_sources"]["collision_count"],
                "runtime_dynamic_probe",
            )
            ignored_dynamic_reasons = {
                item["reason"] for item in result["runtime_evidence"]["ignored_dynamic_probe_attempts"]
            }
            self.assertIn("scenario_filter_mismatch", ignored_dynamic_reasons)
            self.assertIn("superseded_by_newer_dynamic_probe", ignored_dynamic_reasons)
            self.assertEqual(result["runtime_evidence"]["sensor_probe_attempt_count"], 1)
            self.assertEqual(result["runtime_evidence"]["successful_sensor_probe_count"], 1)
            self.assertEqual(
                result["runtime_evidence"]["ignored_sensor_probe_attempts"][0]["reason"],
                "superseded_by_newer_sensor_probe",
            )
            self.assertEqual(result["kpis"]["sensor_topic_coverage"], 1.0)
            self.assertEqual(result["kpis"]["sensor_sample_coverage"], 1.0)

    def test_finalize_folds_perception_metric_probe_into_run_result(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_bevfusion"
            metric_probe_dir = run_dir / "runtime_verification" / "perception_readiness_20260419T101500"
            metric_probe_dir.mkdir(parents=True)
            (run_dir / "run_result.json").write_text(
                json.dumps(
                    {
                        "run_id": "run_bevfusion",
                        "scenario_id": "stable_l2_perception_bevfusion_public_road_occlusion",
                        "stack": "stable",
                        "status": "launch_submitted",
                        "scenario_path": str(
                            REPO_ROOT / "scenarios" / "l2" / "perception_bevfusion_public_road_occlusion.yaml"
                        ),
                        "scenario_params": {
                            "traffic_profile": {
                                "mode": "public_road_occlusion_shadow",
                                "vehicles": 24,
                                "pedestrians": 10,
                            }
                        },
                        "kpis": {},
                        "gate": {
                            "gate_id": "perception_bevfusion_public_road_gate",
                            "passed": False,
                            "violations": [{"metric": "execution", "reason": "awaiting_runtime_results"}],
                        },
                        "failure_labels": [],
                        "runtime_health": {"passed": True, "failed_checks": []},
                        "artifacts": {"run_dir": str(run_dir)},
                    }
                ),
                encoding="utf-8",
            )
            (metric_probe_dir / "perception_readiness_20260419T101500.json").write_text(
                json.dumps(
                    {
                        "profile": "bevfusion_public_road",
                        "overall_passed": True,
                        "missing_metrics": [],
                        "missing_topics": [],
                        "sample_missing_topics": [],
                        "metrics_file": str(
                            run_dir
                            / "runtime_verification"
                            / "perception_metrics"
                            / "bevfusion_public_road_metrics.json"
                        ),
                        "metrics": {
                            "perception_readiness": 1.0,
                            "detection_recall": 0.94,
                            "false_positive_per_frame": 0.2,
                            "tracking_id_switches": 1,
                            "occupancy_iou": 0.74,
                            "lane_topology_recall": 0.9,
                            "latency_ms": 98,
                            "planner_interface_disagreement_rate": 0.08,
                        },
                    }
                ),
                encoding="utf-8",
            )

            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(["--repo-root", str(REPO_ROOT), "finalize", "--run-dir", str(run_dir)])

            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["gate"]["passed"])
            self.assertEqual(result["runtime_evidence"]["metric_probe_attempt_count"], 1)
            self.assertEqual(result["runtime_evidence"]["successful_metric_probe_count"], 1)
            self.assertEqual(result["kpis"]["perception_readiness"], 1.0)
            self.assertEqual(result["kpis"]["detection_recall"], 0.94)
            self.assertEqual(
                result["runtime_evidence"]["metric_sources"]["detection_recall"],
                "runtime_metric_probe",
            )

    def test_finalize_folds_multi_actor_probe_metrics_into_run_result(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_multi_actor"
            runtime_dir = run_dir / "runtime_verification"
            probe_dir = runtime_dir / "l2_multi_actor_cut_in_lead_brake_actor_bridge_20260419T120000"
            sensor_probe_dir = runtime_dir / "sensor_topics_20260419T120010"
            probe_dir.mkdir(parents=True)
            sensor_probe_dir.mkdir(parents=True)
            (run_dir / "run_result.json").write_text(
                json.dumps(
                    {
                        "run_id": "run_multi_actor",
                        "scenario_id": "stable_l2_planning_control_multi_actor_cut_in_lead_brake",
                        "stack": "stable",
                        "status": "launch_submitted",
                        "scenario_path": str(
                            REPO_ROOT
                            / "scenarios"
                            / "l2"
                            / "planning_control_multi_actor_cut_in_lead_brake.yaml"
                        ),
                        "scenario_params": {
                            "traffic_profile": {
                                "mode": "multi_actor_cut_in_lead_brake_actor_bridge",
                                "vehicles": 3,
                                "pedestrians": 0,
                            }
                        },
                        "kpis": {},
                        "gate": {
                            "gate_id": "planning_control_multi_actor_regression",
                            "passed": False,
                            "violations": [{"metric": "execution", "reason": "awaiting_runtime_results"}],
                        },
                        "failure_labels": [],
                        "runtime_health": {"passed": True, "failed_checks": []},
                        "artifacts": {"run_dir": str(run_dir)},
                    }
                ),
                encoding="utf-8",
            )
            (probe_dir / "l2_multi_actor_cut_in_lead_brake_actor_bridge_20260419T120000.json").write_text(
                json.dumps(
                    {
                        "classification": "l2_multi_actor_cut_in_lead_brake_with_perception_pipeline:actor_bridge",
                        "service_calls": [{"step": "set_route_points", "returncode": 0}],
                        "summary": {
                            "sample_count": 160,
                            "moved": True,
                            "collision_count": 0,
                            "min_distance_m": 12.0,
                            "min_ttc_sec": 4.2,
                            "autoware_reacted": True,
                            "reaction_reason": "near_stop",
                            "target_in_lane": True,
                            "max_speed_mps": 5.0,
                            "total_delta_m": 28.0,
                            "actor_count_spawned": 3,
                            "actor_count_observed": 3,
                            "object_pipeline_nonempty_duration_ratio": 1.0,
                        },
                        "object_pipeline": {
                            "perception_source": "actor_bridge",
                            "dummy_object_injected": False,
                            "objects_topic_nonempty_after_injection": True,
                            "actor_count_observed": 3,
                            "expected_actor_count": 3,
                        },
                        "recording": {
                            "rosbag_dir": str(probe_dir / "rosbag_l2_multi_actor_20260419T120000"),
                            "carla_recorder": str(probe_dir / "carla_l2_multi_actor_20260419T120000.log"),
                        },
                        "verdict": {
                            "overall_passed": True,
                            "safety_passed": True,
                            "autoware_dynamic_actor_response_passed": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (sensor_probe_dir / "sensor_topics_20260419T120010.json").write_text(
                json.dumps(
                    {
                        "overall_passed": True,
                        "profile": "robobus117th",
                        "summary": {
                            "required_topic_count": 4,
                            "passing_topic_count": 4,
                            "sample_required_topic_count": 3,
                            "sample_received_count": 3,
                            "missing_topics": [],
                            "sample_missing_topics": [],
                            "groups": {},
                        },
                    }
                ),
                encoding="utf-8",
            )

            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(["--repo-root", str(REPO_ROOT), "finalize", "--run-dir", str(run_dir)])

            self.assertEqual(rc, 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["gate"]["passed"])
            self.assertEqual(result["kpis"]["actor_count_observed"], 3.0)
            self.assertEqual(result["kpis"]["yield_response_count"], 1.0)
            self.assertEqual(result["kpis"]["object_pipeline_nonempty_duration_ratio"], 1.0)

    def test_validate_executes_scenario_validation_command(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "run_validate"
            run_dir.mkdir()
            scenario_path = root / "scenario_validate.yaml"
            scenario_path.write_text(
                dedent(
                    """
                    scenario_id: validate_command_smoke
                    stack: stable
                    map_id: Town01
                    asset_bundle: carla_town01
                    ego_init: {spawn_point: Town01/1}
                    goal: {route_id: Town01/simple_loop}
                    traffic_profile: {mode: empty_smoke, vehicles: 0, pedestrians: 0}
                    weather_profile: {preset: ClearNoon}
                    sensor_profile: ground_truth_control_baseline
                    algorithm_profile: planning_control_baseline
                    seed: 1
                    recording: {}
                    kpi_gate: planning_control_smoke
                    metadata:
                      validation_command: >
                        python3 -c "import pathlib,sys; pathlib.Path(sys.argv[1]).joinpath('marker.txt').write_text('ok')" <run_dir>
                    execution:
                      mode: external
                      stable_runtime:
                        ros_domain_id: "21"
                        ros_rmw_implementation: rmw_cyclonedds_cpp
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "run_result.json").write_text(
                json.dumps(
                    {
                        "run_id": "run_validate",
                        "scenario_id": "validate_command_smoke",
                        "scenario_path": str(scenario_path),
                        "status": "launch_submitted",
                        "gate": {"gate_id": "planning_control_smoke", "passed": False, "violations": []},
                        "kpis": {},
                        "ros_domain_id": 42,
                        "artifacts": {"run_dir": str(run_dir), "run_result": str(run_dir / "run_result.json")},
                    }
                ),
                encoding="utf-8",
            )

            dry_stream = io.StringIO()
            with redirect_stdout(dry_stream):
                dry_rc = main(["--repo-root", str(REPO_ROOT), "validate", "--run-dir", str(run_dir)])
            dry_payload = json.loads(dry_stream.getvalue())
            self.assertEqual(dry_rc, 0)
            self.assertTrue(dry_payload["validation_available"])
            self.assertIn(str(run_dir), dry_payload["command"])
            self.assertIn("export ROS_DOMAIN_ID=21", dry_payload["shell_command"])

            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(["--repo-root", str(REPO_ROOT), "validate", "--run-dir", str(run_dir), "--execute"])
            payload = json.loads(stream.getvalue())

            self.assertEqual(rc, 0)
            self.assertEqual(payload["validation"]["status"], "passed")
            self.assertTrue((run_dir / "marker.txt").exists())
            self.assertTrue((run_dir / "validation_logs" / "validation_result.json").exists())

    def test_validate_uses_run_result_ros_domain_when_scenario_omits_it(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "run_validate"
            run_dir.mkdir()
            scenario_path = root / "scenario_validate.yaml"
            scenario_path.write_text(
                dedent(
                    """
                    scenario_id: validate_command_smoke
                    stack: stable
                    map_id: Town01
                    asset_bundle: carla_town01
                    ego_init: {spawn_point: Town01/1}
                    goal: {route_id: Town01/simple_loop}
                    traffic_profile: {mode: empty_smoke, vehicles: 0, pedestrians: 0}
                    weather_profile: {preset: ClearNoon}
                    sensor_profile: ground_truth_control_baseline
                    algorithm_profile: planning_control_baseline
                    seed: 1
                    recording: {}
                    kpi_gate: planning_control_smoke
                    metadata:
                      validation_command: echo ok
                    execution:
                      mode: external
                      stable_runtime:
                        ros_rmw_implementation: rmw_cyclonedds_cpp
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "run_result.json").write_text(
                json.dumps(
                    {
                        "run_id": "run_validate",
                        "scenario_id": "validate_command_smoke",
                        "scenario_path": str(scenario_path),
                        "status": "launch_submitted",
                        "gate": {"gate_id": "planning_control_smoke", "passed": False, "violations": []},
                        "kpis": {},
                        "ros_domain_id": 42,
                        "artifacts": {"run_dir": str(run_dir), "run_result": str(run_dir / "run_result.json")},
                    }
                ),
                encoding="utf-8",
            )

            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(["--repo-root", str(REPO_ROOT), "validate", "--run-dir", str(run_dir)])
            payload = json.loads(stream.getvalue())

            self.assertEqual(rc, 0)
            self.assertIn("export ROS_DOMAIN_ID=42", payload["shell_command"])

    def test_campaign_dry_run_renders_stable_perception_control_plan(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "campaign",
                    "--config",
                    "ops/test_campaigns/stable_perception_control.yaml",
                ]
            )

        self.assertEqual(rc, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["campaign_id"], "stable_perception_control")
        self.assertFalse(payload["execute"])
        self.assertEqual(payload["slot_id"], "stable-slot-01")
        self.assertEqual(len(payload["scenarios"]), 5)
        scenario_ids = [scenario["scenario_id"] for scenario in payload["scenarios"]]
        self.assertEqual(
            scenario_ids,
            [
                "stable_l1_follow_lane",
                "robobus117th_town01_close_cut_in_actor_bridge",
                "stable_l2_planning_control_merge_regression",
                "stable_l2_planning_control_multi_actor_cut_in_lead_brake",
                "stable_l2_planning_control_public_road_merge_regression",
            ],
        )
        first_scenario = payload["scenarios"][0]
        second_scenario = payload["scenarios"][1]
        third_scenario = payload["scenarios"][2]
        fourth_scenario = payload["scenarios"][3]
        fifth_scenario = payload["scenarios"][4]
        self.assertTrue(first_scenario["validation"])
        self.assertTrue(second_scenario["validation"])
        self.assertTrue(third_scenario["validation"])
        self.assertTrue(fourth_scenario["validation"])
        self.assertTrue(fifth_scenario["validation"])
        self.assertIn("route_completion>=0.98", first_scenario["expected_observables"])
        self.assertIn("route_goal_lateral_error_m<=0.80", first_scenario["expected_observables"])
        self.assertIn("sensor_topic_coverage=1.0", second_scenario["expected_observables"])
        self.assertIn("min_ttc_sec>=1.8", third_scenario["expected_observables"])
        self.assertIn("actor_count_observed>=2", fourth_scenario["expected_observables"])
        self.assertIn("public_road", fifth_scenario["tags"])
        self.assertEqual([command["step"] for command in first_scenario["commands"]], ["run", "validate", "down"])
        self.assertEqual([command["step"] for command in second_scenario["commands"]], ["run", "validate", "down"])
        self.assertEqual([command["step"] for command in third_scenario["commands"]], ["run", "validate", "down"])
        self.assertEqual([command["step"] for command in fourth_scenario["commands"]], ["run", "validate", "down"])
        self.assertEqual([command["step"] for command in fifth_scenario["commands"]], ["run", "validate", "down"])

    def test_campaign_execute_writes_result_and_report_for_stub_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            config_path = root / "campaign.yaml"
            run_root = root / "runs"
            config_path.write_text(
                dedent(
                    """
                    campaign_id: stub_campaign
                    default_run_root: runs/ignored
                    default_slot: stable-slot-02
                    report: true
                    scenarios:
                      - id: smoke_stub
                        path: scenarios/l0/smoke_stub.yaml
                        validation: false
                        execute: true
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "campaign",
                        "--config",
                        str(config_path),
                        "--run-root",
                        str(run_root),
                        "--execute",
                        "--mock-result",
                        "passed",
                    ]
                )

            self.assertEqual(rc, 0)
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["status"], "passed")
            self.assertTrue(Path(payload["result_path"]).exists())
            self.assertEqual(payload["records"][0]["run_status"], "passed")
            self.assertTrue((run_root / "report" / "report.md").exists())

    def test_batch_validate_report_executes_scenario_validation_command(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            scenario_path = root / "batch_validate.yaml"
            scenario_path.write_text(
                dedent(
                    """
                    scenario_id: batch_validate_smoke
                    stack: stable
                    map_id: Town01
                    asset_bundle: carla_town01
                    ego_init: {spawn_point: Town01/1}
                    goal: {route_id: Town01/simple_loop}
                    traffic_profile: {mode: empty_smoke, vehicles: 0, pedestrians: 0}
                    weather_profile: {preset: ClearNoon}
                    sensor_profile: ground_truth_control_baseline
                    algorithm_profile: planning_control_baseline
                    seed: 1
                    recording: {}
                    kpi_gate: planning_control_smoke
                    metadata:
                      validation_command: >
                        python3 -c "import pathlib,sys; pathlib.Path(sys.argv[1]).joinpath('batch_marker.txt').write_text('ok')" <run_dir>
                    execution:
                      mode: stub
                      stub_outcome: passed
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "batch",
                        str(scenario_path),
                        "--run-root",
                        str(root / "runs"),
                        "--execute",
                        "--mock-result",
                        "passed",
                        "--validate",
                        "--require-validation",
                        "--report",
                    ]
                )

            self.assertEqual(rc, 0)
            batch_index_path = Path(stream.getvalue().strip())
            batch_index = json.loads(batch_index_path.read_text(encoding="utf-8"))
            record = batch_index["records"][0]
            self.assertEqual(record["status"], "passed")
            self.assertEqual(record["validation_returncode"], 0)
            self.assertEqual(record["validation_result"]["validation"]["status"], "passed")
            self.assertTrue((Path(record["run_dir"]) / "batch_marker.txt").exists())
            self.assertTrue(Path(batch_index["report_outputs"]["markdown"]).exists())

    def test_batch_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "batch",
                    "--glob",
                    "scenarios/l1/*.yaml",
                    "--run-root",
                    tempdir,
                    "--mock-result",
                    "passed",
                ]
            )
            first_result_path = next(Path(tempdir).rglob("run_result.json"))
            first_result = json.loads(first_result_path.read_text(encoding="utf-8"))
            first_result["runtime_health"] = {"passed": True, "failed_checks": []}
            first_result["artifacts"]["visual_screenshot"] = str(
                first_result_path.parent / "screenshots" / "visual_startup.png"
            )
            first_result["artifacts"]["operator_action_log"] = str(
                first_result_path.parent / "operator_actions" / "route_reset.log"
            )
            first_result_path.write_text(json.dumps(first_result, indent=2), encoding="utf-8")
            report_dir = Path(tempdir) / "report"
            rc = main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "report",
                    "--run-root",
                    tempdir,
                    "--output-dir",
                    str(report_dir),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertTrue((report_dir / "report.md").exists())
            self.assertTrue((report_dir / "report.html").exists())
            self.assertTrue((report_dir / "issue_update.md").exists())
            report_md = (report_dir / "report.md").read_text(encoding="utf-8")
            report_html = (report_dir / "report.html").read_text(encoding="utf-8")
            self.assertIn("## Failure Clusters", report_md)
            self.assertIn("- None", report_md)
            self.assertIn("runtime_health:passed", report_md)
            self.assertIn("visual_screenshot", report_md)
            self.assertIn("operator_action_log", report_md)
            self.assertIn("runtime_health:passed", report_html)
            self.assertIn("visual_screenshot", report_html)
            self.assertIn("operator_action_log", report_html)

    def test_batch_parallel_uses_two_slots_and_reuses_one_for_third_run(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "batch",
                        "scenarios/l0/smoke_stub.yaml",
                        "scenarios/l1/regression_follow_lane.yaml",
                        "scenarios/l2/planning_control_merge_regression.yaml",
                        "--run-root",
                        tempdir,
                        "--parallel",
                        "2",
                        "--mock-result",
                        "passed",
                    ]
                )
            self.assertEqual(rc, 0)
            batch_index_path = Path(stream.getvalue().strip())
            batch_index = json.loads(batch_index_path.read_text(encoding="utf-8"))
            self.assertEqual(batch_index["parallel"], 2)
            self.assertEqual(len(batch_index["records"]), 3)
            slot_ids = [record["slot_id"] for record in batch_index["records"]]
            self.assertEqual(len(set(slot_ids)), 2)
            for record in batch_index["records"]:
                result = json.loads(Path(record["run_result"]).read_text(encoding="utf-8"))
                self.assertEqual(result["slot_id"], record["slot_id"])
                self.assertEqual(result["status"], "passed")

    def test_batch_ignores_existing_report_directory_when_indexing_results(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            (Path(tempdir) / "report").mkdir()
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "batch",
                        "--glob",
                        "scenarios/l1/*.yaml",
                        "--run-root",
                        tempdir,
                        "--mock-result",
                        "passed",
                    ]
                )
            self.assertEqual(rc, 0)
            batch_dirs = sorted(path for path in Path(tempdir).iterdir() if path.is_dir() and "__batch" in path.name)
            self.assertEqual(len(batch_dirs), 1)
            batch_index = json.loads((batch_dirs[0] / "batch_index.json").read_text(encoding="utf-8"))
            for record in batch_index["records"]:
                self.assertTrue(Path(record["run_result"]).exists())
                self.assertEqual(Path(record["run_result"]).name, "run_result.json")

    def test_down_releases_slot_lock_for_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "20260330T000000000000Z__stable_l1_follow_lane"
            run_dir.mkdir(parents=True)
            slot = load_slot_catalog("stable", REPO_ROOT)[0]
            lock_path = REPO_ROOT / "artifacts" / "slot_locks" / "stable" / f"{slot.slot_id}.json"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            previous_lock = lock_path.read_text(encoding="utf-8") if lock_path.exists() else None
            (run_dir / "run_result.json").write_text(
                json.dumps(
                    {
                        "stack": "stable",
                        "slot_id": slot.slot_id,
                    }
                ),
                encoding="utf-8",
            )
            try:
                lock_path.write_text(
                    json.dumps(
                        {
                            "stack_id": "stable",
                            "slot_id": slot.slot_id,
                            "scenario_id": "stable_l1_follow_lane",
                            "run_dir": str(run_dir),
                        }
                    ),
                    encoding="utf-8",
                )
                with patch("simctl.cli.execute_plan", return_value=[]):
                    rc = main(
                        [
                            "--repo-root",
                            str(REPO_ROOT),
                            "down",
                            "--stack",
                            "stable",
                            "--run-dir",
                            str(run_dir),
                            "--execute",
                        ]
                    )
                self.assertEqual(rc, 0)
                self.assertIsNone(read_slot_lock(REPO_ROOT, "stable", slot.slot_id))
            finally:
                if previous_lock is None:
                    lock_path.unlink(missing_ok=True)
                else:
                    lock_path.write_text(previous_lock, encoding="utf-8")

    def test_digest_from_fixture_json(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            stream = io.StringIO()
            with redirect_stdout(stream):
                rc = main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "digest",
                        "--config",
                        str(REPO_ROOT / "ops" / "project_automation.yaml"),
                        "--tasks-json",
                        str(REPO_ROOT / "tests" / "fixtures" / "project_tasks.json"),
                        "--scenarios-json",
                        str(REPO_ROOT / "tests" / "fixtures" / "project_scenarios.json"),
                        "--output-dir",
                        tempdir,
                    ]
                )
            self.assertEqual(rc, 0)
            outputs = json.loads(stream.getvalue())
            summary = json.loads(Path(outputs["summary"]).read_text(encoding="utf-8"))
            self.assertIn("Confirm E2E shadow evaluation plan", summary["task_summary"]["blocked_titles"])
            scenario_watch_titles = summary["scenario_summary"]["due_soon_titles"] + summary["scenario_summary"]["overdue_titles"]
            self.assertIn("Unprotected left at signalized intersection", scenario_watch_titles)
            self.assertTrue(Path(outputs["markdown"]).exists())
            self.assertTrue(Path(outputs["html"]).exists())

if __name__ == "__main__":
    unittest.main()
