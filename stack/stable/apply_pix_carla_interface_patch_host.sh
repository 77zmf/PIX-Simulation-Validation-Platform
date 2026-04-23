#!/usr/bin/env bash
set -euo pipefail

AUTOWARE_WS="${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/autoware}"
ROLLBACK=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Apply the PIX robobus Autoware CARLA interface steering normalization patch.

Default target:
  $HOME/zmf_ws/projects/autoware_universe/autoware

Why:
  Autoware actuation steer_cmd follows the control tire-angle command in radians,
  while CARLA VehicleControl.steer expects a normalized [-1, 1] input. Without
  this conversion, the actual CARLA tire angle is roughly steer_cmd * max_steer,
  which halves the PIX robobus steering response for max_steer_angle=0.506 rad.

Validation:
  Run scenarios/l1/regression_follow_lane.yaml with simctl --execute and compare
  /vehicle/status/steering_status.steering_tire_angle against
  /control/command/control_cmd.steering_tire_angle.
  PIX_CARLA_STEER_GAIN can be used for controlled route-tracking sweeps after
  the radians-to-normalized steering conversion is applied.

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
BACKUP_SUFFIX=".pix_steer_normalize.bak"

python3 - "$SOURCE_FILE" "$BUILD_FILE" "$BACKUP_SUFFIX" "$ROLLBACK" "$DRY_RUN" <<'PY'
from __future__ import annotations

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

old = """            max_steer_ratio = numpy.interp(
                abs(current_vel.x), [v.x for v in steer_curve], [v.y for v in steer_curve]
            )
            out_cmd.steer = self.first_order_steering(-in_cmd.actuation.steer_cmd) * max_steer_ratio
            out_cmd.brake = brake
            self.current_control = out_cmd
"""

normalized_without_gain = """            max_steer_ratio = numpy.interp(
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
            out_cmd.steer = min(
                max(self.first_order_steering(steer_input) * max_steer_ratio, -1.0), 1.0
            )
            out_cmd.brake = brake
            self.current_control = out_cmd
"""

normalized_with_gain = """            max_steer_ratio = numpy.interp(
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
            try:
                steer_gain = float(os.environ.get("PIX_CARLA_STEER_GAIN", "1.0") or "1.0")
            except ValueError:
                steer_gain = 1.0
            out_cmd.steer = min(
                max(self.first_order_steering(steer_input * steer_gain) * max_steer_ratio, -1.0),
                1.0,
            )
            out_cmd.brake = brake
            self.current_control = out_cmd
"""

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

    if "PIX_CARLA_STEER_GAIN" in text:
        print(f"already patched: {path}")
        continue

    patch_description = ""
    if normalized_without_gain in text:
        patched_text = text.replace(normalized_without_gain, normalized_with_gain)
        patch_description = "added steer gain"
    elif old in text:
        patched_text = text.replace(old, normalized_with_gain)
        patch_description = "normalized steer and added steer gain"
    else:
        raise SystemExit(f"target block not found: {path}")

    if "import os\n" not in patched_text:
        if "import math\n" not in patched_text:
            raise SystemExit(f"cannot add os import: {path}")
        patched_text = patched_text.replace("import math\n", "import math\nimport os\n", 1)

    if dry_run:
        print(f"would patch ({patch_description}): {path}")
        continue

    if not backup.exists():
        backup.write_text(text)
        print(f"backup: {backup}")

    path.write_text(patched_text)
    py_compile.compile(str(path), doraise=True)
    print(f"patched ({patch_description}): {path}")
PY

echo "Patch operation completed."
