#!/usr/bin/env bash
set -euo pipefail

EXECUTE=0
CARLA_ROOT_ARG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -Execute|--execute) EXECUTE=1; shift ;;
    --carla-root) CARLA_ROOT_ARG="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

CARLA_ROOT="${CARLA_ROOT_ARG:-${CARLA_0915_ROOT:-$HOME/CARLA_0.9.15}}"
SUMO_HOME_CANDIDATE="${SUMO_HOME:-/usr/share/sumo}"
COSIM_SCRIPT="${CARLA_ROOT}/Co-Simulation/Sumo/run_synchronization.py"

COMMANDS=(
  "sudo apt-get update"
  "sudo apt-get install -y sumo sumo-tools sumo-doc python3-pip"
  "python3 -m pip install --user traci sumolib"
)

echo "Preparing SUMO runtime for CARLA co-simulation"
echo "EXECUTE=${EXECUTE}"
echo "CARLA root: ${CARLA_ROOT}"
echo "SUMO_HOME candidate: ${SUMO_HOME_CANDIDATE}"
echo "CARLA SUMO co-sim script: ${COSIM_SCRIPT}"

for cmd in "${COMMANDS[@]}"; do
  echo "$cmd"
  if [[ "${EXECUTE}" -eq 1 ]]; then
    eval "$cmd"
  fi
done

echo
echo "Post-install checks"
if command -v sumo >/dev/null 2>&1; then
  echo "[PASS] sumo available: $(command -v sumo)"
else
  echo "[WARN] sumo is not available yet"
fi
if command -v netconvert >/dev/null 2>&1; then
  echo "[PASS] netconvert available: $(command -v netconvert)"
else
  echo "[WARN] netconvert is not available yet"
fi
if [[ -d "${SUMO_HOME_CANDIDATE}" ]]; then
  echo "[PASS] SUMO_HOME directory exists: ${SUMO_HOME_CANDIDATE}"
else
  echo "[WARN] SUMO_HOME directory missing: ${SUMO_HOME_CANDIDATE}"
fi
if [[ -f "${COSIM_SCRIPT}" ]]; then
  echo "[PASS] CARLA SUMO co-sim script found"
else
  echo "[WARN] CARLA SUMO co-sim script missing; set stable_runtime.sumo_cosim_script if using a source checkout path."
fi

echo
echo "Recommended environment for shell sessions:"
echo "export SUMO_HOME=${SUMO_HOME_CANDIDATE}"
