#!/usr/bin/env bash
set -euo pipefail

RUN_DIR=""
CARLA_PORT=""
ROS_DOMAIN_ID=""
RMW_IMPLEMENTATION_ARG=""
CPU_AFFINITY=""
AUTOWARE_WS_ARG=""
EGO_VEHICLE_ROLE_NAME=""
ENABLED=""
POLL_SEC=""
WAIT_SEC=""
INCLUDE_WALKERS=""
DELETE_ALL_ON_START=""
DELETE_ALL_ON_STOP=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --carla-port) CARLA_PORT="$2"; shift 2 ;;
    --ros-domain-id) ROS_DOMAIN_ID="$2"; shift 2 ;;
    --rmw-implementation) RMW_IMPLEMENTATION_ARG="$2"; shift 2 ;;
    --cpu-affinity) CPU_AFFINITY="$2"; shift 2 ;;
    --autoware-ws) AUTOWARE_WS_ARG="$2"; shift 2 ;;
    --ego-vehicle-role-name) EGO_VEHICLE_ROLE_NAME="$2"; shift 2 ;;
    --enabled) ENABLED="$2"; shift 2 ;;
    --poll-sec) POLL_SEC="$2"; shift 2 ;;
    --wait-sec) WAIT_SEC="$2"; shift 2 ;;
    --include-walkers) INCLUDE_WALKERS="$2"; shift 2 ;;
    --delete-all-on-start) DELETE_ALL_ON_START="$2"; shift 2 ;;
    --delete-all-on-stop) DELETE_ALL_ON_STOP="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

truthy() {
  local normalized
  normalized="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$normalized" in
    1|true|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

shell_quote() {
  printf "%q" "$1"
}

AUTOWARE_WS="${AUTOWARE_WS_ARG:-${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/private_autoware}}"
AUTOWARE_SETUP="${AUTOWARE_WS}/install/setup.bash"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_SCRIPT="${SCRIPT_DIR}/carla_actor_object_bridge.py"
CARLA_PORT="${CARLA_PORT:-2000}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-21}"
RMW_IMPLEMENTATION_VALUE="${RMW_IMPLEMENTATION_ARG:-${RMW_IMPLEMENTATION:-}}"
EGO_VEHICLE_ROLE_NAME="${EGO_VEHICLE_ROLE_NAME:-ego_vehicle}"
ENABLED="${ENABLED:-${SIMCTL_CARLA_ACTOR_OBJECT_BRIDGE_ENABLED:-false}}"
POLL_SEC="${POLL_SEC:-${SIMCTL_CARLA_ACTOR_OBJECT_BRIDGE_POLL_SEC:-0.2}}"
WAIT_SEC="${WAIT_SEC:-${SIMCTL_CARLA_ACTOR_OBJECT_BRIDGE_WAIT_SEC:-240}}"
INCLUDE_WALKERS="${INCLUDE_WALKERS:-${SIMCTL_CARLA_ACTOR_OBJECT_BRIDGE_INCLUDE_WALKERS:-true}}"
DELETE_ALL_ON_START="${DELETE_ALL_ON_START:-${SIMCTL_CARLA_ACTOR_OBJECT_BRIDGE_DELETE_ALL_ON_START:-true}}"
DELETE_ALL_ON_STOP="${DELETE_ALL_ON_STOP:-${SIMCTL_CARLA_ACTOR_OBJECT_BRIDGE_DELETE_ALL_ON_STOP:-true}}"

PY_CMD=("python3" "${BRIDGE_SCRIPT}" "--carla-port" "${CARLA_PORT}" "--ego-vehicle-role-name" "${EGO_VEHICLE_ROLE_NAME}" "--poll-sec" "${POLL_SEC}" "--carla-wait-sec" "${WAIT_SEC}")
if truthy "${INCLUDE_WALKERS}"; then
  PY_CMD+=("--include-walkers")
fi
if truthy "${DELETE_ALL_ON_START}"; then
  PY_CMD+=("--delete-all-on-start")
fi
if truthy "${DELETE_ALL_ON_STOP}"; then
  PY_CMD+=("--delete-all-on-stop")
fi

PY_CMD_DISPLAY=""
for cmd_part in "${PY_CMD[@]}"; do
  PY_CMD_DISPLAY+=" $(shell_quote "${cmd_part}")"
done
PY_CMD_DISPLAY="${PY_CMD_DISPLAY# }"

echo "RunDir: ${RUN_DIR}"
echo "CARLA actor object bridge enabled: ${ENABLED}"
echo "Autoware workspace: ${AUTOWARE_WS}"
echo "CARLA RPC Port: ${CARLA_PORT}"
echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "RMW_IMPLEMENTATION: ${RMW_IMPLEMENTATION_VALUE}"
echo "Ego role: ${EGO_VEHICLE_ROLE_NAME}"
echo "Poll seconds: ${POLL_SEC}"
echo "CARLA wait seconds: ${WAIT_SEC}"
echo "Include walkers: ${INCLUDE_WALKERS}"
echo "Delete all on start: ${DELETE_ALL_ON_START}"
echo "Delete all on stop: ${DELETE_ALL_ON_STOP}"
echo "Command: ${PY_CMD_DISPLAY}"

if ! truthy "${ENABLED}"; then
  echo "CARLA actor object bridge disabled; set SIMCTL_CARLA_ACTOR_OBJECT_BRIDGE_ENABLED=true or scenario stable_runtime.carla_actor_object_bridge_enabled=true to enable."
  exit 0
fi

if [[ "${EXECUTE}" -ne 1 ]]; then
  exit 0
fi

if [[ ! -f "${AUTOWARE_SETUP}" ]]; then
  echo "Autoware setup script not found at ${AUTOWARE_SETUP}" >&2
  exit 1
fi
if [[ ! -f "${BRIDGE_SCRIPT}" ]]; then
  echo "Bridge script not found at ${BRIDGE_SCRIPT}" >&2
  exit 1
fi

set +u
# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
# shellcheck disable=SC1090
source "${AUTOWARE_SETUP}"
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID}"
if [[ -n "${RMW_IMPLEMENTATION_VALUE}" ]]; then
  export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION_VALUE}"
fi

if [[ -n "${CPU_AFFINITY}" ]]; then
  exec taskset -c "${CPU_AFFINITY}" "${PY_CMD[@]}"
fi
exec "${PY_CMD[@]}"
