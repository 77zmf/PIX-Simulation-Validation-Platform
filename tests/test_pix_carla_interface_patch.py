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
            out_steering_state = SteeringReport()
            out_steering_state.steering_tire_angle = -math.radians(
                self.ego_actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FL_Wheel)
            )
    """
).lstrip()

UPSTREAM_CARLA_WRAPPER = textwrap.dedent(
    """
    import numpy as np
    from queue import Empty, Queue

    class SensorInterface(object):
        def __init__(self):
            self._sensors_objects = {}
            self._new_data_buffers = Queue()
            self._queue_timeout = 10
    """
).lstrip()

LEGACY_PATCHED_CARLA_ROS = textwrap.dedent(
    """
    import math
    import os
    import threading

    class carla_ros2_interface(object):
        def first_order_steering(self, steer_input):
            '''First order steering model.'''
            # PIX_CARLA_STEER_HOLD_PATCH: hold previous output when callbacks
            # share the same timestamp.
            steer_output = self.prev_steer_output
            if self.prev_timestamp is None:
                self.prev_timestamp = self.timestamp
            return steer_output

        def control_callback(self, in_cmd):
            \"\"\"Convert and publish CARLA Ego Vehicle Control to AUTOWARE.\"\"\"
            # PIX_CARLA_ACTUATION_MAP_PATCH: apply PIX robobus CARLA actuation calibration.
            def _env_float(name, default):
                return float(os.environ.get(name, str(default)) or str(default))

            out_cmd = carla.VehicleControl()
            current_vel = self.ego_actor.get_velocity()
            ego_speed_mps = math.sqrt(current_vel.x * current_vel.x)
            raw_throttle = max(float(in_cmd.actuation.accel_cmd), 0.0)
            raw_brake = max(float(in_cmd.actuation.brake_cmd), 0.0)
            throttle_gain = _env_float("PIX_CARLA_THROTTLE_GAIN", 1.0)
            brake_gain = _env_float("PIX_CARLA_BRAKE_GAIN", 1.0)
            max_brake = _env_float("PIX_CARLA_MAX_BRAKE", 1.0)
            throttle = raw_throttle * throttle_gain
            brake = min(max(raw_brake * brake_gain, 0.0), max_brake)
            if brake > 0.0:
                throttle = 0.0
            out_cmd.throttle = throttle
            out_cmd.brake = brake
            self.current_control = out_cmd

        def ego_status(self):
            out_steering_state = SteeringReport()
            # PIX_CARLA_SKIP_WHEEL_STEER_ANGLE_PATCH: existing legacy marker.
            out_steering_state.steering_tire_angle = 0.0
    """
).lstrip()

UPSTREAM_CARLA_AUTOWARE = textwrap.dedent(
    """
    import random

    class BridgeLoop(object):
        def _tick_sensor(self, timestamp):
            try:
                ego_action = self.sensor()
            except SensorReceivedNoData as e:
                raise RuntimeError(e)
            self.ego_actor.apply_control(ego_action)

    class InitializeInterface(object):
        def load_world(self):
            client = carla.Client(self.local_host, self.port)
            client.set_timeout(self.timeout)
            client.load_world(self.carla_map)
            self.world = client.get_world()
            settings = self.world.get_settings()
    """
).lstrip()

UPSTREAM_CARLA_UTILS = textwrap.dedent(
    """
    import math

    def carla_location_to_ros_point(carla_location):
        \"\"\"Convert a carla location to a ROS point.\"\"\"
        ros_point = Point()
        ros_point.x = carla_location.x
        ros_point.y = -carla_location.y
        ros_point.z = carla_location.z

        return ros_point

    def carla_rotation_to_ros_quaternion(carla_rotation):
        \"\"\"Convert a carla rotation to a ROS quaternion.\"\"\"
        roll = math.radians(carla_rotation.roll)
        pitch = -math.radians(carla_rotation.pitch)
        yaw = -math.radians(carla_rotation.yaw)
        quat = euler2quat(roll, pitch, yaw)
        ros_quaternion = Quaternion(w=quat[0], x=quat[1], y=quat[2], z=quat[3])

        return ros_quaternion

    def ros_quaternion_to_carla_rotation(ros_quaternion):
        \"\"\"Convert ROS quaternion to carla rotation.\"\"\"
        roll, pitch, yaw = quat2euler(
            [ros_quaternion.w, ros_quaternion.x, ros_quaternion.y, ros_quaternion.z]
        )

        return carla.Rotation(
            roll=math.degrees(roll), pitch=-math.degrees(pitch), yaw=-math.degrees(yaw)
        )

    def ros_pose_to_carla_transform(ros_pose):
        \"\"\"Convert ROS pose to carla transform.\"\"\"
        return carla.Transform(
            carla.Location(ros_pose.position.x, -ros_pose.position.y, ros_pose.position.z),
            ros_quaternion_to_carla_rotation(ros_pose.orientation),
        )
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
        source_bridge_loop = source.parent / "carla_autoware.py"
        build_bridge_loop = build.parent / "carla_autoware.py"
        source_wrapper = source.parent / "modules" / "carla_wrapper.py"
        build_wrapper = build.parent / "modules" / "carla_wrapper.py"
        source_utils = source.parent / "modules" / "carla_utils.py"
        build_utils = build.parent / "modules" / "carla_utils.py"
        source.parent.mkdir(parents=True)
        build.parent.mkdir(parents=True)
        source_wrapper.parent.mkdir(parents=True)
        build_wrapper.parent.mkdir(parents=True)
        source.write_text(UPSTREAM_CARLA_ROS, encoding="utf-8")
        build.write_text(UPSTREAM_CARLA_ROS, encoding="utf-8")
        source_bridge_loop.write_text(UPSTREAM_CARLA_AUTOWARE, encoding="utf-8")
        build_bridge_loop.write_text(UPSTREAM_CARLA_AUTOWARE, encoding="utf-8")
        source_wrapper.write_text(UPSTREAM_CARLA_WRAPPER, encoding="utf-8")
        build_wrapper.write_text(UPSTREAM_CARLA_WRAPPER, encoding="utf-8")
        source_utils.write_text(UPSTREAM_CARLA_UTILS, encoding="utf-8")
        build_utils.write_text(UPSTREAM_CARLA_UTILS, encoding="utf-8")
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
                self.assertIn("PIX_CARLA_SKIP_WHEEL_STEER_ANGLE_PATCH", payload)
                self.assertIn("PIX_CARLA_THROTTLE_GAIN", payload)
                self.assertIn("PIX_CARLA_BRAKE_DEADBAND", payload)
                self.assertIn("PIX_CARLA_SPEED_GUARD_MAX_MPS", payload)
                self.assertIn("speed_guard_start_mps", payload)
                self.assertIn("speed_guard_brake_gain", payload)
                self.assertIn("PIX_CARLA_STEER_GAIN", payload)
                self.assertIn("out_steering_state.steering_tire_angle = 0.0", payload)
                self.assertIn("steer_output = self.prev_steer_output", payload)
                self.assertIn("out_cmd.throttle = throttle", payload)
                self.assertIn("out_cmd.brake = brake", payload)
                self.assertIn("steer_input = -steer_cmd_rad / max_steer_angle_rad", payload)
                self.assertIn("import os", payload)
                self.assertTrue(Path(str(target) + ".pix_actuation_map.bak").exists())
                wrapper = target.parent / "modules" / "carla_wrapper.py"
                wrapper_payload = wrapper.read_text(encoding="utf-8")
                self.assertIn("PIX_CARLA_SENSOR_QUEUE_TIMEOUT_PATCH", wrapper_payload)
                self.assertIn("PIX_CARLA_SENSOR_QUEUE_TIMEOUT_SEC", wrapper_payload)
                self.assertIn("import os", wrapper_payload)
                self.assertTrue(Path(str(wrapper) + ".pix_sensor_queue_timeout.bak").exists())
                utils = target.parent / "modules" / "carla_utils.py"
                utils_payload = utils.read_text(encoding="utf-8")
                self.assertIn("PIX_CARLA_ROS_Y_SIGN_PATCH", utils_payload)
                self.assertIn("PIX_CARLA_ROS_Y_SIGN", utils_payload)
                self.assertIn("pix_carla_ros_y_sign()", utils_payload)
                self.assertTrue(Path(str(utils) + ".pix_ros_y_sign.bak").exists())
                bridge_loop = target.parent / "carla_autoware.py"
                bridge_payload = bridge_loop.read_text(encoding="utf-8")
                self.assertIn("PIX_CARLA_OPENDRIVE_WORLD_PATCH", bridge_payload)
                self.assertIn("client.generate_opendrive_world", bridge_payload)
                self.assertIn("carla.OpendriveGenerationParameters", bridge_payload)
                self.assertIn("generation_params.enable_mesh_visibility = True", bridge_payload)
                self.assertIn("generation_params.enable_pedestrian_navigation = False", bridge_payload)
                self.assertIn("PIX_CARLA_SENSOR_TIMEOUT_TOLERANCE_PATCH", bridge_payload)
                self.assertIn("ego_action = self.ego_actor.get_control()", bridge_payload)
                self.assertIn("import os", bridge_payload)
                self.assertTrue(Path(str(bridge_loop) + ".pix_sensor_timeout_tolerance.bak").exists())

    def test_patch_upgrades_legacy_actuation_patch_with_speed_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, build = self._write_workspace(Path(tmp))
            source.write_text(LEGACY_PATCHED_CARLA_ROS, encoding="utf-8")
            build.write_text(LEGACY_PATCHED_CARLA_ROS, encoding="utf-8")

            proc = subprocess.run(
                ["bash", str(SCRIPT), "--autoware-ws", tmp],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("upgraded calibrated throttle, brake, steer, and speed guard", proc.stdout)
            for target in (source, build):
                payload = target.read_text(encoding="utf-8")
                self.assertIn("PIX_CARLA_SPEED_GUARD_MAX_MPS", payload)
                self.assertIn("overspeed_mps", payload)

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
