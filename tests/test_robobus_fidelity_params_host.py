from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "stack" / "stable" / "apply_robobus_2ws_autoware_params_host.sh"


MPC_PARAM = """/**:
  ros__parameters:
    vehicle_model_type: "kinematics_adaptive" # original
"""

SIM_PARAM = """/**:
  ros__parameters:
    vehicle_model_type: "DELAY_STEER_ACC_GEARED_ADAPTIVE" # original
"""

VEHICLE_PARAM = """/**:
  ros__parameters:
    to_4ws_k_threshold: 0.09 # original
    to_2ws_k_threshold: 0.01 # original
    coef_for_4ws: 0.5 # original
"""


def _write_fake_install(root: Path) -> None:
    (root / "install/autoware_launch/share/autoware_launch/config/control/trajectory_follower/lateral").mkdir(
        parents=True
    )
    (root / "install/robobus_description/share/robobus_description/config").mkdir(parents=True)
    (
        root
        / "install/autoware_launch/share/autoware_launch/config/control/trajectory_follower/lateral/mpc.param.yaml"
    ).write_text(MPC_PARAM, encoding="utf-8")
    (
        root / "install/robobus_description/share/robobus_description/config/simulator_model.param.yaml"
    ).write_text(SIM_PARAM, encoding="utf-8")
    (
        root / "install/robobus_description/share/robobus_description/config/vehicle_info.param.yaml"
    ).write_text(VEHICLE_PARAM, encoding="utf-8")


class RobobusFidelityParamsHostTests(unittest.TestCase):
    def test_restore_117th_4ws_profile_writes_real_vehicle_steering_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fake_install(root)
            snapshot_path = root / "runtime_verification" / "robobus_fidelity_profile.json"

            result = subprocess.run(
                [
                    "bash",
                    str(SCRIPT),
                    "--autoware-ws",
                    str(root),
                    "--profile",
                    "117th_4ws",
                    "--snapshot-out",
                    str(snapshot_path),
                ],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Applied PIX robobus Autoware parameter profile: 117th_4ws", result.stdout)
            self.assertIn(
                'vehicle_model_type: "kinematics_adaptive" # PIX 117th 4WS fidelity profile',
                (
                    root
                    / "install/autoware_launch/share/autoware_launch/config/control/trajectory_follower/lateral/mpc.param.yaml"
                ).read_text(encoding="utf-8"),
            )
            self.assertIn(
                'vehicle_model_type: "DELAY_STEER_ACC_GEARED_ADAPTIVE" # PIX 117th 4WS fidelity profile',
                (
                    root / "install/robobus_description/share/robobus_description/config/simulator_model.param.yaml"
                ).read_text(encoding="utf-8"),
            )
            vehicle_text = (
                root / "install/robobus_description/share/robobus_description/config/vehicle_info.param.yaml"
            ).read_text(encoding="utf-8")
            self.assertIn("to_4ws_k_threshold: 0.09 # PIX 117th 4WS fidelity profile", vehicle_text)
            self.assertIn("to_2ws_k_threshold: 0.01 # PIX 117th 4WS fidelity profile", vehicle_text)
            self.assertIn("coef_for_4ws: 0.5 # PIX 117th 4WS fidelity profile", vehicle_text)
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["profile"], "117th_4ws")
            self.assertEqual(snapshot["parameters"]["mpc_vehicle_model_type"], "kinematics_adaptive")
            self.assertEqual(snapshot["parameters"]["simulator_vehicle_model_type"], "DELAY_STEER_ACC_GEARED_ADAPTIVE")
            self.assertEqual(snapshot["parameters"]["to_4ws_k_threshold"], "0.09")
            self.assertEqual(snapshot["parameters"]["to_2ws_k_threshold"], "0.01")
            self.assertEqual(snapshot["parameters"]["coef_for_4ws"], "0.5")

    def test_legacy_carla_2ws_profile_remains_explicitly_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fake_install(root)

            result = subprocess.run(
                ["bash", str(SCRIPT), "--autoware-ws", str(root), "--profile", "carla_2ws"],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            vehicle_text = (
                root / "install/robobus_description/share/robobus_description/config/vehicle_info.param.yaml"
            ).read_text(encoding="utf-8")
            self.assertIn("to_4ws_k_threshold: 999.0 # PIX 2WS CARLA validation override", vehicle_text)
            self.assertIn("to_2ws_k_threshold: 998.0 # PIX 2WS CARLA validation override", vehicle_text)
            self.assertIn("coef_for_4ws: 1.0 # PIX 2WS CARLA validation override", vehicle_text)


if __name__ == "__main__":
    unittest.main()
