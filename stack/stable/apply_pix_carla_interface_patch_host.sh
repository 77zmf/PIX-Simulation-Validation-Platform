#!/usr/bin/env bash
set -euo pipefail

AUTOWARE_WS="${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/autoware}"
PRIVATE_AUTOWARE_WS="${PRIVATE_AUTOWARE_WS:-}"
ROLLBACK=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Apply the PIX robobus Autoware CARLA interface actuation mapping patch.

Default target:
  $HOME/zmf_ws/projects/autoware_universe/autoware

Why:
  Autoware actuation accel/brake/steer commands are not a calibrated PIX
  robobus CARLA VehicleControl mapping by themselves. The stable launcher
  exports PIX_CARLA_* gains and limits; this patch makes the bridge consume
  them, including:
  - throttle gain/min/max/creep
  - brake gain/max/deadband
  - optional target-speed-aware brake suppression using Autoware control_cmd context
  - steer radians-to-normalized conversion plus steer gain
  - explicit low-speed brake-to-creep guard for CARLA-only final-approach deadlocks
  - first-order steering hold when ROS callbacks arrive faster than CARLA ticks
  - ROS-time vehicle status stamps so Autoware component_state_monitor does
    not treat CARLA elapsed-time vehicle reports as stale in planning_simulation
  - simulation-tolerant vehicle status topic-rate thresholds so CARLA bridge
    velocity/steering status jitter does not block autonomous availability
  - unique static TF node names so Autoware duplicated_node_checker does not
    block autonomous mode on generic /imu or /velodyne_top node names
  - unique raw vehicle converter node name so the CARLA bridge converter does
    not collide with Autoware's vehicle-side converter

Validation:
  Run scenarios/l0/robobus117th_town01_closed_loop.yaml with simctl --execute.
  Compare /control/command/actuation_cmd against
  /vehicle/status/actuation_status and verify route movement improves without
  losing steering-status consistency.

Rollback:
  Re-run this script with --rollback, or restore the generated .bak file.

Options:
  --autoware-ws PATH  Autoware workspace root.
  --private-autoware-ws PATH
                       Optional private Autoware underlay workspace root.
                       Defaults to the sibling private_autoware directory.
  --dry-run           Check target files without writing.
  --rollback          Restore backups created by this script.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --autoware-ws) AUTOWARE_WS="$2"; shift 2 ;;
    --private-autoware-ws) PRIVATE_AUTOWARE_WS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --rollback) ROLLBACK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$PRIVATE_AUTOWARE_WS" ]]; then
  PRIVATE_AUTOWARE_WS="$(dirname "${AUTOWARE_WS}")/private_autoware"
fi

SOURCE_FILE="${AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/src/autoware_carla_interface/carla_ros.py"
BUILD_FILE="${AUTOWARE_WS}/build/autoware_carla_interface/src/autoware_carla_interface/carla_ros.py"
INSTALL_FILE="${AUTOWARE_WS}/install/autoware_carla_interface/lib/python3.10/site-packages/autoware_carla_interface/carla_ros.py"
PRIVATE_SOURCE_FILE="${PRIVATE_AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/src/autoware_carla_interface/carla_ros.py"
PRIVATE_BUILD_FILE="${PRIVATE_AUTOWARE_WS}/build/autoware_carla_interface/src/autoware_carla_interface/carla_ros.py"
PRIVATE_INSTALL_FILE="${PRIVATE_AUTOWARE_WS}/install/autoware_carla_interface/lib/python3.10/site-packages/autoware_carla_interface/carla_ros.py"
SOURCE_BRIDGE_LOOP_FILE="${AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/src/autoware_carla_interface/carla_autoware.py"
BUILD_BRIDGE_LOOP_FILE="${AUTOWARE_WS}/build/autoware_carla_interface/src/autoware_carla_interface/carla_autoware.py"
INSTALL_BRIDGE_LOOP_FILE="${AUTOWARE_WS}/install/autoware_carla_interface/lib/python3.10/site-packages/autoware_carla_interface/carla_autoware.py"
PRIVATE_SOURCE_BRIDGE_LOOP_FILE="${PRIVATE_AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/src/autoware_carla_interface/carla_autoware.py"
PRIVATE_BUILD_BRIDGE_LOOP_FILE="${PRIVATE_AUTOWARE_WS}/build/autoware_carla_interface/src/autoware_carla_interface/carla_autoware.py"
PRIVATE_INSTALL_BRIDGE_LOOP_FILE="${PRIVATE_AUTOWARE_WS}/install/autoware_carla_interface/lib/python3.10/site-packages/autoware_carla_interface/carla_autoware.py"
SOURCE_WRAPPER_FILE="${AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/src/autoware_carla_interface/modules/carla_wrapper.py"
BUILD_WRAPPER_FILE="${AUTOWARE_WS}/build/autoware_carla_interface/src/autoware_carla_interface/modules/carla_wrapper.py"
INSTALL_WRAPPER_FILE="${AUTOWARE_WS}/install/autoware_carla_interface/lib/python3.10/site-packages/autoware_carla_interface/modules/carla_wrapper.py"
PRIVATE_SOURCE_WRAPPER_FILE="${PRIVATE_AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/src/autoware_carla_interface/modules/carla_wrapper.py"
PRIVATE_BUILD_WRAPPER_FILE="${PRIVATE_AUTOWARE_WS}/build/autoware_carla_interface/src/autoware_carla_interface/modules/carla_wrapper.py"
PRIVATE_INSTALL_WRAPPER_FILE="${PRIVATE_AUTOWARE_WS}/install/autoware_carla_interface/lib/python3.10/site-packages/autoware_carla_interface/modules/carla_wrapper.py"
SOURCE_UTILS_FILE="${AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/src/autoware_carla_interface/modules/carla_utils.py"
BUILD_UTILS_FILE="${AUTOWARE_WS}/build/autoware_carla_interface/src/autoware_carla_interface/modules/carla_utils.py"
INSTALL_UTILS_FILE="${AUTOWARE_WS}/install/autoware_carla_interface/lib/python3.10/site-packages/autoware_carla_interface/modules/carla_utils.py"
PRIVATE_SOURCE_UTILS_FILE="${PRIVATE_AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/src/autoware_carla_interface/modules/carla_utils.py"
PRIVATE_BUILD_UTILS_FILE="${PRIVATE_AUTOWARE_WS}/build/autoware_carla_interface/src/autoware_carla_interface/modules/carla_utils.py"
PRIVATE_INSTALL_UTILS_FILE="${PRIVATE_AUTOWARE_WS}/install/autoware_carla_interface/lib/python3.10/site-packages/autoware_carla_interface/modules/carla_utils.py"
SOURCE_LAUNCH_FILE="${AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/launch/autoware_carla_interface.launch.xml"
INSTALL_LAUNCH_FILE="${AUTOWARE_WS}/install/autoware_carla_interface/share/autoware_carla_interface/autoware_carla_interface.launch.xml"
PRIVATE_SOURCE_LAUNCH_FILE="${PRIVATE_AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/launch/autoware_carla_interface.launch.xml"
PRIVATE_INSTALL_LAUNCH_FILE="${PRIVATE_AUTOWARE_WS}/install/autoware_carla_interface/share/autoware_carla_interface/autoware_carla_interface.launch.xml"
SOURCE_COMPONENT_TOPICS_FILE="${AUTOWARE_WS}/src/launcher/autoware_launch/autoware_launch/config/system/component_state_monitor/topics.yaml"
INSTALL_COMPONENT_TOPICS_FILE="${AUTOWARE_WS}/install/autoware_launch/share/autoware_launch/config/system/component_state_monitor/topics.yaml"
PRIVATE_SOURCE_COMPONENT_TOPICS_FILE="${PRIVATE_AUTOWARE_WS}/src/launcher/autoware_launch/autoware_launch/config/system/component_state_monitor/topics.yaml"
PRIVATE_INSTALL_COMPONENT_TOPICS_FILE="${PRIVATE_AUTOWARE_WS}/install/autoware_launch/share/autoware_launch/config/system/component_state_monitor/topics.yaml"
BACKUP_SUFFIX=".pix_actuation_map.bak"
BRIDGE_LOOP_BACKUP_SUFFIX=".pix_sensor_timeout_tolerance.bak"
WRAPPER_BACKUP_SUFFIX=".pix_sensor_queue_timeout.bak"
UTILS_BACKUP_SUFFIX=".pix_ros_y_sign.bak"
LAUNCH_BACKUP_SUFFIX=".pix_static_tf_node_names.bak"
COMPONENT_TOPICS_BACKUP_SUFFIX=".pix_vehicle_topic_rate.bak"

python3 - "$BACKUP_SUFFIX" "$ROLLBACK" "$DRY_RUN" \
  "$SOURCE_FILE" \
  "$BUILD_FILE" \
  "$INSTALL_FILE" \
  "$PRIVATE_SOURCE_FILE" \
  "$PRIVATE_BUILD_FILE" \
  "$PRIVATE_INSTALL_FILE" <<'PY'
from __future__ import annotations

import re
import py_compile
import sys
from pathlib import Path

backup_suffix = sys.argv[1]
rollback = sys.argv[2] == "1"
dry_run = sys.argv[3] == "1"
candidate_paths = [Path(arg) for arg in sys.argv[4:]]
targets: list[Path] = []
for path in candidate_paths:
    if path.exists() and path not in targets:
        targets.append(path)

if not targets:
    print("actuation patch skipped: autoware_carla_interface carla_ros.py not found")
    raise SystemExit(0)

marker = "PIX_CARLA_ACTUATION_MAP_PATCH"
steer_hold_marker = "PIX_CARLA_STEER_HOLD_PATCH"
wheel_steer_marker = "PIX_CARLA_SKIP_WHEEL_STEER_ANGLE_PATCH"
status_stamp_marker = "PIX_CARLA_STATUS_ROS_TIME_PATCH"
control_cmd_context_marker = "PIX_CARLA_CONTROL_CMD_CONTEXT_PATCH"
angular_velocity_marker = "PIX_CARLA_ANGULAR_VELOCITY_RAD_PATCH"
steer_method_pattern = re.compile(
    r"    def first_order_steering\(self, steer_input\):\n.*?\n    def control_callback\(self, in_cmd\):",
    re.DOTALL,
)
method_pattern = re.compile(
    r"(?:    def control_cmd_callback\(self, in_cmd\):\n.*?\n\n)?"
    r"    def control_callback\(self, in_cmd\):\n.*?\n    def ego_status\(self\):",
    re.DOTALL,
)
wheel_steer_pattern = re.compile(
    r"        out_steering_state\.steering_tire_angle = -math\.radians\(\n"
    r"            self\.ego_actor\.get_wheel_steer_angle\(carla\.VehicleWheelLocation\.FL_Wheel\)\n"
    r"        \)",
)
legacy_constant_wheel_steer_pattern = re.compile(
    r"        # PIX_CARLA_SKIP_WHEEL_STEER_ANGLE_PATCH:.*?\n"
    r"        out_steering_state\.steering_tire_angle = 0\.0",
    re.DOTALL,
)
control_subscription_pattern = re.compile(
    r"        self\.sub_control = self\.ros2_node\.create_subscription\(\n"
    r"            ActuationCommandStamped, \"/control/command/actuation_cmd\", self\.control_callback, 1\n"
    r"        \)\n",
)
heading_rate_pattern = re.compile(
    r"        out_vel_state\.heading_rate = \(\n"
    r"            self\.ego_actor\.get_transform\(\)\.transform_vector\(self\.ego_actor\.get_angular_velocity\(\)\)\.z\n"
    r"        \)"
)
patched_steer_method = '''    def first_order_steering(self, steer_input):
        """First order steering model."""
        # PIX_CARLA_STEER_HOLD_PATCH: keep the previous steering output when
        # ROS control callbacks arrive multiple times inside the same CARLA tick.
        steer_output = self.prev_steer_output
        if self.timestamp is None:
            return steer_output
        if self.prev_timestamp is None:
            self.prev_timestamp = self.timestamp

        dt = self.timestamp - self.prev_timestamp
        if dt > 0.0:
            try:
                steer_tau = float(os.environ.get("PIX_CARLA_STEER_TAU", str(self.tau)) or str(self.tau))
            except ValueError:
                steer_tau = self.tau
            steer_tau = max(float(steer_tau), 0.0)
            steer_output = self.prev_steer_output + (steer_input - self.prev_steer_output) * (
                dt / (steer_tau + dt)
            )
            self.prev_steer_output = steer_output
            self.prev_timestamp = self.timestamp
        return steer_output

    def control_callback(self, in_cmd):'''
patched_method = '''    def control_cmd_callback(self, in_cmd):
        """Cache Autoware control command context for CARLA actuation mapping."""
        # PIX_CARLA_CONTROL_CMD_CONTEXT_PATCH: actuation_cmd alone cannot tell
        # whether a small brake command is a true stop or a final-approach
        # crawl while Autoware still publishes positive target velocity.
        self.latest_control_cmd = in_cmd

    def control_callback(self, in_cmd):
        """Convert and publish CARLA Ego Vehicle Control to AUTOWARE."""
        # PIX_CARLA_ACTUATION_MAP_PATCH: apply PIX robobus CARLA actuation calibration.
        def _env_float(name, default):
            try:
                return float(os.environ.get(name, str(default)) or str(default))
            except ValueError:
                return float(default)

        out_cmd = carla.VehicleControl()
        current_vel = self.ego_actor.get_velocity()
        ego_speed_mps = math.sqrt(
            current_vel.x * current_vel.x
            + current_vel.y * current_vel.y
            + current_vel.z * current_vel.z
        )

        raw_throttle = max(float(in_cmd.actuation.accel_cmd), 0.0)
        raw_brake = max(float(in_cmd.actuation.brake_cmd), 0.0)
        requested_brake = raw_brake
        latest_control_cmd = getattr(self, "latest_control_cmd", None)
        target_velocity_mps = None
        if latest_control_cmd is not None:
            longitudinal = getattr(latest_control_cmd, "longitudinal", None)
            if longitudinal is not None:
                try:
                    target_velocity_mps = float(getattr(longitudinal, "velocity"))
                except (TypeError, ValueError):
                    target_velocity_mps = None
        throttle_gain = _env_float("PIX_CARLA_THROTTLE_GAIN", 1.0)
        min_throttle = _env_float("PIX_CARLA_MIN_THROTTLE", 0.0)
        max_throttle = _env_float("PIX_CARLA_MAX_THROTTLE", 1.0)
        creep_throttle = _env_float("PIX_CARLA_CREEP_THROTTLE", 0.0)
        creep_speed_threshold = _env_float("PIX_CARLA_CREEP_SPEED_THRESHOLD_MPS", 0.08)
        brake_gain = _env_float("PIX_CARLA_BRAKE_GAIN", 1.0)
        max_brake = _env_float("PIX_CARLA_MAX_BRAKE", 1.0)
        brake_deadband = _env_float("PIX_CARLA_BRAKE_DEADBAND", 0.0)
        brake_creep_throttle = _env_float("PIX_CARLA_BRAKE_CREEP_THROTTLE", 0.0)
        brake_creep_max_brake_cmd = _env_float("PIX_CARLA_BRAKE_CREEP_MAX_BRAKE_CMD", 0.0)
        brake_creep_speed_threshold = _env_float(
            "PIX_CARLA_BRAKE_CREEP_SPEED_THRESHOLD_MPS",
            creep_speed_threshold,
        )
        brake_creep_min_target_velocity = _env_float(
            "PIX_CARLA_BRAKE_CREEP_MIN_TARGET_VELOCITY_MPS",
            0.05,
        )
        suppress_brake_below_target = _env_float("PIX_CARLA_SUPPRESS_BRAKE_BELOW_TARGET", 0.0)
        brake_target_speed_margin = _env_float("PIX_CARLA_BRAKE_TARGET_SPEED_MARGIN_MPS", 0.2)
        target_speed_brake_max_cmd = _env_float("PIX_CARLA_TARGET_SPEED_BRAKE_MAX_CMD", 0.25)
        speed_guard_max_mps = _env_float("PIX_CARLA_SPEED_GUARD_MAX_MPS", 0.0)
        speed_guard_band_mps = max(_env_float("PIX_CARLA_SPEED_GUARD_BAND_MPS", 1.0), 0.01)
        speed_guard_brake_gain = _env_float("PIX_CARLA_SPEED_GUARD_BRAKE_GAIN", 0.0)

        throttle = raw_throttle * throttle_gain
        if raw_throttle > 0.0 and throttle < min_throttle:
            throttle = min_throttle
        if raw_throttle > 0.0 and ego_speed_mps <= creep_speed_threshold:
            throttle = max(throttle, creep_throttle)
        throttle = min(max(throttle, 0.0), max_throttle)

        if (
            suppress_brake_below_target > 0.0
            and target_velocity_mps is not None
            and target_velocity_mps > ego_speed_mps + brake_target_speed_margin
            and 0.0 < requested_brake <= target_speed_brake_max_cmd
        ):
            raw_brake = 0.0

        brake = 0.0 if raw_brake < brake_deadband else raw_brake * brake_gain
        brake = min(max(brake, 0.0), max_brake)
        if (
            raw_throttle <= 0.0
            and brake_creep_throttle > 0.0
            and brake_creep_max_brake_cmd > 0.0
            and 0.0 < requested_brake <= brake_creep_max_brake_cmd
            and ego_speed_mps <= brake_creep_speed_threshold
            and target_velocity_mps is not None
            and target_velocity_mps >= brake_creep_min_target_velocity
        ):
            # PIX_CARLA_BRAKE_CREEP_PATCH: CARLA can stall at low speed when
            # Autoware asks for a small final-approach brake while still
            # publishing a positive crawl-speed trajectory. Keep this
            # scenario-configured and default-off so real stop commands remain
            # authoritative.
            brake = 0.0
            throttle = max(throttle, brake_creep_throttle)
        if speed_guard_max_mps > 0.0:
            speed_guard_start_mps = max(speed_guard_max_mps - speed_guard_band_mps, 0.0)
            if ego_speed_mps >= speed_guard_max_mps:
                throttle = 0.0
                overspeed_mps = ego_speed_mps - speed_guard_max_mps
                if speed_guard_brake_gain > 0.0 and overspeed_mps > 0.0:
                    brake = max(brake, min(overspeed_mps * speed_guard_brake_gain, max_brake))
            elif ego_speed_mps > speed_guard_start_mps:
                guard_scale = (speed_guard_max_mps - ego_speed_mps) / (
                    speed_guard_max_mps - speed_guard_start_mps
                )
                throttle *= min(max(guard_scale, 0.0), 1.0)
        if brake > 0.0:
            throttle = 0.0

        out_cmd.throttle = throttle

        # convert base on steer curve of the vehicle
        steer_curve = self.physics_control.steering_curve
        max_steer_ratio = numpy.interp(
            abs(current_vel.x), [v.x for v in steer_curve], [v.y for v in steer_curve]
        )
        max_steer_angle_deg = 0.0
        if self.physics_control and getattr(self.physics_control, "wheels", None):
            wheel_limits = [
                abs(float(getattr(wheel, "max_steer_angle", 0.0)))
                for wheel in self.physics_control.wheels
                if abs(float(getattr(wheel, "max_steer_angle", 0.0))) > 1e-3
            ]
            if wheel_limits:
                max_steer_angle_deg = max(wheel_limits)
        max_steer_angle_rad = math.radians(max_steer_angle_deg)
        steer_cmd_rad = float(in_cmd.actuation.steer_cmd)
        if max_steer_angle_rad > 1e-6:
            steer_input = -steer_cmd_rad / max_steer_angle_rad
        else:
            steer_input = -steer_cmd_rad
        steer_gain = _env_float("PIX_CARLA_STEER_GAIN", 1.0)
        steer_abs_limit = min(max(abs(_env_float("PIX_CARLA_STEER_ABS_LIMIT", 1.0)), 0.0), 1.0)
        raw_steer_output = self.first_order_steering(steer_input * steer_gain) * max_steer_ratio
        out_cmd.steer = min(max(raw_steer_output, -steer_abs_limit), steer_abs_limit)
        out_cmd.brake = brake
        self.current_control = out_cmd

    def ego_status(self):'''
patched_wheel_steer = '''        # PIX_CARLA_SKIP_WHEEL_STEER_ANGLE_PATCH: some PIX CARLA builds block on
        # get_wheel_steer_angle after custom-map sensor spawning. Allow the
        # stable launcher to publish a neutral steering report instead.
        if os.environ.get("PIX_CARLA_SKIP_WHEEL_STEER_ANGLE", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
            out_steering_state.steering_tire_angle = 0.0
        else:
            try:
                steering_report_sign = float(os.environ.get("PIX_CARLA_STEERING_REPORT_SIGN", "-1.0") or "-1.0")
            except ValueError:
                steering_report_sign = -1.0
            out_steering_state.steering_tire_angle = steering_report_sign * math.radians(
                self.ego_actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FL_Wheel)
            )'''
status_stamp_target = '        out_vel_state.header = self.get_msg_header(frame_id="base_link")\n'
patched_status_stamp = '''        out_vel_state.header = self.get_msg_header(frame_id="base_link")
        # PIX_CARLA_STATUS_ROS_TIME_PATCH: Autoware component_state_monitor
        # compares vehicle status stamps against the node clock. In the stable
        # planning_simulation stack, CARLA elapsed-time stamps look stale.
        if os.environ.get("PIX_CARLA_STATUS_USE_ROS_TIME", "1").strip().lower() not in {"0", "false", "no", "n", "off"}:
            out_vel_state.header.stamp = self.ros2_node.get_clock().now().to_msg()
'''
actuation_status_stamp_target = '        out_actuation_status.header = self.get_msg_header(frame_id="base_link")\n'
patched_actuation_status_stamp = '''        out_actuation_status.header = self.get_msg_header(frame_id="base_link")
        if os.environ.get("PIX_CARLA_STATUS_USE_ROS_TIME", "1").strip().lower() not in {"0", "false", "no", "n", "off"}:
            out_actuation_status.header.stamp = out_vel_state.header.stamp
'''
patched_heading_rate = '''        # PIX_CARLA_ANGULAR_VELOCITY_RAD_PATCH: CARLA exposes vehicle angular
        # velocity in degrees/sec, while Autoware VelocityReport.heading_rate
        # and nav_msgs/Odometry.twist.angular.z expect radians/sec.
        out_vel_state.heading_rate = math.radians(
            self.ego_actor.get_transform().transform_vector(self.ego_actor.get_angular_velocity()).z
        )'''

for path in targets:
    if not path.exists():
        raise SystemExit(f"target file not found: {path}")

    backup = Path(str(path) + backup_suffix)
    text = path.read_text()

    if rollback:
        if not backup.exists():
            print(f"no backup to restore: {backup}")
            continue
        if dry_run:
            print(f"would restore: {backup} -> {path}")
            continue
        path.write_text(backup.read_text())
        py_compile.compile(str(path), doraise=True)
        print(f"restored: {path}")
        continue

    patched_text = text
    patch_descriptions = []

    if steer_hold_marker not in patched_text or "PIX_CARLA_STEER_TAU" not in patched_text:
        steer_match = steer_method_pattern.search(patched_text)
        if not steer_match:
            raise SystemExit(f"steering target block not found: {path}")
        patched_text = patched_text[: steer_match.start()] + patched_steer_method + patched_text[steer_match.end() :]
        if steer_hold_marker in text:
            patch_descriptions.append("upgraded steering hold with configurable response tau")
        else:
            patch_descriptions.append("held steering output across same-tick callbacks")

    if (
        marker not in patched_text
        or "PIX_CARLA_SPEED_GUARD_MAX_MPS" not in patched_text
        or "PIX_CARLA_BRAKE_CREEP_PATCH" not in patched_text
        or control_cmd_context_marker not in patched_text
        or "PIX_CARLA_STEER_ABS_LIMIT" not in patched_text
        or "def control_cmd_callback" not in patched_text
        or "self.latest_control_cmd = in_cmd" not in patched_text
        or "requested_brake = raw_brake" not in patched_text
        or patched_text.count("def control_cmd_callback") > 1
    ):
        match = method_pattern.search(patched_text)
        if not match:
            raise SystemExit(f"actuation target block not found: {path}")
        patched_text = patched_text[: match.start()] + patched_method + patched_text[match.end() :]
        if marker in text:
            patch_descriptions.append("upgraded calibrated throttle, brake, steer, and speed guard")
        else:
            patch_descriptions.append("calibrated throttle, brake, steer, and speed guard")

    if wheel_steer_marker not in patched_text or "PIX_CARLA_STEERING_REPORT_SIGN" not in patched_text:
        wheel_patch_count = 0
        if wheel_steer_marker in patched_text and "PIX_CARLA_STEERING_REPORT_SIGN" not in patched_text:
            old_wheel_steer = '''        # PIX_CARLA_SKIP_WHEEL_STEER_ANGLE_PATCH: some PIX CARLA builds block on
        # get_wheel_steer_angle after custom-map sensor spawning. Allow the
        # stable launcher to publish a neutral steering report instead.
        if os.environ.get("PIX_CARLA_SKIP_WHEEL_STEER_ANGLE", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
            out_steering_state.steering_tire_angle = 0.0
        else:
            out_steering_state.steering_tire_angle = -math.radians(
                self.ego_actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FL_Wheel)
            )'''
            if old_wheel_steer in patched_text:
                patched_text = patched_text.replace(old_wheel_steer, patched_wheel_steer, 1)
                wheel_patch_count = 1
            else:
                patched_text, wheel_patch_count = legacy_constant_wheel_steer_pattern.subn(
                    patched_wheel_steer,
                    patched_text,
                    count=1,
                )
            if not wheel_patch_count:
                raise SystemExit(f"wheel steer status upgrade block not found: {path}")
        else:
            patched_text, wheel_patch_count = wheel_steer_pattern.subn(patched_wheel_steer, patched_text, count=1)
        if wheel_patch_count:
            patch_descriptions.append("guarded wheel steer status query")

    if status_stamp_marker not in patched_text:
        if status_stamp_target not in patched_text:
            raise SystemExit(f"vehicle status stamp target block not found: {path}")
        patched_text = patched_text.replace(status_stamp_target, patched_status_stamp, 1)
        if actuation_status_stamp_target not in patched_text:
            raise SystemExit(f"actuation status stamp target block not found: {path}")
        patched_text = patched_text.replace(actuation_status_stamp_target, patched_actuation_status_stamp, 1)
        patch_descriptions.append("stamped vehicle status with ROS node time")

    if angular_velocity_marker not in patched_text and "out_vel_state.heading_rate" in patched_text:
        heading_rate_match = heading_rate_pattern.search(patched_text)
        if not heading_rate_match:
            raise SystemExit(f"heading rate target block not found: {path}")
        patched_text = (
            patched_text[: heading_rate_match.start()]
            + patched_heading_rate
            + patched_text[heading_rate_match.end() :]
        )
        patch_descriptions.append("converted CARLA angular velocity degrees/sec to ROS radians/sec")

    if "PIX_CARLA_ACTUATION_STEER_STATUS_SIGN" not in patched_text:
        old_status = "        out_actuation_status.status.steer_status = -control.steer\n"
        new_status = '''        try:
            actuation_steer_status_sign = float(os.environ.get("PIX_CARLA_ACTUATION_STEER_STATUS_SIGN", "-1.0") or "-1.0")
        except ValueError:
            actuation_steer_status_sign = -1.0
        out_actuation_status.status.steer_status = actuation_steer_status_sign * control.steer
'''
        if old_status not in patched_text:
            if "out_actuation_status.status.steer_status" not in patched_text:
                old_status = ""
            else:
                raise SystemExit(f"actuation steer status sign target block not found: {path}")
        if old_status:
            patched_text = patched_text.replace(old_status, new_status, 1)
            patch_descriptions.append("made actuation steer status sign scenario-configurable")

    if not patch_descriptions:
        print(f"already patched: {path}")
        continue

    if "import os\n" not in patched_text:
        if "import math\n" not in patched_text:
            raise SystemExit(f"cannot add os import: {path}")
        patched_text = patched_text.replace("import math\n", "import math\nimport os\n", 1)

    if "from autoware_control_msgs.msg import Control\n" not in patched_text:
        if "from tier4_vehicle_msgs.msg import ActuationCommandStamped\n" in patched_text:
            patched_text = patched_text.replace(
                "from tier4_vehicle_msgs.msg import ActuationCommandStamped\n",
                "from autoware_control_msgs.msg import Control\n"
                "from tier4_vehicle_msgs.msg import ActuationCommandStamped\n",
                1,
            )
        elif "import os\n" in patched_text:
            patched_text = patched_text.replace(
                "import os\n",
                "import os\nfrom autoware_control_msgs.msg import Control\n",
                1,
            )
        else:
            raise SystemExit(f"cannot add Control import: {path}")

    if "self.sub_control_cmd = self.ros2_node.create_subscription(" not in patched_text:
        match = control_subscription_pattern.search(patched_text)
        if match:
            subscription_target = match.group(0)
            subscription_patch = (
                subscription_target
                + "        # PIX_CARLA_CONTROL_CMD_CONTEXT_PATCH: keep target-speed context\n"
                + "        # next to actuation_cmd so CARLA brake mapping can avoid\n"
                + "        # simulation-only deadlocks and speed-contradictory braking.\n"
                + "        self.latest_control_cmd = None\n"
                + "        self.sub_control_cmd = self.ros2_node.create_subscription(\n"
                + "            Control, \"/control/command/control_cmd\", self.control_cmd_callback, 1\n"
                + "        )\n"
            )
            patched_text = patched_text[: match.start()] + subscription_patch + patched_text[match.end() :]
        elif "self.latest_control_cmd = None" not in patched_text:
            print(f"warning: control command subscription target block not found: {path}")

    if dry_run:
        print(f"would patch ({'; '.join(patch_descriptions)}): {path}")
        continue

    if not backup.exists():
        backup.write_text(text)
        print(f"backup: {backup}")

    path.write_text(patched_text)
    py_compile.compile(str(path), doraise=True)
    print(f"patched ({'; '.join(patch_descriptions)}): {path}")
PY

echo "Patch operation completed."

python3 - "$WRAPPER_BACKUP_SUFFIX" "$ROLLBACK" "$DRY_RUN" \
  "$SOURCE_WRAPPER_FILE" \
  "$BUILD_WRAPPER_FILE" \
  "$INSTALL_WRAPPER_FILE" \
  "$PRIVATE_SOURCE_WRAPPER_FILE" \
  "$PRIVATE_BUILD_WRAPPER_FILE" \
  "$PRIVATE_INSTALL_WRAPPER_FILE" <<'PY'
from __future__ import annotations

import py_compile
import re
import sys
from pathlib import Path

backup_suffix = sys.argv[1]
rollback = sys.argv[2] == "1"
dry_run = sys.argv[3] == "1"
candidate_paths = [Path(arg) for arg in sys.argv[4:]]
targets: list[Path] = []
for path in candidate_paths:
    if path.exists() and path not in targets:
        targets.append(path)

if not targets:
    print("wrapper patch skipped: autoware_carla_interface carla_wrapper.py not found")
    raise SystemExit(0)

marker = "PIX_CARLA_SENSOR_QUEUE_TIMEOUT_PATCH"
timeout_pattern = re.compile(r"        self\._queue_timeout = 10\n")
patched_timeout = '''        # PIX_CARLA_SENSOR_QUEUE_TIMEOUT_PATCH: allow heavy custom-map sensor
        # bundles to tolerate intermittent CARLA sensor delivery stalls.
        try:
            self._queue_timeout = float(os.environ.get("PIX_CARLA_SENSOR_QUEUE_TIMEOUT_SEC", "10") or "10")
        except ValueError:
            self._queue_timeout = 10
'''

for path in targets:
    if not path.exists():
        raise SystemExit(f"wrapper target file not found: {path}")

    backup = Path(str(path) + backup_suffix)
    text = path.read_text()

    if rollback:
        if not backup.exists():
            print(f"no wrapper backup to restore: {backup}")
            continue
        if dry_run:
            print(f"would restore wrapper: {backup} -> {path}")
            continue
        path.write_text(backup.read_text())
        py_compile.compile(str(path), doraise=True)
        print(f"restored wrapper: {path}")
        continue

    patched_text = text
    if marker in patched_text:
        print(f"wrapper already patched: {path}")
        continue

    patched_text, patch_count = timeout_pattern.subn(patched_timeout, patched_text, count=1)
    if not patch_count:
        raise SystemExit(f"sensor queue timeout target block not found: {path}")

    if "import os\n" not in patched_text:
        if "import numpy as np\n" in patched_text:
            patched_text = patched_text.replace("import numpy as np\n", "import os\nimport numpy as np\n", 1)
        elif "from queue import Empty, Queue\n" in patched_text:
            patched_text = patched_text.replace("from queue import Empty, Queue\n", "import os\nfrom queue import Empty, Queue\n", 1)
        else:
            raise SystemExit(f"cannot add os import to wrapper: {path}")

    if dry_run:
        print(f"would patch wrapper sensor queue timeout: {path}")
        continue

    if not backup.exists():
        backup.write_text(text)
        print(f"wrapper backup: {backup}")

    path.write_text(patched_text)
    py_compile.compile(str(path), doraise=True)
    print(f"patched wrapper sensor queue timeout: {path}")
PY

echo "Wrapper patch operation completed."

python3 - "$UTILS_BACKUP_SUFFIX" "$ROLLBACK" "$DRY_RUN" \
  "$SOURCE_UTILS_FILE" \
  "$BUILD_UTILS_FILE" \
  "$INSTALL_UTILS_FILE" \
  "$PRIVATE_SOURCE_UTILS_FILE" \
  "$PRIVATE_BUILD_UTILS_FILE" \
  "$PRIVATE_INSTALL_UTILS_FILE" <<'PY'
from __future__ import annotations

import py_compile
import re
import sys
from pathlib import Path

backup_suffix = sys.argv[1]
rollback = sys.argv[2] == "1"
dry_run = sys.argv[3] == "1"
candidate_paths = [Path(arg) for arg in sys.argv[4:]]
targets: list[Path] = []
for path in candidate_paths:
    if path.exists() and path not in targets:
        targets.append(path)

if not targets:
    print("utils patch skipped: autoware_carla_interface carla_utils.py not found")
    raise SystemExit(0)

marker = "PIX_CARLA_ROS_Y_SIGN_PATCH"
location_pattern = re.compile(
    r"def carla_location_to_ros_point\(carla_location\):\n"
    r"    \"\"\"Convert a carla location to a ROS point\.\"\"\"\n"
    r"    ros_point = Point\(\)\n"
    r"    ros_point\.x = carla_location\.x\n"
    r"    ros_point\.y = -carla_location\.y\n"
    r"    ros_point\.z = carla_location\.z\n"
    r"\n"
    r"    return ros_point\n",
)
rotation_pattern = re.compile(
    r"def carla_rotation_to_ros_quaternion\(carla_rotation\):\n"
    r"    \"\"\"Convert a carla rotation to a ROS quaternion\.\"\"\"\n"
    r"    roll = math\.radians\(carla_rotation\.roll\)\n"
    r"    pitch = -math\.radians\(carla_rotation\.pitch\)\n"
    r"    yaw = -math\.radians\(carla_rotation\.yaw\)\n"
    r"    quat = euler2quat\(roll, pitch, yaw\)\n"
    r"    ros_quaternion = Quaternion\(w=quat\[0\], x=quat\[1\], y=quat\[2\], z=quat\[3\]\)\n"
    r"\n"
    r"    return ros_quaternion\n",
)
ros_rotation_pattern = re.compile(
    r"def ros_quaternion_to_carla_rotation\(ros_quaternion\):\n"
    r"    \"\"\"Convert ROS quaternion to (?:CARLA|carla) rotation\.\"\"\"\n"
    r"    roll, pitch, yaw = quat2euler\(\n"
    r"        \[ros_quaternion\.w, ros_quaternion\.x, ros_quaternion\.y, ros_quaternion\.z\]\n"
    r"    \)\n"
    r"\n"
    r"    return carla\.Rotation\(\n"
    r"        roll=math\.degrees\(roll\), pitch=-math\.degrees\(pitch\), yaw=-math\.degrees\(yaw\)\n"
    r"    \)\n",
)
pose_pattern = re.compile(
    r"def ros_pose_to_carla_transform\(ros_pose\):\n"
    r"    \"\"\"Convert ROS pose to carla transform\.\"\"\"\n"
    r"    return carla\.Transform\(\n"
    r"        carla\.Location\(ros_pose\.position\.x, -ros_pose\.position\.y, ros_pose\.position\.z\),\n"
    r"        ros_quaternion_to_carla_rotation\(ros_pose\.orientation\),\n"
    r"    \)\n",
)
patched_helper = '''def pix_carla_ros_y_sign():
    # PIX_CARLA_ROS_Y_SIGN_PATCH: CARLA's default ROS bridge flips y. Some
    # imported public-road XODR/lanelet bundles are already in the same y axis
    # as CARLA and need PIX_CARLA_ROS_Y_SIGN=1 at scenario scope.
    value = os.environ.get("PIX_CARLA_ROS_Y_SIGN", "-1").strip().lower()
    return 1.0 if value in {"1", "+1", "same", "positive", "carla"} else -1.0


'''
patched_location = '''def carla_location_to_ros_point(carla_location):
    """Convert a carla location to a ROS point."""
    y_sign = pix_carla_ros_y_sign()
    ros_point = Point()
    ros_point.x = carla_location.x
    ros_point.y = y_sign * carla_location.y
    ros_point.z = carla_location.z

    return ros_point
'''
patched_rotation = '''def carla_rotation_to_ros_quaternion(carla_rotation):
    """Convert a carla rotation to a ROS quaternion."""
    y_sign = pix_carla_ros_y_sign()
    roll = math.radians(carla_rotation.roll)
    pitch = y_sign * math.radians(carla_rotation.pitch)
    yaw = y_sign * math.radians(carla_rotation.yaw)
    quat = euler2quat(roll, pitch, yaw)
    ros_quaternion = Quaternion(w=quat[0], x=quat[1], y=quat[2], z=quat[3])

    return ros_quaternion
'''
patched_ros_rotation = '''def ros_quaternion_to_carla_rotation(ros_quaternion):
    """Convert ROS quaternion to carla rotation."""
    y_sign = pix_carla_ros_y_sign()
    roll, pitch, yaw = quat2euler(
        [ros_quaternion.w, ros_quaternion.x, ros_quaternion.y, ros_quaternion.z]
    )

    return carla.Rotation(
        roll=math.degrees(roll), pitch=y_sign * math.degrees(pitch), yaw=y_sign * math.degrees(yaw)
    )
'''
patched_pose = '''def ros_pose_to_carla_transform(ros_pose):
    """Convert ROS pose to carla transform."""
    y_sign = pix_carla_ros_y_sign()
    return carla.Transform(
        carla.Location(ros_pose.position.x, y_sign * ros_pose.position.y, ros_pose.position.z),
        ros_quaternion_to_carla_rotation(ros_pose.orientation),
    )
'''

for path in targets:
    if not path.exists():
        raise SystemExit(f"utils target file not found: {path}")

    backup = Path(str(path) + backup_suffix)
    text = path.read_text()

    if rollback:
        if not backup.exists():
            print(f"no utils backup to restore: {backup}")
            continue
        if dry_run:
            print(f"would restore utils: {backup} -> {path}")
            continue
        path.write_text(backup.read_text())
        py_compile.compile(str(path), doraise=True)
        print(f"restored utils: {path}")
        continue

    if marker in text:
        print(f"utils already patched: {path}")
        continue

    patched_text = text
    if "import os\n" not in patched_text:
        patched_text = patched_text.replace("import math\n", "import math\nimport os\n", 1)
    patched_text = patched_text.replace("\n\ndef carla_location_to_ros_point", "\n\n" + patched_helper + "def carla_location_to_ros_point", 1)
    patched_text, location_count = location_pattern.subn(patched_location, patched_text, count=1)
    patched_text, rotation_count = rotation_pattern.subn(patched_rotation, patched_text, count=1)
    patched_text, ros_rotation_count = ros_rotation_pattern.subn(patched_ros_rotation, patched_text, count=1)
    patched_text, pose_count = pose_pattern.subn(patched_pose, patched_text, count=1)
    if not all((location_count, rotation_count, ros_rotation_count, pose_count)):
        raise SystemExit(f"ROS y-sign utility target block not found: {path}")

    if dry_run:
        print(f"would patch utils ROS y sign: {path}")
        continue

    if not backup.exists():
        backup.write_text(text)
        print(f"utils backup: {backup}")

    path.write_text(patched_text)
    py_compile.compile(str(path), doraise=True)
    print(f"patched utils ROS y sign: {path}")
PY

echo "Utils patch operation completed."

python3 - "$BRIDGE_LOOP_BACKUP_SUFFIX" "$ROLLBACK" "$DRY_RUN" \
  "$SOURCE_BRIDGE_LOOP_FILE" \
  "$BUILD_BRIDGE_LOOP_FILE" \
  "$INSTALL_BRIDGE_LOOP_FILE" \
  "$PRIVATE_SOURCE_BRIDGE_LOOP_FILE" \
  "$PRIVATE_BUILD_BRIDGE_LOOP_FILE" \
  "$PRIVATE_INSTALL_BRIDGE_LOOP_FILE" <<'PY'
from __future__ import annotations

import py_compile
import re
import sys
from pathlib import Path

backup_suffix = sys.argv[1]
rollback = sys.argv[2] == "1"
dry_run = sys.argv[3] == "1"
candidate_paths = [Path(arg) for arg in sys.argv[4:]]
targets: list[Path] = []
for path in candidate_paths:
    if path.exists() and path not in targets:
        targets.append(path)

if not targets:
    print("bridge loop patch skipped: autoware_carla_interface carla_autoware.py not found")
    raise SystemExit(0)

timeout_marker = "PIX_CARLA_SENSOR_TIMEOUT_TOLERANCE_PATCH"
opendrive_marker = "PIX_CARLA_OPENDRIVE_WORLD_PATCH"
physics_marker = "PIX_CARLA_RUNTIME_PHYSICS_PATCH"
raise_pattern = re.compile(
    r"(?P<indent>[ \t]+)except SensorReceivedNoData as e:\n"
    r"(?P=indent)    raise RuntimeError\(e\)\n"
)
load_world_pattern = re.compile(
    r"(?P<indent>[ \t]+)(?:"
    r"self\.world = client\.load_world\(self\.carla_map\)"
    r"|client\.load_world\(self\.carla_map\)\n(?P=indent)self\.world = client\.get_world\(\)"
    r")\n"
)
physics_assignment_pattern = re.compile(
    r"(?P<line>(?P<indent>[ \t]+)self\.interface\.physics_control = "
    r"self\.ego_actor\.get_physics_control\(\)\n)"
)


def patched_except(match: re.Match[str]) -> str:
    indent = match.group("indent")
    inner = indent + "    "
    return (
        f"{indent}except SensorReceivedNoData as e:\n"
        f"{inner}# PIX_CARLA_SENSOR_TIMEOUT_TOLERANCE_PATCH: keep the CARLA bridge\n"
        f"{inner}# ticking through intermittent heavy-map sensor stalls.\n"
        f"{inner}print(f\"PIX_CARLA_SENSOR_TIMEOUT_TOLERANCE_PATCH: {{e}}\", flush=True)\n"
        f"{inner}ego_action = self.ego_actor.get_control()\n"
    )


def patched_physics_assignment(match: re.Match[str]) -> str:
    indent = match.group("indent")
    inner = indent + "    "
    deeper = inner + "    "
    return (
        match.group("line")
        + f"{indent}# PIX_CARLA_RUNTIME_PHYSICS_PATCH: apply scenario-scoped CARLA\n"
        + f"{indent}# VehiclePhysicsControl overrides after the ego actor is spawned.\n"
        + f"{indent}def _pix_env_float(name):\n"
        + f"{inner}value = os.environ.get(name, \"\").strip()\n"
        + f"{inner}if not value:\n"
        + f"{deeper}return None\n"
        + f"{inner}try:\n"
        + f"{deeper}return float(value)\n"
        + f"{inner}except ValueError:\n"
        + f"{deeper}print(f\"PIX_CARLA_RUNTIME_PHYSICS_PATCH: ignoring invalid {{name}}={{value}}\", flush=True)\n"
        + f"{deeper}return None\n"
        + f"\n"
        + f"{indent}def _pix_env_bool(name):\n"
        + f"{inner}value = os.environ.get(name, \"\").strip().lower()\n"
        + f"{inner}if not value:\n"
        + f"{deeper}return None\n"
        + f"{inner}if value in {{\"1\", \"true\", \"yes\", \"y\", \"on\"}}:\n"
        + f"{deeper}return True\n"
        + f"{inner}if value in {{\"0\", \"false\", \"no\", \"n\", \"off\"}}:\n"
        + f"{deeper}return False\n"
        + f"{inner}print(f\"PIX_CARLA_RUNTIME_PHYSICS_PATCH: ignoring invalid {{name}}={{value}}\", flush=True)\n"
        + f"{inner}return None\n"
        + f"\n"
        + f"{indent}physics = self.interface.physics_control\n"
        + f"{indent}physics_changed = False\n"
        + f"{indent}mass_kg = _pix_env_float(\"PIX_CARLA_PHYSICS_MASS_KG\")\n"
        + f"{indent}if mass_kg is not None:\n"
        + f"{inner}physics.mass = mass_kg\n"
        + f"{inner}physics_changed = True\n"
        + f"{indent}drag = _pix_env_float(\"PIX_CARLA_PHYSICS_DRAG_COEFFICIENT\")\n"
        + f"{indent}if drag is not None:\n"
        + f"{inner}physics.drag_coefficient = drag\n"
        + f"{inner}physics_changed = True\n"
        + f"{indent}com_x = _pix_env_float(\"PIX_CARLA_PHYSICS_CENTER_OF_MASS_X_M\")\n"
        + f"{indent}com_y = _pix_env_float(\"PIX_CARLA_PHYSICS_CENTER_OF_MASS_Y_M\")\n"
        + f"{indent}com_z = _pix_env_float(\"PIX_CARLA_PHYSICS_CENTER_OF_MASS_Z_M\")\n"
        + f"{indent}if any(value is not None for value in (com_x, com_y, com_z)):\n"
        + f"{inner}current_com = getattr(physics, \"center_of_mass\", carla.Vector3D())\n"
        + f"{inner}physics.center_of_mass = carla.Vector3D(\n"
        + f"{deeper}current_com.x if com_x is None else com_x,\n"
        + f"{deeper}current_com.y if com_y is None else com_y,\n"
        + f"{deeper}current_com.z if com_z is None else com_z,\n"
        + f"{inner})\n"
        + f"{inner}physics_changed = True\n"
        + f"{indent}tire_friction = _pix_env_float(\"PIX_CARLA_PHYSICS_TIRE_FRICTION\")\n"
        + f"{indent}wheel_damping = _pix_env_float(\"PIX_CARLA_PHYSICS_WHEEL_DAMPING_RATE\")\n"
        + f"{indent}front_max_steer = _pix_env_float(\"PIX_CARLA_PHYSICS_FRONT_MAX_STEER_ANGLE_DEG\")\n"
        + f"{indent}rear_max_steer = _pix_env_float(\"PIX_CARLA_PHYSICS_REAR_MAX_STEER_ANGLE_DEG\")\n"
        + f"{indent}if getattr(physics, \"wheels\", None):\n"
        + f"{inner}for index, wheel in enumerate(physics.wheels):\n"
        + f"{deeper}if tire_friction is not None:\n"
        + f"{deeper}    wheel.tire_friction = tire_friction\n"
        + f"{deeper}    physics_changed = True\n"
        + f"{deeper}if wheel_damping is not None:\n"
        + f"{deeper}    wheel.damping_rate = wheel_damping\n"
        + f"{deeper}    physics_changed = True\n"
        + f"{deeper}if front_max_steer is not None and index < 2:\n"
        + f"{deeper}    wheel.max_steer_angle = front_max_steer\n"
        + f"{deeper}    physics_changed = True\n"
        + f"{deeper}if rear_max_steer is not None and index >= 2:\n"
        + f"{deeper}    wheel.max_steer_angle = rear_max_steer\n"
        + f"{deeper}    physics_changed = True\n"
        + f"{indent}sweep_collision = _pix_env_bool(\"PIX_CARLA_PHYSICS_USE_SWEEP_WHEEL_COLLISION\")\n"
        + f"{indent}if sweep_collision is not None:\n"
        + f"{inner}physics.use_sweep_wheel_collision = sweep_collision\n"
        + f"{inner}physics_changed = True\n"
        + f"{indent}if physics_changed:\n"
        + f"{inner}self.ego_actor.apply_physics_control(physics)\n"
        + f"{inner}self.interface.physics_control = self.ego_actor.get_physics_control()\n"
        + f"{inner}print(\"PIX_CARLA_RUNTIME_PHYSICS_PATCH: applied\", flush=True)\n"
    )

for path in targets:
    if not path.exists():
        raise SystemExit(f"bridge loop target file not found: {path}")

    backup = Path(str(path) + backup_suffix)
    text = path.read_text()

    if rollback:
        if not backup.exists():
            print(f"no bridge loop backup to restore: {backup}")
            continue
        if dry_run:
            print(f"would restore bridge loop: {backup} -> {path}")
            continue
        path.write_text(backup.read_text())
        py_compile.compile(str(path), doraise=True)
        print(f"restored bridge loop: {path}")
        continue

    patched_text = text
    patch_descriptions = []

    if opendrive_marker not in patched_text:
        def patched_load_world(match: re.Match[str]) -> str:
            indent = match.group("indent")
            inner = indent + "    "
            return (
                f"{indent}if self.carla_map.endswith(\".xodr\") and os.path.isfile(self.carla_map):\n"
                f"{inner}# PIX_CARLA_OPENDRIVE_WORLD_PATCH: use a CARLA-generated\n"
                f"{inner}# OpenDRIVE world when the cooked reconstruction mesh lacks\n"
                f"{inner}# drivable collision but the XODR/lanelet route is valid.\n"
                f"{inner}with open(self.carla_map, \"r\", encoding=\"utf-8\") as xodr_file:\n"
                f"{inner}    xodr_data = xodr_file.read()\n"
                f"{inner}generation_params = carla.OpendriveGenerationParameters()\n"
                f"{inner}generation_params.vertex_distance = 2.0\n"
                f"{inner}generation_params.max_road_length = 500.0\n"
                f"{inner}generation_params.wall_height = 0.0\n"
                f"{inner}generation_params.additional_width = 1.0\n"
                f"{inner}generation_params.smooth_junctions = True\n"
                f"{inner}generation_params.enable_mesh_visibility = True\n"
                f"{inner}generation_params.enable_pedestrian_navigation = False\n"
                f"{inner}self.world = client.generate_opendrive_world(xodr_data, generation_params)\n"
                f"{indent}else:\n"
                f"{inner}self.world = client.load_world(self.carla_map)\n"
            )

        patched_text, opendrive_patch_count = load_world_pattern.subn(patched_load_world, patched_text, count=1)
        if not opendrive_patch_count:
            raise SystemExit(f"OpenDRIVE world target block not found: {path}")
        patch_descriptions.append("added OpenDRIVE world fallback")
    elif "generation_params.enable_pedestrian_navigation" not in patched_text:
        patched_text = patched_text.replace(
            "generation_params.enable_mesh_visibility = True\n",
            "generation_params.enable_mesh_visibility = False\n"
            "            generation_params.enable_pedestrian_navigation = False\n",
            1,
        )
        patch_descriptions.append("disabled OpenDRIVE pedestrian navigation generation")
    elif "generation_params.enable_mesh_visibility = False" in patched_text:
        patched_text = patched_text.replace(
            "generation_params.enable_mesh_visibility = False\n",
            "generation_params.enable_mesh_visibility = True\n",
            1,
        )
        patch_descriptions.append("enabled OpenDRIVE mesh visibility generation")

    if timeout_marker not in patched_text:
        patched_text, timeout_patch_count = raise_pattern.subn(patched_except, patched_text, count=1)
        if not timeout_patch_count:
            raise SystemExit(f"sensor timeout target block not found: {path}")
        patch_descriptions.append("added sensor timeout tolerance")

    if physics_marker not in patched_text:
        patched_text, physics_patch_count = physics_assignment_pattern.subn(
            patched_physics_assignment,
            patched_text,
            count=1,
        )
        if not physics_patch_count:
            raise SystemExit(f"runtime physics target block not found: {path}")
        patch_descriptions.append("added runtime vehicle physics tuning")

    if not patch_descriptions:
        print(f"bridge loop already patched: {path}")
        continue

    if "import os\n" not in patched_text:
        if "import random\n" in patched_text:
            patched_text = patched_text.replace("import random\n", "import os\nimport random\n", 1)
        else:
            raise SystemExit(f"cannot add os import to bridge loop: {path}")

    if dry_run:
        print(f"would patch bridge loop ({'; '.join(patch_descriptions)}): {path}")
        continue

    if not backup.exists():
        backup.write_text(text)
        print(f"bridge loop backup: {backup}")

    path.write_text(patched_text)
    py_compile.compile(str(path), doraise=True)
    print(f"patched bridge loop ({'; '.join(patch_descriptions)}): {path}")
PY

echo "Bridge loop patch operation completed."

python3 - "$LAUNCH_BACKUP_SUFFIX" "$ROLLBACK" "$DRY_RUN" \
  "$SOURCE_LAUNCH_FILE" \
  "$INSTALL_LAUNCH_FILE" \
  "$PRIVATE_SOURCE_LAUNCH_FILE" \
  "$PRIVATE_INSTALL_LAUNCH_FILE" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

backup_suffix = sys.argv[1]
rollback = sys.argv[2] == "1"
dry_run = sys.argv[3] == "1"

targets = []
for path in [Path(arg) for arg in sys.argv[4:]]:
    if path.exists() and path not in targets:
        targets.append(path)

if not targets:
    print("launch patch skipped: autoware_carla_interface launch file not found in source or install tree")
    raise SystemExit(0)

replacements = {
    'name="velodyne_top"': 'name="simctl_static_tf_velodyne_top"',
    'name="imu"': 'name="simctl_static_tf_imu"',
    'name="autoware_raw_vehicle_cmd_converter"': 'name="simctl_carla_raw_vehicle_cmd_converter"',
}

for path in targets:
    backup = Path(str(path) + backup_suffix)
    if rollback:
        if not backup.exists():
            print(f"no launch backup to restore: {backup}")
            continue
        if dry_run:
            print(f"would restore launch: {backup} -> {path}")
            continue
        path.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"restored launch: {path}")
        continue

    text = path.read_text(encoding="utf-8")
    patched = text
    for old, new in replacements.items():
        patched = patched.replace(old, new)

    if patched == text:
        print(f"launch already patched: {path}")
        continue

    if dry_run:
        print(f"would patch launch static TF node names: {path}")
        continue

    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
        print(f"launch backup: {backup}")
    path.write_text(patched, encoding="utf-8")
    print(f"patched launch static TF node names: {path}")
PY

echo "Launch patch operation completed."

python3 - "$COMPONENT_TOPICS_BACKUP_SUFFIX" "$ROLLBACK" "$DRY_RUN" \
  "$SOURCE_COMPONENT_TOPICS_FILE" \
  "$INSTALL_COMPONENT_TOPICS_FILE" \
  "$PRIVATE_SOURCE_COMPONENT_TOPICS_FILE" \
  "$PRIVATE_INSTALL_COMPONENT_TOPICS_FILE" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

backup_suffix = sys.argv[1]
rollback = sys.argv[2] == "1"
dry_run = sys.argv[3] == "1"
candidate_paths = [Path(arg) for arg in sys.argv[4:]]

targets: list[Path] = []
for path in candidate_paths:
    if path.exists() and path not in targets:
        targets.append(path)

if not targets:
    print("component topics patch skipped: autoware_launch component_state_monitor topics file not found")
    raise SystemExit(0)

vehicle_topic_block = re.compile(
    r"(?P<block>- module: vehicle\n(?:(?!\n- module:).)*?topic: /vehicle/status/"
    r"(?P<topic>velocity_status|steering_status)\n(?:(?!\n- module:).)*?)(?=\n- module:|\Z)",
    re.DOTALL,
)


def replace_or_fail(block: str, key: str, value: str, *, path: Path, topic: str) -> str:
    pattern = re.compile(rf"(?m)^(\s*{re.escape(key)}:\s*)[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?\d+)?\s*$")
    patched, count = pattern.subn(rf"\g<1>{value}", block, count=1)
    if count != 1:
        raise SystemExit(f"component topics {key} target not found for {topic}: {path}")
    return patched


for path in targets:
    backup = Path(str(path) + backup_suffix)
    if rollback:
        if not backup.exists():
            print(f"no component topics backup to restore: {backup}")
            continue
        if dry_run:
            print(f"would restore component topics: {backup} -> {path}")
            continue
        path.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"restored component topics: {path}")
        continue

    text = path.read_text(encoding="utf-8")
    patched_topics: set[str] = set()

    def patch_block(match: re.Match[str]) -> str:
        topic = match.group("topic")
        block = match.group("block")
        patched = replace_or_fail(block, "warn_rate", "0.0", path=path, topic=topic)
        patched = replace_or_fail(patched, "error_rate", "0.0", path=path, topic=topic)
        patched = replace_or_fail(patched, "timeout", "5.0", path=path, topic=topic)
        patched_topics.add(topic)
        return patched

    patched_text = vehicle_topic_block.sub(patch_block, text)
    if patched_topics != {"velocity_status", "steering_status"}:
        raise SystemExit(f"vehicle component topics not found in component_state_monitor config: {path}")

    if patched_text == text:
        print(f"component topics already patched: {path}")
        continue

    if dry_run:
        print(f"would patch component vehicle topic rates: {path}")
        continue

    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
        print(f"component topics backup: {backup}")
    path.write_text(patched_text, encoding="utf-8")
    print(f"patched component vehicle topic rates: {path}")
PY

echo "Component topics patch operation completed."
