#!/usr/bin/env bash
set -euo pipefail

AUTOWARE_WS="${AUTOWARE_WS:-/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware}"
MODE="apply"
PROFILE="carla_2ws"
SNAPSHOT_OUT=""

usage() {
  cat <<'USAGE'
Usage:
  stack/stable/apply_robobus_2ws_autoware_params_host.sh [--autoware-ws PATH] [--profile carla_2ws|117th_4ws] [--snapshot-out PATH] [--dry-run|--rollback]

Applies a reversible Autoware vehicle-parameter profile for the current CARLA
robobus validation vehicle.

Why this exists:
  The stable CARLA actor vehicle.pixmoving.robobus currently uses front-wheel
  steering only. The private robobus Autoware install is configured with
  kinematics_adaptive / 4WS-aware parameters. The legacy carla_2ws profile
  temporarily aligns Autoware with that 2WS approximation. The 117th_4ws profile
  restores the real 117th robobus steering model and should be the default for
  simulation-fidelity validation.

Targets:
  install/autoware_launch/share/autoware_launch/config/control/trajectory_follower/lateral/mpc.param.yaml
  install/robobus_description/share/robobus_description/config/simulator_model.param.yaml
  install/robobus_description/share/robobus_description/config/vehicle_info.param.yaml

Options:
  --autoware-ws PATH  Autoware workspace containing install/ (default: AUTOWARE_WS or private_autoware)
  --profile NAME      carla_2ws or 117th_4ws (default: carla_2ws for backward compatibility)
  --apply-2ws         Alias for --profile carla_2ws
  --restore-117th-4ws Alias for --profile 117th_4ws
  --snapshot-out PATH Write a JSON evidence snapshot with the applied key parameters
  --dry-run           Print target files and current relevant lines without changing files
  --rollback          Restore the latest script-created .pix_2ws.bak files
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --autoware-ws) AUTOWARE_WS="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --profile=*) PROFILE="${1#--profile=}"; shift ;;
    --snapshot-out) SNAPSHOT_OUT="$2"; shift 2 ;;
    --snapshot-out=*) SNAPSHOT_OUT="${1#--snapshot-out=}"; shift ;;
    --apply-2ws) PROFILE="carla_2ws"; shift ;;
    --restore-117th-4ws) PROFILE="117th_4ws"; shift ;;
    --dry-run) MODE="dry-run"; shift ;;
    --rollback) MODE="rollback"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${PROFILE}" in
  carla_2ws|117th_4ws) ;;
  *) echo "Unknown profile: ${PROFILE}" >&2; usage >&2; exit 2 ;;
esac

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
  echo "Profile=${PROFILE}"
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

python3 - "$PROFILE" "$MPC_PARAM" "$SIM_PARAM" "$VEHICLE_PARAM" <<'PY'
from pathlib import Path
import re
import sys

profile = sys.argv[1]
mpc_path, sim_path, vehicle_path = map(Path, sys.argv[2:])

def rewrite(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text()
    original = text
    for pattern, repl in replacements:
        text, count = re.subn(pattern, repl, text, flags=re.MULTILINE)
        if count == 0:
            raise SystemExit(f"pattern not found in {path}: {pattern}")
    if text != original:
        path.write_text(text)

profiles = {
    "carla_2ws": {
        "mpc_model": 'vehicle_model_type: "kinematics" # PIX 2WS CARLA validation override',
        "sim_model": 'vehicle_model_type: "DELAY_STEER_ACC_GEARED" # PIX 2WS CARLA validation override',
        "to_4ws": "to_4ws_k_threshold: 999.0 # PIX 2WS CARLA validation override",
        "to_2ws": "to_2ws_k_threshold: 998.0 # PIX 2WS CARLA validation override",
        "coef": "coef_for_4ws: 1.0 # PIX 2WS CARLA validation override",
    },
    "117th_4ws": {
        "mpc_model": 'vehicle_model_type: "kinematics_adaptive" # PIX 117th 4WS fidelity profile',
        "sim_model": 'vehicle_model_type: "DELAY_STEER_ACC_GEARED_ADAPTIVE" # PIX 117th 4WS fidelity profile',
        "to_4ws": "to_4ws_k_threshold: 0.09 # PIX 117th 4WS fidelity profile",
        "to_2ws": "to_2ws_k_threshold: 0.01 # PIX 117th 4WS fidelity profile",
        "coef": "coef_for_4ws: 0.5 # PIX 117th 4WS fidelity profile",
    },
}

values = profiles[profile]

rewrite(mpc_path, [(r'^(\s*)vehicle_model_type:\s*".*"(.*)$', r"\1" + values["mpc_model"])])
rewrite(sim_path, [(r'^(\s*)vehicle_model_type:\s*".*"(.*)$', r"\1" + values["sim_model"])])
rewrite(
    vehicle_path,
    [
        (r'^(\s*)to_4ws_k_threshold:\s*[-+0-9.eE]+(.*)$', r"\1" + values["to_4ws"]),
        (r'^(\s*)to_2ws_k_threshold:\s*[-+0-9.eE]+(.*)$', r"\1" + values["to_2ws"]),
        (r'^(\s*)coef_for_4ws:\s*[-+0-9.eE]+(.*)$', r"\1" + values["coef"]),
    ],
)
PY

echo "Applied PIX robobus Autoware parameter profile: ${PROFILE}"
for target in "${TARGETS[@]}"; do
  show_relevant_lines "${target}"
done

if [[ -n "${SNAPSHOT_OUT}" ]]; then
  mkdir -p "$(dirname "${SNAPSHOT_OUT}")"
  python3 - "$PROFILE" "$AUTOWARE_WS" "$SNAPSHOT_OUT" "$MPC_PARAM" "$SIM_PARAM" "$VEHICLE_PARAM" <<'PY'
from pathlib import Path
import json
import re
import sys

profile, autoware_ws, snapshot_out = sys.argv[1:4]
mpc_path, sim_path, vehicle_path = map(Path, sys.argv[4:])

def value_for(path: Path, key: str):
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*(?:#.*)?$", path.read_text(), re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    return value.strip('"')

payload = {
    "profile": profile,
    "autoware_ws": autoware_ws,
    "targets": {
        "mpc_param": str(mpc_path),
        "simulator_model_param": str(sim_path),
        "vehicle_info_param": str(vehicle_path),
    },
    "parameters": {
        "mpc_vehicle_model_type": value_for(mpc_path, "vehicle_model_type"),
        "simulator_vehicle_model_type": value_for(sim_path, "vehicle_model_type"),
        "to_4ws_k_threshold": value_for(vehicle_path, "to_4ws_k_threshold"),
        "to_2ws_k_threshold": value_for(vehicle_path, "to_2ws_k_threshold"),
        "coef_for_4ws": value_for(vehicle_path, "coef_for_4ws"),
    },
}
Path(snapshot_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
PY
  echo "wrote snapshot: ${SNAPSHOT_OUT}"
fi
