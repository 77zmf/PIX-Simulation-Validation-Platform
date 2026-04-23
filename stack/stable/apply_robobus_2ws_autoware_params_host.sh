#!/usr/bin/env bash
set -euo pipefail

AUTOWARE_WS="${AUTOWARE_WS:-/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware}"
MODE="apply"

usage() {
  cat <<'USAGE'
Usage:
  stack/stable/apply_robobus_2ws_autoware_params_host.sh [--autoware-ws PATH] [--dry-run|--rollback]

Applies a reversible 2WS-compatible Autoware parameter override for the current
CARLA robobus validation vehicle.

Why this exists:
  The stable CARLA actor vehicle.pixmoving.robobus currently uses front-wheel
  steering only. The private robobus Autoware install is configured with
  kinematics_adaptive / 4WS-aware parameters. This script temporarily aligns
  Autoware's lateral controller and simulator model with the current CARLA 2WS
  physics so L1 closed-loop validation can isolate vehicle tracking behavior.

Targets:
  install/autoware_launch/share/autoware_launch/config/control/trajectory_follower/lateral/mpc.param.yaml
  install/robobus_description/share/robobus_description/config/simulator_model.param.yaml
  install/robobus_description/share/robobus_description/config/vehicle_info.param.yaml

Options:
  --autoware-ws PATH  Autoware workspace containing install/ (default: AUTOWARE_WS or private_autoware)
  --dry-run           Print target files and current relevant lines without changing files
  --rollback          Restore the latest script-created .pix_2ws.bak files
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --autoware-ws) AUTOWARE_WS="$2"; shift 2 ;;
    --dry-run) MODE="dry-run"; shift ;;
    --rollback) MODE="rollback"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

MPC_PARAM="${AUTOWARE_WS}/install/autoware_launch/share/autoware_launch/config/control/trajectory_follower/lateral/mpc.param.yaml"
SIM_PARAM="${AUTOWARE_WS}/install/robobus_description/share/robobus_description/config/simulator_model.param.yaml"
VEHICLE_PARAM="${AUTOWARE_WS}/install/robobus_description/share/robobus_description/config/vehicle_info.param.yaml"
TARGETS=("${MPC_PARAM}" "${SIM_PARAM}" "${VEHICLE_PARAM}")

for target in "${TARGETS[@]}"; do
  if [[ ! -f "${target}" ]]; then
    echo "Required file not found: ${target}" >&2
    exit 1
  fi
done

show_relevant_lines() {
  local file="$1"
  echo "--- ${file}"
  grep -nE 'vehicle_model_type|to_4ws_k_threshold|to_2ws_k_threshold|coef_for_4ws' "${file}" || true
}

backup_once() {
  local file="$1"
  local backup="${file}.pix_2ws.bak"
  if [[ ! -f "${backup}" ]]; then
    cp -p "${file}" "${backup}"
    echo "created backup: ${backup}"
  else
    echo "backup exists: ${backup}"
  fi
}

restore_backup() {
  local file="$1"
  local backup="${file}.pix_2ws.bak"
  if [[ ! -f "${backup}" ]]; then
    echo "rollback backup not found: ${backup}" >&2
    exit 1
  fi
  cp -p "${backup}" "${file}"
  echo "restored: ${file}"
}

if [[ "${MODE}" == "dry-run" ]]; then
  echo "AUTOWARE_WS=${AUTOWARE_WS}"
  for target in "${TARGETS[@]}"; do
    show_relevant_lines "${target}"
  done
  exit 0
fi

if [[ "${MODE}" == "rollback" ]]; then
  for target in "${TARGETS[@]}"; do
    restore_backup "${target}"
  done
  echo "Rollback completed."
  exit 0
fi

for target in "${TARGETS[@]}"; do
  backup_once "${target}"
done

python3 - "$MPC_PARAM" "$SIM_PARAM" "$VEHICLE_PARAM" <<'PY'
from pathlib import Path
import re
import sys

mpc_path, sim_path, vehicle_path = map(Path, sys.argv[1:])

def rewrite(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text()
    original = text
    for pattern, repl in replacements:
        text, count = re.subn(pattern, repl, text, flags=re.MULTILINE)
        if count == 0:
            raise SystemExit(f"pattern not found in {path}: {pattern}")
    if text != original:
        path.write_text(text)

rewrite(
    mpc_path,
    [
        (
            r'^(\s*)vehicle_model_type:\s*".*"(.*)$',
            r'\1vehicle_model_type: "kinematics" # PIX 2WS CARLA validation override',
        ),
    ],
)

rewrite(
    sim_path,
    [
        (
            r'^(\s*)vehicle_model_type:\s*".*"(.*)$',
            r'\1vehicle_model_type: "DELAY_STEER_ACC_GEARED" # PIX 2WS CARLA validation override',
        ),
    ],
)

rewrite(
    vehicle_path,
    [
        (
            r'^(\s*)to_4ws_k_threshold:\s*[-+0-9.eE]+(.*)$',
            r'\1to_4ws_k_threshold: 999.0 # PIX 2WS CARLA validation override',
        ),
        (
            r'^(\s*)to_2ws_k_threshold:\s*[-+0-9.eE]+(.*)$',
            r'\1to_2ws_k_threshold: 998.0 # PIX 2WS CARLA validation override',
        ),
        (
            r'^(\s*)coef_for_4ws:\s*[-+0-9.eE]+(.*)$',
            r'\1coef_for_4ws: 1.0 # PIX 2WS CARLA validation override',
        ),
    ],
)
PY

echo "Applied PIX robobus 2WS Autoware parameter override."
for target in "${TARGETS[@]}"; do
  show_relevant_lines "${target}"
done
