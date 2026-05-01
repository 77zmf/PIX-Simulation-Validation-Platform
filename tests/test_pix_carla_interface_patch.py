from __future__ import annotations

import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "stack" / "stable" / "apply_pix_carla_interface_patch_host.sh"


UPSTREAM_CARLA_ROS = textwrap.dedent(
    """
    import math
    import threading

    class carla_ros2_interface(object):
        def first_order_steering(self, steer_input):
            '''First order steering model.'''
            steer_output = 0.0
            if self.prev_timestamp is None:
                self.prev_timestamp = self.timestamp

            dt = self.timestamp - self.prev_timestamp
            if dt > 0.0:
                steer_output = self.prev_steer_output + (steer_input - self.prev_steer_output) * (
                    dt / (self.tau + dt)
                )
            self.prev_steer_output = steer_output
            self.prev_timestamp = self.timestamp
            return steer_output

        def control_callback(self, in_cmd):
            '''Convert and publish CARLA Ego Vehicle Control to AUTOWARE.'''
            out_cmd = carla.VehicleControl()
            out_cmd.throttle = in_cmd.actuation.accel_cmd
            # convert base on steer curve of the vehicle
            steer_curve = self.physics_control.steering_curve
            current_vel = self.ego_actor.get_velocity()
            max_steer_ratio = numpy.interp(
                abs(current_vel.x), [v.x for v in steer_curve], [v.y for v in steer_curve]
            )
            out_cmd.steer = self.first_order_steering(-in_cmd.actuation.steer_cmd) * max_steer_ratio
            out_cmd.brake = in_cmd.actuation.brake_cmd
            self.current_control = out_cmd

        def ego_status(self):
            pass
    """
).lstrip()


class PixCarlaInterfacePatchTests(unittest.TestCase):
    def _write_workspace(self, root: Path) -> tuple[Path, Path]:
        source = (
            root
            / "src"
            / "universe"
            / "autoware_universe"
            / "simulator"
            / "autoware_carla_interface"
            / "src"
            / "autoware_carla_interface"
            / "carla_ros.py"
        )
        build = root / "build" / "autoware_carla_interface" / "src" / "autoware_carla_interface" / "carla_ros.py"
        source.parent.mkdir(parents=True)
        build.parent.mkdir(parents=True)
        source.write_text(UPSTREAM_CARLA_ROS, encoding="utf-8")
        build.write_text(UPSTREAM_CARLA_ROS, encoding="utf-8")
        return source, build

    def test_patch_applies_pix_throttle_brake_and_steer_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, build = self._write_workspace(Path(tmp))

            proc = subprocess.run(
                ["bash", str(SCRIPT), "--autoware-ws", tmp],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            for target in (source, build):
                payload = target.read_text(encoding="utf-8")
                self.assertIn("PIX_CARLA_STEER_HOLD_PATCH", payload)
                self.assertIn("PIX_CARLA_ACTUATION_MAP_PATCH", payload)
                self.assertIn("PIX_CARLA_THROTTLE_GAIN", payload)
                self.assertIn("PIX_CARLA_BRAKE_DEADBAND", payload)
                self.assertIn("PIX_CARLA_STEER_GAIN", payload)
                self.assertIn("steer_output = self.prev_steer_output", payload)
                self.assertIn("out_cmd.throttle = throttle", payload)
                self.assertIn("out_cmd.brake = brake", payload)
                self.assertIn("steer_input = -steer_cmd_rad / max_steer_angle_rad", payload)
                self.assertIn("import os", payload)
                self.assertTrue(Path(str(target) + ".pix_actuation_map.bak").exists())

            second = subprocess.run(
                ["bash", str(SCRIPT), "--autoware-ws", tmp],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("already patched", second.stdout)

    def test_patch_can_rollback_to_original_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, build = self._write_workspace(Path(tmp))
            subprocess.run(["bash", str(SCRIPT), "--autoware-ws", tmp], check=True)

            proc = subprocess.run(
                ["bash", str(SCRIPT), "--autoware-ws", tmp, "--rollback"],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), UPSTREAM_CARLA_ROS)
            self.assertEqual(build.read_text(encoding="utf-8"), UPSTREAM_CARLA_ROS)


if __name__ == "__main__":
    unittest.main()
