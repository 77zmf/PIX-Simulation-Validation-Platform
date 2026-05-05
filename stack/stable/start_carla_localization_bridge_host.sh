#!/usr/bin/env bash
set -euo pipefail

SCENARIO=""
RUN_DIR=""
SLOT_ID=""
ROS_DOMAIN_ID=""
RMW_IMPLEMENTATION_ARG=""
RUNTIME_NAMESPACE=""
CPU_AFFINITY=""
AUTOWARE_WS_ARG=""
AUTOWARE_BRIDGE_WS_ARG=""
CARLA_ROOT_ARG=""
CARLA_HOST=""
CARLA_PORT=""
EGO_VEHICLE_ROLE_NAME=""
LOCALIZATION_SOURCE=""
ROS_Y_SIGN_ARG=""
KILL_SIMPLE_SIM=""
WAIT_SEC=""
KILL_MONITOR_SEC=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario) SCENARIO="$2"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --slot-id) SLOT_ID="$2"; shift 2 ;;
    --ros-domain-id) ROS_DOMAIN_ID="$2"; shift 2 ;;
    --rmw-implementation) RMW_IMPLEMENTATION_ARG="$2"; shift 2 ;;
    --runtime-namespace) RUNTIME_NAMESPACE="$2"; shift 2 ;;
    --cpu-affinity) CPU_AFFINITY="$2"; shift 2 ;;
    --autoware-ws) AUTOWARE_WS_ARG="$2"; shift 2 ;;
    --autoware-bridge-ws) AUTOWARE_BRIDGE_WS_ARG="$2"; shift 2 ;;
    --carla-root) CARLA_ROOT_ARG="$2"; shift 2 ;;
    --carla-host) CARLA_HOST="$2"; shift 2 ;;
    --carla-port) CARLA_PORT="$2"; shift 2 ;;
    --ego-vehicle-role-name) EGO_VEHICLE_ROLE_NAME="$2"; shift 2 ;;
    --source) LOCALIZATION_SOURCE="$2"; shift 2 ;;
    --ros-y-sign) ROS_Y_SIGN_ARG="$2"; shift 2 ;;
    --kill-simple-sim) KILL_SIMPLE_SIM="$2"; shift 2 ;;
    --wait-sec) WAIT_SEC="$2"; shift 2 ;;
    --kill-monitor-sec) KILL_MONITOR_SEC="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
AUTOWARE_WS="${AUTOWARE_WS_ARG:-${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/private_autoware}}"
AUTOWARE_BRIDGE_WS="${AUTOWARE_BRIDGE_WS_ARG:-${AUTOWARE_BRIDGE_WS:-$HOME/zmf_ws/projects/autoware_universe/autoware}}"
CARLA_ROOT="${CARLA_ROOT_ARG:-${CARLA_0915_ROOT:-}}"
CARLA_HOST="${CARLA_HOST:-${SIMCTL_CARLA_HOST:-127.0.0.1}}"
CARLA_PORT="${CARLA_PORT:-${SIMCTL_CARLA_RPC_PORT:-2000}}"
EGO_VEHICLE_ROLE_NAME="${EGO_VEHICLE_ROLE_NAME:-${SIMCTL_CARLA_EGO_ROLE_NAME:-ego_vehicle}}"
LOCALIZATION_SOURCE="${LOCALIZATION_SOURCE:-${SIMCTL_CARLA_LOCALIZATION_SOURCE:-topics}}"
ROS_Y_SIGN_VALUE="${ROS_Y_SIGN_ARG:-${SIMCTL_CARLA_ROS_Y_SIGN:-${PIX_CARLA_ROS_Y_SIGN:-}}}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-21}"
RMW_IMPLEMENTATION_VALUE="${RMW_IMPLEMENTATION_ARG:-${RMW_IMPLEMENTATION:-}}"
KILL_SIMPLE_SIM="${KILL_SIMPLE_SIM:-${SIMCTL_CARLA_LOCALIZATION_BRIDGE_KILL_SIMPLE_SIM:-true}}"
WAIT_SEC="${WAIT_SEC:-${SIMCTL_CARLA_LOCALIZATION_BRIDGE_WAIT_SEC:-60}}"
KILL_MONITOR_SEC="${KILL_MONITOR_SEC:-${SIMCTL_CARLA_LOCALIZATION_BRIDGE_KILL_MONITOR_SEC:-45}}"
ROS_TOPIC_LIST_TIMEOUT_SEC="${SIMCTL_ROS_TOPIC_LIST_TIMEOUT_SEC:-5}"
BRIDGE_SCRIPT="${REPO_ROOT}/stack/stable/carla_localization_bridge.py"

source_runtime_environment() {
  local nounset_was_enabled=0
  if [[ "$-" == *u* ]]; then
    nounset_was_enabled=1
    set +u
  fi
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
  # shellcheck disable=SC1090
  source "${AUTOWARE_WS}/install/setup.bash"
  if [[ -f "${AUTOWARE_BRIDGE_WS}/install/setup.bash" ]]; then
    # shellcheck disable=SC1090
    source "${AUTOWARE_BRIDGE_WS}/install/setup.bash"
  fi
  if [[ "${nounset_was_enabled}" -eq 1 ]]; then
    set -u
  fi
}

wait_for_topic() {
  local topic="$1"
  local deadline=$((SECONDS + WAIT_SEC))
  while [[ "${SECONDS}" -lt "${deadline}" ]]; do
    if timeout "${ROS_TOPIC_LIST_TIMEOUT_SEC}s" ros2 topic list 2>/dev/null | grep -Fxq "${topic}"; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for ROS topic ${topic}" >&2
  return 1
}

stop_simple_planning_simulator_once() {
  if [[ "${KILL_SIMPLE_SIM}" != "true" && "${KILL_SIMPLE_SIM}" != "1" ]]; then
    echo "Skipping simple planning simulator stop"
    return
  fi
  pkill -f "autoware_simple_planning_simulator_node" 2>/dev/null || true
  pkill -f "autoware_simple_planning_simulator" 2>/dev/null || true
  echo "Requested simple planning simulator stop"
}

start_simple_planning_simulator_stop_monitor() {
  if [[ "${KILL_SIMPLE_SIM}" != "true" && "${KILL_SIMPLE_SIM}" != "1" ]]; then
    return
  fi
  (
    local deadline=$((SECONDS + KILL_MONITOR_SEC))
    while [[ "${SECONDS}" -lt "${deadline}" ]]; do
      pkill -f "autoware_simple_planning_simulator_node" 2>/dev/null || true
      pkill -f "autoware_simple_planning_simulator" 2>/dev/null || true
      sleep 1
    done
  ) &
  echo "Started simple planning simulator stop monitor for ${KILL_MONITOR_SEC}s"
}

echo "Scenario: ${SCENARIO}"
echo "SlotId: ${SLOT_ID}"
echo "RunDir: ${RUN_DIR}"
echo "Autoware workspace: ${AUTOWARE_WS}"
echo "Autoware bridge workspace: ${AUTOWARE_BRIDGE_WS}"
echo "CARLA root: ${CARLA_ROOT}"
echo "CARLA host: ${CARLA_HOST}"
echo "CARLA port: ${CARLA_PORT}"
echo "CARLA ego role: ${EGO_VEHICLE_ROLE_NAME}"
echo "Localization source: ${LOCALIZATION_SOURCE}"
echo "ROS y sign: ${ROS_Y_SIGN_VALUE}"
echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "RMW_IMPLEMENTATION: ${RMW_IMPLEMENTATION_VALUE}"
echo "Runtime namespace: ${RUNTIME_NAMESPACE}"
echo "CPU Affinity: ${CPU_AFFINITY}"
echo "Kill simple simulator: ${KILL_SIMPLE_SIM}"
echo "WaitSec: ${WAIT_SEC}"
echo "KillMonitorSec: ${KILL_MONITOR_SEC}"
echo "RosTopicListTimeoutSec: ${ROS_TOPIC_LIST_TIMEOUT_SEC}"
echo "BridgeScript: ${BRIDGE_SCRIPT}"

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ ! -f "${AUTOWARE_WS}/install/setup.bash" ]]; then
    echo "Autoware setup script not found at ${AUTOWARE_WS}/install/setup.bash" >&2
    exit 1
  fi
  if [[ ! -f "${BRIDGE_SCRIPT}" ]]; then
    echo "CARLA localization bridge script not found at ${BRIDGE_SCRIPT}" >&2
    exit 1
  fi
  if [[ "${LOCALIZATION_SOURCE}" == "carla_actor" && -z "${CARLA_ROOT}" ]]; then
    echo "CARLA root is required for carla_actor localization source" >&2
    exit 1
  fi
  source_runtime_environment
  export ROS_DOMAIN_ID="${ROS_DOMAIN_ID}"
  if [[ -n "${RMW_IMPLEMENTATION_VALUE}" ]]; then
    export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION_VALUE}"
  fi
  export ROS2CLI_DISABLE_DAEMON=1
  export PYTHONNOUSERSITE=1
  if [[ -n "${CARLA_ROOT}" ]]; then
    CARLA_DIST_PYTHONPATH=""
    for carla_dist in "${CARLA_ROOT}"/PythonAPI/carla/dist/carla-*.egg "${CARLA_ROOT}"/PythonAPI/carla/dist/carla-*.whl; do
      if [[ -e "${carla_dist}" ]]; then
        CARLA_DIST_PYTHONPATH="${CARLA_DIST_PYTHONPATH:+${CARLA_DIST_PYTHONPATH}:}${carla_dist}"
      fi
    done
    if [[ -n "${CARLA_DIST_PYTHONPATH}" ]]; then
      export PYTHONPATH="${CARLA_DIST_PYTHONPATH}:${PYTHONPATH:-}"
    fi
    if [[ -d "${CARLA_ROOT}/PythonAPI/carla" ]]; then
      export PYTHONPATH="${PYTHONPATH:-}:${CARLA_ROOT}/PythonAPI/carla"
    fi
  fi
  export SIMCTL_RUNTIME_NAMESPACE="${RUNTIME_NAMESPACE}"
  export SIMCTL_CARLA_LOCALIZATION_SOURCE="${LOCALIZATION_SOURCE}"
  export SIMCTL_CARLA_HOST="${CARLA_HOST}"
  export SIMCTL_CARLA_RPC_PORT="${CARLA_PORT}"
  export SIMCTL_CARLA_EGO_ROLE_NAME="${EGO_VEHICLE_ROLE_NAME}"
  if [[ -n "${ROS_Y_SIGN_VALUE}" ]]; then
    export SIMCTL_CARLA_ROS_Y_SIGN="${ROS_Y_SIGN_VALUE}"
  fi
  wait_for_topic "/sensing/gnss/pose_with_covariance"
  wait_for_topic "/vehicle/status/velocity_status"
  stop_simple_planning_simulator_once
  start_simple_planning_simulator_stop_monitor
  if [[ -n "${CPU_AFFINITY}" ]]; then
    exec taskset -c "${CPU_AFFINITY}" python3 "${BRIDGE_SCRIPT}"
  fi
  exec python3 "${BRIDGE_SCRIPT}"
fi
