from __future__ import annotations

import subprocess
import unittest
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "stack" / "stable" / "start_bridge_host.sh"


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
        self.assertIn("PIX throttle gain: 3.2", proc.stdout)
        self.assertIn("PIX min throttle: 0.0", proc.stdout)
        self.assertIn("PIX max throttle: 0.85", proc.stdout)
        self.assertIn("PIX brake gain: 0.2", proc.stdout)
        self.assertIn("PIX max brake: 0.8", proc.stdout)
        self.assertIn("PIX brake deadband: 0.05", proc.stdout)
        self.assertNotIn("export PIX_CARLA_SKIP_WHEEL_STEER_ANGLE", proc.stdout)
        self.assertIn("export PIX_CARLA_THROTTLE_GAIN=3.2", proc.stdout)
        self.assertIn("export PIX_CARLA_MIN_THROTTLE=0.0", proc.stdout)
        self.assertIn("export PIX_CARLA_MAX_THROTTLE=0.85", proc.stdout)
        self.assertIn("export PIX_CARLA_BRAKE_GAIN=0.2", proc.stdout)
        self.assertIn("export PIX_CARLA_MAX_BRAKE=0.8", proc.stdout)
        self.assertIn("export PIX_CARLA_BRAKE_DEADBAND=0.05", proc.stdout)

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

    def test_non_pix_vehicle_leaves_wheel_steer_guard_unset(self) -> None:
        proc = _run_script("vehicle.toyota.prius")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PIX skip wheel steer angle: ", proc.stdout)
        self.assertIn("PIX throttle gain: ", proc.stdout)
        self.assertIn("PIX brake gain: ", proc.stdout)
        self.assertNotIn("export PIX_CARLA_SKIP_WHEEL_STEER_ANGLE", proc.stdout)
        self.assertNotIn("export PIX_CARLA_THROTTLE_GAIN", proc.stdout)
        self.assertNotIn("export PIX_CARLA_BRAKE_GAIN", proc.stdout)


if __name__ == "__main__":
    unittest.main()
