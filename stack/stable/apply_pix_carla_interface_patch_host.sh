#!/usr/bin/env bash
set -euo pipefail

AUTOWARE_WS="${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/autoware}"
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
  - steer radians-to-normalized conversion plus steer gain
  - first-order steering hold when ROS callbacks arrive faster than CARLA ticks
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
  --dry-run           Check target files without writing.
  --rollback          Restore backups created by this script.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --autoware-ws) AUTOWARE_WS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --rollback) ROLLBACK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

SOURCE_FILE="${AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/src/autoware_carla_interface/carla_ros.py"
BUILD_FILE="${AUTOWARE_WS}/build/autoware_carla_interface/src/autoware_carla_interface/carla_ros.py"
SOURCE_LAUNCH_FILE="${AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/launch/autoware_carla_interface.launch.xml"
INSTALL_LAUNCH_FILE="${AUTOWARE_WS}/install/autoware_carla_interface/share/autoware_carla_interface/autoware_carla_interface.launch.xml"
BACKUP_SUFFIX=".pix_actuation_map.bak"
LAUNCH_BACKUP_SUFFIX=".pix_static_tf_node_names.bak"

python3 - "$SOURCE_FILE" "$BUILD_FILE" "$BACKUP_SUFFIX" "$ROLLBACK" "$DRY_RUN" <<'PY'
from __future__ import annotations

import re
import py_compile
import sys
from pathlib import Path

source_file = Path(sys.argv[1])
build_file = Path(sys.argv[2])
backup_suffix = sys.argv[3]
rollback = sys.argv[4] == "1"
dry_run = sys.argv[5] == "1"
targets = [source_file]
if build_file != source_file:
    targets.append(build_file)

marker = "PIX_CARLA_ACTUATION_MAP_PATCH"
steer_hold_marker = "PIX_CARLA_STEER_HOLD_PATCH"
steer_method_pattern = re.compile(
    r"    def first_order_steering\(self, steer_input\):\n.*?\n    def control_callback\(self, in_cmd\):",
    re.DOTALL,
)
method_pattern = re.compile(
    r"    def control_callback\(self, in_cmd\):\n.*?\n    def ego_status\(self\):",
    re.DOTALL,
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
            steer_output = self.prev_steer_output + (steer_input - self.prev_steer_output) * (
                dt / (self.tau + dt)
            )
            self.prev_steer_output = steer_output
            self.prev_timestamp = self.timestamp
        return steer_output

    def control_callback(self, in_cmd):'''
patched_method = '''    def control_callback(self, in_cmd):
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
        throttle_gain = _env_float("PIX_CARLA_THROTTLE_GAIN", 1.0)
        min_throttle = _env_float("PIX_CARLA_MIN_THROTTLE", 0.0)
        max_throttle = _env_float("PIX_CARLA_MAX_THROTTLE", 1.0)
        creep_throttle = _env_float("PIX_CARLA_CREEP_THROTTLE", 0.0)
        creep_speed_threshold = _env_float("PIX_CARLA_CREEP_SPEED_THRESHOLD_MPS", 0.08)
        brake_gain = _env_float("PIX_CARLA_BRAKE_GAIN", 1.0)
        max_brake = _env_float("PIX_CARLA_MAX_BRAKE", 1.0)
        brake_deadband = _env_float("PIX_CARLA_BRAKE_DEADBAND", 0.0)

        throttle = raw_throttle * throttle_gain
        if raw_throttle > 0.0 and throttle < min_throttle:
            throttle = min_throttle
        if raw_throttle > 0.0 and ego_speed_mps <= creep_speed_threshold:
            throttle = max(throttle, creep_throttle)
        throttle = min(max(throttle, 0.0), max_throttle)

        brake = 0.0 if raw_brake < brake_deadband else raw_brake * brake_gain
        brake = min(max(brake, 0.0), max_brake)
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
        out_cmd.steer = min(
            max(self.first_order_steering(steer_input * steer_gain) * max_steer_ratio, -1.0),
            1.0,
        )
        out_cmd.brake = brake
        self.current_control = out_cmd

    def ego_status(self):'''

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

    if steer_hold_marker not in patched_text:
        steer_match = steer_method_pattern.search(patched_text)
        if not steer_match:
            raise SystemExit(f"steering target block not found: {path}")
        patched_text = patched_text[: steer_match.start()] + patched_steer_method + patched_text[steer_match.end() :]
        patch_descriptions.append("held steering output across same-tick callbacks")

    if marker not in patched_text:
        match = method_pattern.search(patched_text)
        if not match:
            raise SystemExit(f"actuation target block not found: {path}")
        patched_text = patched_text[: match.start()] + patched_method + patched_text[match.end() :]
        patch_descriptions.append("calibrated throttle, brake, and steer")

    if not patch_descriptions:
        print(f"already patched: {path}")
        continue

    if "import os\n" not in patched_text:
        if "import math\n" not in patched_text:
            raise SystemExit(f"cannot add os import: {path}")
        patched_text = patched_text.replace("import math\n", "import math\nimport os\n", 1)

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

python3 - "$SOURCE_LAUNCH_FILE" "$INSTALL_LAUNCH_FILE" "$LAUNCH_BACKUP_SUFFIX" "$ROLLBACK" "$DRY_RUN" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

source_launch_file = Path(sys.argv[1])
install_launch_file = Path(sys.argv[2])
backup_suffix = sys.argv[3]
rollback = sys.argv[4] == "1"
dry_run = sys.argv[5] == "1"

targets = []
for path in (source_launch_file, install_launch_file):
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
