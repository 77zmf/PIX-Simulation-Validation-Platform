from __future__ import annotations

import subprocess
import unittest
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "stack" / "stable" / "start_bridge_host.sh"
LOCALIZATION_SCRIPT = REPO_ROOT / "stack" / "stable" / "start_carla_localization_bridge_host.sh"


def _run_script(vehicle_type: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--scenario",
            "scenario.yaml",
            "--run-dir",
            "/tmp/run",
            "--vehicle-type",
            vehicle_type,
            "--carla-port",
            "2000",
            "--traffic-manager-port",
            "8000",
            "--ros-domain-id",
            "21",
            "--rmw-implementation",
            "rmw_cyclonedds_cpp",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class StartBridgeHostTests(unittest.TestCase):
    def test_pix_vehicle_leaves_wheel_steer_guard_unset_by_default(self) -> None:
        proc = _run_script("vehicle.pixmoving.robobus")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX skip wheel steer angle: ", proc.stdout)
        self.assertIn("PIX steer gain: 0.90", proc.stdout)
        self.assertIn("PIX steer abs limit: ", proc.stdout)
        self.assertIn("PIX steer tau: ", proc.stdout)
        self.assertIn("PIX throttle gain: 3.8", proc.stdout)
        self.assertIn("PIX min throttle: 0.0", proc.stdout)
        self.assertIn("PIX max throttle: 1.0", proc.stdout)
        self.assertIn("PIX creep throttle: 0.0", proc.stdout)
        self.assertIn("PIX creep speed threshold mps: 0.08", proc.stdout)
        self.assertIn("PIX brake gain: 0.2", proc.stdout)
        self.assertIn("PIX max brake: 0.8", proc.stdout)
        self.assertIn("PIX brake deadband: 0.05", proc.stdout)
        self.assertIn("PIX brake creep throttle: ", proc.stdout)
        self.assertIn("PIX brake creep max brake cmd: ", proc.stdout)
        self.assertIn("PIX brake creep speed threshold mps: ", proc.stdout)
        self.assertIn("PIX brake creep min target velocity mps: ", proc.stdout)
        self.assertIn("PIX suppress brake below target: ", proc.stdout)
        self.assertIn("PIX brake target speed margin mps: ", proc.stdout)
        self.assertIn("PIX target speed brake max cmd: ", proc.stdout)
        self.assertIn("PIX speed guard max mps: ", proc.stdout)
        self.assertIn("PIX speed guard band mps: ", proc.stdout)
        self.assertIn("PIX speed guard brake gain: ", proc.stdout)
        self.assertIn("PIX ROS y sign: ", proc.stdout)
        self.assertIn("PIX physics center of mass z m: ", proc.stdout)
        self.assertIn("PIX physics use sweep wheel collision: ", proc.stdout)
        self.assertNotIn("export PIX_CARLA_SKIP_WHEEL_STEER_ANGLE", proc.stdout)
        self.assertNotIn("export PIX_CARLA_ROS_Y_SIGN", proc.stdout)
        self.assertNotIn("export PIX_CARLA_SPEED_GUARD_MAX_MPS", proc.stdout)
        self.assertNotIn("export PIX_CARLA_PHYSICS_CENTER_OF_MASS_Z_M", proc.stdout)
        self.assertIn("export PIX_CARLA_STEER_GAIN=0.90", proc.stdout)
        self.assertNotIn("export PIX_CARLA_STEER_ABS_LIMIT", proc.stdout)
        self.assertNotIn("export PIX_CARLA_STEER_TAU", proc.stdout)
        self.assertNotIn("export PIX_CARLA_STEERING_REPORT_SIGN", proc.stdout)
        self.assertNotIn("export PIX_CARLA_ACTUATION_STEER_STATUS_SIGN", proc.stdout)
        self.assertIn("export PIX_CARLA_THROTTLE_GAIN=3.8", proc.stdout)
        self.assertIn("export PIX_CARLA_MIN_THROTTLE=0.0", proc.stdout)
        self.assertIn("export PIX_CARLA_MAX_THROTTLE=1.0", proc.stdout)
        self.assertIn("export PIX_CARLA_CREEP_THROTTLE=0.0", proc.stdout)
        self.assertIn("export PIX_CARLA_CREEP_SPEED_THRESHOLD_MPS=0.08", proc.stdout)
        self.assertIn("export PIX_CARLA_BRAKE_GAIN=0.2", proc.stdout)
        self.assertIn("export PIX_CARLA_MAX_BRAKE=0.8", proc.stdout)
        self.assertIn("export PIX_CARLA_BRAKE_DEADBAND=0.05", proc.stdout)
        self.assertNotIn("export PIX_CARLA_BRAKE_CREEP_THROTTLE", proc.stdout)
        self.assertNotIn("export PIX_CARLA_BRAKE_CREEP_MAX_BRAKE_CMD", proc.stdout)
        self.assertNotIn("export PIX_CARLA_BRAKE_CREEP_SPEED_THRESHOLD_MPS", proc.stdout)
        self.assertNotIn("export PIX_CARLA_BRAKE_CREEP_MIN_TARGET_VELOCITY_MPS", proc.stdout)
        self.assertNotIn("export PIX_CARLA_SUPPRESS_BRAKE_BELOW_TARGET", proc.stdout)
        self.assertIn("export PYTHONNOUSERSITE=1", proc.stdout)
        self.assertIn("CARLA Python path:", proc.stdout)
        self.assertIn("pythonpath_overlay", proc.stdout)

    def test_pix_vehicle_can_enable_wheel_steer_guard_by_override(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--vehicle-type",
                "vehicle.pixmoving.robobus",
                "--carla-port",
                "2000",
                "--traffic-manager-port",
                "8000",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PIX_CARLA_SKIP_WHEEL_STEER_ANGLE": "1"},
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX skip wheel steer angle: 1", proc.stdout)
        self.assertIn("export PIX_CARLA_SKIP_WHEEL_STEER_ANGLE=1", proc.stdout)

    def test_pix_vehicle_can_override_steer_gain(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--vehicle-type",
                "vehicle.pixmoving.robobus",
                "--carla-port",
                "2000",
                "--traffic-manager-port",
                "8000",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PIX_CARLA_STEER_GAIN": "1.12"},
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX steer gain: 1.12", proc.stdout)
        self.assertIn("export PIX_CARLA_STEER_GAIN=1.12", proc.stdout)

    def test_pix_vehicle_can_override_steer_abs_limit(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--vehicle-type",
                "vehicle.pixmoving.robobus",
                "--carla-port",
                "2000",
                "--traffic-manager-port",
                "8000",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PIX_CARLA_STEER_ABS_LIMIT": "0.018"},
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX steer abs limit: 0.018", proc.stdout)
        self.assertIn("export PIX_CARLA_STEER_ABS_LIMIT=0.018", proc.stdout)

    def test_exports_pix_carla_steering_status_sign_overrides(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--vehicle-type",
                "vehicle.pixmoving.robobus",
                "--carla-port",
                "2000",
                "--traffic-manager-port",
                "8000",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **os.environ,
                "PIX_CARLA_STEERING_REPORT_SIGN": "1.0",
                "PIX_CARLA_ACTUATION_STEER_STATUS_SIGN": "1.0",
            },
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX steering report sign: 1.0", proc.stdout)
        self.assertIn("PIX actuation steer status sign: 1.0", proc.stdout)
        self.assertIn("export PIX_CARLA_STEERING_REPORT_SIGN=1.0", proc.stdout)
        self.assertIn("export PIX_CARLA_ACTUATION_STEER_STATUS_SIGN=1.0", proc.stdout)

    def test_pix_vehicle_can_override_steer_tau(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--vehicle-type",
                "vehicle.pixmoving.robobus",
                "--carla-port",
                "2000",
                "--traffic-manager-port",
                "8000",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PIX_CARLA_STEER_TAU": "0.05"},
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX steer tau: 0.05", proc.stdout)
        self.assertIn("export PIX_CARLA_STEER_TAU=0.05", proc.stdout)

    def test_pix_vehicle_can_enable_speed_guard_by_override(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--vehicle-type",
                "vehicle.pixmoving.robobus",
                "--carla-port",
                "2000",
                "--traffic-manager-port",
                "8000",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **os.environ,
                "PIX_CARLA_SPEED_GUARD_MAX_MPS": "9.2",
                "PIX_CARLA_SPEED_GUARD_BAND_MPS": "1.5",
                "PIX_CARLA_SPEED_GUARD_BRAKE_GAIN": "0.4",
            },
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX speed guard max mps: 9.2", proc.stdout)
        self.assertIn("PIX speed guard band mps: 1.5", proc.stdout)
        self.assertIn("PIX speed guard brake gain: 0.4", proc.stdout)
        self.assertIn("export PIX_CARLA_SPEED_GUARD_MAX_MPS=9.2", proc.stdout)
        self.assertIn("export PIX_CARLA_SPEED_GUARD_BAND_MPS=1.5", proc.stdout)
        self.assertIn("export PIX_CARLA_SPEED_GUARD_BRAKE_GAIN=0.4", proc.stdout)

    def test_pix_vehicle_can_enable_brake_creep_by_override(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--vehicle-type",
                "vehicle.pixmoving.robobus",
                "--carla-port",
                "2000",
                "--traffic-manager-port",
                "8000",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **os.environ,
                "PIX_CARLA_BRAKE_CREEP_THROTTLE": "0.22",
                "PIX_CARLA_BRAKE_CREEP_MAX_BRAKE_CMD": "0.25",
                "PIX_CARLA_BRAKE_CREEP_SPEED_THRESHOLD_MPS": "0.12",
                "PIX_CARLA_BRAKE_CREEP_MIN_TARGET_VELOCITY_MPS": "0.08",
                "PIX_CARLA_SUPPRESS_BRAKE_BELOW_TARGET": "1",
                "PIX_CARLA_BRAKE_TARGET_SPEED_MARGIN_MPS": "0.3",
                "PIX_CARLA_TARGET_SPEED_BRAKE_MAX_CMD": "0.2",
            },
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX brake creep throttle: 0.22", proc.stdout)
        self.assertIn("PIX brake creep max brake cmd: 0.25", proc.stdout)
        self.assertIn("PIX brake creep speed threshold mps: 0.12", proc.stdout)
        self.assertIn("PIX brake creep min target velocity mps: 0.08", proc.stdout)
        self.assertIn("PIX suppress brake below target: 1", proc.stdout)
        self.assertIn("PIX brake target speed margin mps: 0.3", proc.stdout)
        self.assertIn("PIX target speed brake max cmd: 0.2", proc.stdout)
        self.assertIn("export PIX_CARLA_BRAKE_CREEP_THROTTLE=0.22", proc.stdout)
        self.assertIn("export PIX_CARLA_BRAKE_CREEP_MAX_BRAKE_CMD=0.25", proc.stdout)
        self.assertIn("export PIX_CARLA_BRAKE_CREEP_SPEED_THRESHOLD_MPS=0.12", proc.stdout)
        self.assertIn("export PIX_CARLA_BRAKE_CREEP_MIN_TARGET_VELOCITY_MPS=0.08", proc.stdout)
        self.assertIn("export PIX_CARLA_SUPPRESS_BRAKE_BELOW_TARGET=1", proc.stdout)
        self.assertIn("export PIX_CARLA_BRAKE_TARGET_SPEED_MARGIN_MPS=0.3", proc.stdout)
        self.assertIn("export PIX_CARLA_TARGET_SPEED_BRAKE_MAX_CMD=0.2", proc.stdout)

    def test_pix_vehicle_can_override_ros_y_sign(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--vehicle-type",
                "vehicle.pixmoving.robobus",
                "--carla-port",
                "2000",
                "--traffic-manager-port",
                "8000",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PIX_CARLA_ROS_Y_SIGN": "1"},
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX ROS y sign: 1", proc.stdout)
        self.assertIn("export PIX_CARLA_ROS_Y_SIGN=1", proc.stdout)

    def test_pix_vehicle_can_enable_runtime_physics_overrides(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--vehicle-type",
                "vehicle.pixmoving.robobus",
                "--carla-port",
                "2000",
                "--traffic-manager-port",
                "8000",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **os.environ,
                "PIX_CARLA_PHYSICS_MASS_KG": "1800",
                "PIX_CARLA_PHYSICS_DRAG_COEFFICIENT": "0.35",
                "PIX_CARLA_PHYSICS_CENTER_OF_MASS_Z_M": "-0.80",
                "PIX_CARLA_PHYSICS_WHEEL_DAMPING_RATE": "0.35",
                "PIX_CARLA_PHYSICS_USE_SWEEP_WHEEL_COLLISION": "true",
            },
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX physics mass kg: 1800", proc.stdout)
        self.assertIn("PIX physics drag coefficient: 0.35", proc.stdout)
        self.assertIn("PIX physics center of mass z m: -0.80", proc.stdout)
        self.assertIn("PIX physics wheel damping rate: 0.35", proc.stdout)
        self.assertIn("PIX physics use sweep wheel collision: true", proc.stdout)
        self.assertIn("export PIX_CARLA_PHYSICS_MASS_KG=1800", proc.stdout)
        self.assertIn("export PIX_CARLA_PHYSICS_CENTER_OF_MASS_Z_M=-0.80", proc.stdout)
        self.assertIn("export PIX_CARLA_PHYSICS_USE_SWEEP_WHEEL_COLLISION=true", proc.stdout)

    def test_bridge_sync_mode_arg_is_forwarded_when_set(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--vehicle-type",
                "vehicle.pixmoving.robobus",
                "--carla-port",
                "2000",
                "--traffic-manager-port",
                "8000",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
                "--sync-mode",
                "False",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("CARLA bridge sync mode: False", proc.stdout)
        self.assertIn("sync_mode:=False", proc.stdout)

    def test_non_pix_vehicle_leaves_wheel_steer_guard_unset(self) -> None:
        proc = _run_script("vehicle.toyota.prius")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX skip wheel steer angle: ", proc.stdout)
        self.assertIn("PIX steer gain: ", proc.stdout)
        self.assertIn("PIX throttle gain: ", proc.stdout)
        self.assertIn("PIX creep throttle: ", proc.stdout)
        self.assertIn("PIX brake gain: ", proc.stdout)
        self.assertIn("PIX ROS y sign: ", proc.stdout)
        self.assertNotIn("export PIX_CARLA_SKIP_WHEEL_STEER_ANGLE", proc.stdout)
        self.assertNotIn("export PIX_CARLA_ROS_Y_SIGN", proc.stdout)
        self.assertNotIn("export PIX_CARLA_STEER_GAIN", proc.stdout)
        self.assertNotIn("export PIX_CARLA_THROTTLE_GAIN", proc.stdout)
        self.assertNotIn("export PIX_CARLA_CREEP_THROTTLE", proc.stdout)
        self.assertNotIn("export PIX_CARLA_BRAKE_GAIN", proc.stdout)

    def test_localization_bridge_actor_source_exports_carla_context(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                str(LOCALIZATION_SCRIPT),
                "--scenario",
                "scenario.yaml",
                "--run-dir",
                "/tmp/run",
                "--slot-id",
                "stable-slot-01",
                "--ros-domain-id",
                "21",
                "--rmw-implementation",
                "rmw_cyclonedds_cpp",
                "--runtime-namespace",
                "/simctl/stable/slot01",
                "--carla-root",
                "/opt/carla",
                "--carla-host",
                "127.0.0.1",
                "--carla-port",
                "2010",
                "--ego-vehicle-role-name",
                "ego_vehicle",
                "--source",
                "carla_actor",
                "--ros-y-sign",
                "1",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Localization source: carla_actor", proc.stdout)
        self.assertIn("CARLA root: /opt/carla", proc.stdout)
        self.assertIn("CARLA port: 2010", proc.stdout)
        self.assertIn("ROS y sign: 1", proc.stdout)


if __name__ == "__main__":
    unittest.main()
