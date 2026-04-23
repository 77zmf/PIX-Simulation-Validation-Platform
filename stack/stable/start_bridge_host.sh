#!/usr/bin/env bash
set -euo pipefail

SCENARIO=""
RUN_DIR=""
ASSET_BUNDLE=""
SLOT_ID=""
CARLA_PORT=""
TRAFFIC_MANAGER_PORT=""
ROS_DOMAIN_ID=""
RMW_IMPLEMENTATION_ARG=""
RUNTIME_NAMESPACE=""
CPU_AFFINITY=""
AUTOWARE_WS_ARG=""
AUTOWARE_UNDERLAY_WS=""
VEHICLE_TYPE=""
CARLA_MAP=""
SPAWN_POINT=""
EGO_VEHICLE_ROLE_NAME=""
SENSOR_KIT_NAME=""
SENSOR_MAPPING_FILE=""
SENSOR_KIT_CALIBRATION_FILE=""
OBJECTS_DEFINITION_FILE=""
USE_TRAFFIC_MANAGER=""
BRIDGE_TIMEOUT=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario) SCENARIO="$2"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --asset-bundle) ASSET_BUNDLE="$2"; shift 2 ;;
    --slot-id) SLOT_ID="$2"; shift 2 ;;
    --carla-port) CARLA_PORT="$2"; shift 2 ;;
    --traffic-manager-port) TRAFFIC_MANAGER_PORT="$2"; shift 2 ;;
    --ros-domain-id) ROS_DOMAIN_ID="$2"; shift 2 ;;
    --rmw-implementation) RMW_IMPLEMENTATION_ARG="$2"; shift 2 ;;
    --runtime-namespace) RUNTIME_NAMESPACE="$2"; shift 2 ;;
    --cpu-affinity) CPU_AFFINITY="$2"; shift 2 ;;
    --autoware-ws) AUTOWARE_WS_ARG="$2"; shift 2 ;;
    --autoware-underlay-ws) AUTOWARE_UNDERLAY_WS="$2"; shift 2 ;;
    --vehicle-type) VEHICLE_TYPE="$2"; shift 2 ;;
    --carla-map) CARLA_MAP="$2"; shift 2 ;;
    --spawn-point) SPAWN_POINT="$2"; shift 2 ;;
    --ego-vehicle-role-name) EGO_VEHICLE_ROLE_NAME="$2"; shift 2 ;;
    --sensor-kit-name) SENSOR_KIT_NAME="$2"; shift 2 ;;
    --sensor-mapping-file) SENSOR_MAPPING_FILE="$2"; shift 2 ;;
    --sensor-kit-calibration-file) SENSOR_KIT_CALIBRATION_FILE="$2"; shift 2 ;;
    --objects-definition-file) OBJECTS_DEFINITION_FILE="$2"; shift 2 ;;
    --use-traffic-manager) USE_TRAFFIC_MANAGER="$2"; shift 2 ;;
    --timeout) BRIDGE_TIMEOUT="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

AUTOWARE_WS="${AUTOWARE_WS_ARG:-${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/autoware}}"
AUTOWARE_SETUP="${AUTOWARE_WS}/install/setup.bash"
BRIDGE_LAUNCH_FILE="${AUTOWARE_WS}/install/autoware_carla_interface/share/autoware_carla_interface/autoware_carla_interface.launch.xml"
CARLA_PORT="${CARLA_PORT:-2000}"
TRAFFIC_MANAGER_PORT="${TRAFFIC_MANAGER_PORT:-8000}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-21}"
RMW_IMPLEMENTATION_VALUE="${RMW_IMPLEMENTATION_ARG:-${RMW_IMPLEMENTATION:-}}"
VEHICLE_TYPE="${VEHICLE_TYPE:-${CARLA_VEHICLE_TYPE:-vehicle.toyota.prius}}"
CARLA_MAP="${CARLA_MAP:-${SIMCTL_CARLA_MAP:-Town01}}"
EGO_VEHICLE_ROLE_NAME="${EGO_VEHICLE_ROLE_NAME:-${CARLA_EGO_VEHICLE_ROLE_NAME:-ego_vehicle}}"
USE_TRAFFIC_MANAGER="${USE_TRAFFIC_MANAGER:-${CARLA_USE_TRAFFIC_MANAGER:-False}}"
BRIDGE_TIMEOUT="${BRIDGE_TIMEOUT:-${CARLA_BRIDGE_TIMEOUT:-${SIMCTL_CARLA_BRIDGE_TIMEOUT:-90}}}"
PIX_SKIP_WHEEL_STEER_ANGLE="${PIX_CARLA_SKIP_WHEEL_STEER_ANGLE:-}"
PIX_STEER_GAIN="${PIX_CARLA_STEER_GAIN:-}"
PIX_THROTTLE_GAIN="${PIX_CARLA_THROTTLE_GAIN:-}"
PIX_MIN_THROTTLE="${PIX_CARLA_MIN_THROTTLE:-}"
PIX_MAX_THROTTLE="${PIX_CARLA_MAX_THROTTLE:-}"
PIX_CREEP_THROTTLE="${PIX_CARLA_CREEP_THROTTLE:-}"
PIX_CREEP_SPEED_THRESHOLD_MPS="${PIX_CARLA_CREEP_SPEED_THRESHOLD_MPS:-}"
PIX_BRAKE_GAIN="${PIX_CARLA_BRAKE_GAIN:-}"
PIX_MAX_BRAKE="${PIX_CARLA_MAX_BRAKE:-}"
PIX_BRAKE_DEADBAND="${PIX_CARLA_BRAKE_DEADBAND:-}"
if [[ "${VEHICLE_TYPE}" == vehicle.pixmoving.* ]]; then
  PIX_STEER_GAIN="${PIX_STEER_GAIN:-1.04}"
  PIX_THROTTLE_GAIN="${PIX_THROTTLE_GAIN:-3.8}"
  PIX_MIN_THROTTLE="${PIX_MIN_THROTTLE:-0.0}"
  PIX_MAX_THROTTLE="${PIX_MAX_THROTTLE:-0.65}"
  PIX_CREEP_THROTTLE="${PIX_CREEP_THROTTLE:-0.0}"
  PIX_CREEP_SPEED_THRESHOLD_MPS="${PIX_CREEP_SPEED_THRESHOLD_MPS:-0.08}"
  PIX_BRAKE_GAIN="${PIX_BRAKE_GAIN:-0.2}"
  PIX_MAX_BRAKE="${PIX_MAX_BRAKE:-0.8}"
  PIX_BRAKE_DEADBAND="${PIX_BRAKE_DEADBAND:-0.05}"
fi

shell_quote() {
  printf "%q" "$1"
}

launch_supports_arg() {
  local arg_name="$1"
  if [[ ! -f "${BRIDGE_LAUNCH_FILE}" ]]; then
    return 0
  fi
  grep -Eq "<arg[[:space:]][^>]*name=[\"']${arg_name}[\"']" "${BRIDGE_LAUNCH_FILE}"
}

LAUNCH_ARGS=("host:=127.0.0.1" "port:=${CARLA_PORT}")
SKIPPED_LAUNCH_ARGS=()

add_launch_arg_if_supported() {
  local arg_name="$1"
  local arg_value="$2"
  if [[ -z "${arg_value}" ]]; then
    return
  fi
  if launch_supports_arg "${arg_name}"; then
    LAUNCH_ARGS+=("${arg_name}:=${arg_value}")
  else
    SKIPPED_LAUNCH_ARGS+=("${arg_name}")
  fi
}

add_launch_arg_if_supported "vehicle_type" "${VEHICLE_TYPE}"
add_launch_arg_if_supported "carla_map" "${CARLA_MAP}"
add_launch_arg_if_supported "spawn_point" "${SPAWN_POINT}"
add_launch_arg_if_supported "ego_vehicle_role_name" "${EGO_VEHICLE_ROLE_NAME}"
add_launch_arg_if_supported "sensor_kit_name" "${SENSOR_KIT_NAME}"
add_launch_arg_if_supported "sensor_mapping_file" "${SENSOR_MAPPING_FILE}"
add_launch_arg_if_supported "objects_definition_file" "${OBJECTS_DEFINITION_FILE}"
add_launch_arg_if_supported "use_traffic_manager" "${USE_TRAFFIC_MANAGER}"
add_launch_arg_if_supported "timeout" "${BRIDGE_TIMEOUT}"

SOURCE_STEPS=("source /opt/ros/humble/setup.bash")
if [[ -n "${AUTOWARE_UNDERLAY_WS}" ]]; then
  IFS=':' read -r -a UNDERLAY_WS_LIST <<< "${AUTOWARE_UNDERLAY_WS}"
  for underlay_ws in "${UNDERLAY_WS_LIST[@]}"; do
    if [[ -n "${underlay_ws}" ]]; then
      SOURCE_STEPS+=("source $(shell_quote "${underlay_ws}/install/setup.bash")")
    fi
  done
fi
SOURCE_STEPS+=("source $(shell_quote "${AUTOWARE_SETUP}")")

SOURCE_CMD=""
for source_step in "${SOURCE_STEPS[@]}"; do
  if [[ -z "${SOURCE_CMD}" ]]; then
    SOURCE_CMD="${source_step}"
  else
    SOURCE_CMD+=" && ${source_step}"
  fi
done
ROS_CMD=("ros2" "launch" "autoware_carla_interface" "autoware_carla_interface.launch.xml" "${LAUNCH_ARGS[@]}")
ROS_CMD_DISPLAY=""
for cmd_part in "${ROS_CMD[@]}"; do
  ROS_CMD_DISPLAY+=" $(shell_quote "${cmd_part}")"
done
ROS_CMD_DISPLAY="${ROS_CMD_DISPLAY# }"
RMW_EXPORT_CMD=""
if [[ -n "${RMW_IMPLEMENTATION_VALUE}" ]]; then
  RMW_EXPORT_CMD=" && export RMW_IMPLEMENTATION=$(shell_quote "${RMW_IMPLEMENTATION_VALUE}")"
fi
PIX_BRIDGE_EXPORT_CMD=""
if [[ -n "${PIX_SKIP_WHEEL_STEER_ANGLE}" ]]; then
  PIX_BRIDGE_EXPORT_CMD=" && export PIX_CARLA_SKIP_WHEEL_STEER_ANGLE=$(shell_quote "${PIX_SKIP_WHEEL_STEER_ANGLE}")"
fi
if [[ -n "${PIX_STEER_GAIN}" ]]; then
  PIX_BRIDGE_EXPORT_CMD+=" && export PIX_CARLA_STEER_GAIN=$(shell_quote "${PIX_STEER_GAIN}")"
fi
if [[ -n "${PIX_THROTTLE_GAIN}" ]]; then
  PIX_BRIDGE_EXPORT_CMD+=" && export PIX_CARLA_THROTTLE_GAIN=$(shell_quote "${PIX_THROTTLE_GAIN}")"
fi
if [[ -n "${PIX_MIN_THROTTLE}" ]]; then
  PIX_BRIDGE_EXPORT_CMD+=" && export PIX_CARLA_MIN_THROTTLE=$(shell_quote "${PIX_MIN_THROTTLE}")"
fi
if [[ -n "${PIX_MAX_THROTTLE}" ]]; then
  PIX_BRIDGE_EXPORT_CMD+=" && export PIX_CARLA_MAX_THROTTLE=$(shell_quote "${PIX_MAX_THROTTLE}")"
fi
if [[ -n "${PIX_CREEP_THROTTLE}" ]]; then
  PIX_BRIDGE_EXPORT_CMD+=" && export PIX_CARLA_CREEP_THROTTLE=$(shell_quote "${PIX_CREEP_THROTTLE}")"
fi
if [[ -n "${PIX_CREEP_SPEED_THRESHOLD_MPS}" ]]; then
  PIX_BRIDGE_EXPORT_CMD+=" && export PIX_CARLA_CREEP_SPEED_THRESHOLD_MPS=$(shell_quote "${PIX_CREEP_SPEED_THRESHOLD_MPS}")"
fi
if [[ -n "${PIX_BRAKE_GAIN}" ]]; then
  PIX_BRIDGE_EXPORT_CMD+=" && export PIX_CARLA_BRAKE_GAIN=$(shell_quote "${PIX_BRAKE_GAIN}")"
fi
if [[ -n "${PIX_MAX_BRAKE}" ]]; then
  PIX_BRIDGE_EXPORT_CMD+=" && export PIX_CARLA_MAX_BRAKE=$(shell_quote "${PIX_MAX_BRAKE}")"
fi
if [[ -n "${PIX_BRAKE_DEADBAND}" ]]; then
  PIX_BRIDGE_EXPORT_CMD+=" && export PIX_CARLA_BRAKE_DEADBAND=$(shell_quote "${PIX_BRAKE_DEADBAND}")"
fi
CMD="${SOURCE_CMD} && export ROS_DOMAIN_ID=${ROS_DOMAIN_ID}${RMW_EXPORT_CMD} && export SIMCTL_RUNTIME_NAMESPACE=$(shell_quote "${RUNTIME_NAMESPACE}") && export SIMCTL_TRAFFIC_MANAGER_PORT=${TRAFFIC_MANAGER_PORT}${PIX_BRIDGE_EXPORT_CMD} && ${ROS_CMD_DISPLAY}"

source_runtime_environment() {
  local nounset_was_enabled=0
  if [[ "$-" == *u* ]]; then
    nounset_was_enabled=1
    set +u
  fi
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
  if [[ -n "${AUTOWARE_UNDERLAY_WS}" ]]; then
    IFS=':' read -r -a UNDERLAY_WS_LIST <<< "${AUTOWARE_UNDERLAY_WS}"
    for underlay_ws in "${UNDERLAY_WS_LIST[@]}"; do
      if [[ -n "${underlay_ws}" ]]; then
        # shellcheck disable=SC1090
        source "${underlay_ws}/install/setup.bash"
      fi
    done
  fi
  # shellcheck disable=SC1090
  source "${AUTOWARE_SETUP}"
  if [[ "${nounset_was_enabled}" -eq 1 ]]; then
    set -u
  fi
}

install_sensor_kit_calibration() {
  if [[ -z "${SENSOR_KIT_NAME}" || -z "${SENSOR_KIT_CALIBRATION_FILE}" ]]; then
    return
  fi
  if ! launch_supports_arg "sensor_kit_name"; then
    return
  fi
  if [[ ! -f "${SENSOR_KIT_CALIBRATION_FILE}" ]]; then
    echo "Sensor kit calibration file not found at ${SENSOR_KIT_CALIBRATION_FILE}" >&2
    exit 1
  fi
  local prefix
  prefix="$(ros2 pkg prefix "${SENSOR_KIT_NAME}" 2>/dev/null || true)"
  if [[ -z "${prefix}" ]]; then
    echo "ROS package not found for sensor kit ${SENSOR_KIT_NAME}" >&2
    exit 1
  fi
  local config_dir="${prefix}/share/${SENSOR_KIT_NAME}/config"
  mkdir -p "${config_dir}"
  install -m 0644 "${SENSOR_KIT_CALIBRATION_FILE}" "${config_dir}/sensor_kit_calibration.yaml"
  echo "Sensor kit calibration installed: ${config_dir}/sensor_kit_calibration.yaml"
}

echo "Scenario: ${SCENARIO}"
echo "SlotId: ${SLOT_ID}"
echo "RunDir: ${RUN_DIR}"
echo "AssetBundle: ${ASSET_BUNDLE}"
echo "Bridge Autoware workspace: ${AUTOWARE_WS}"
echo "Bridge Autoware underlay workspace: ${AUTOWARE_UNDERLAY_WS}"
echo "Bridge launch file: ${BRIDGE_LAUNCH_FILE}"
echo "CARLA RPC Port: ${CARLA_PORT}"
echo "Traffic Manager Port: ${TRAFFIC_MANAGER_PORT}"
echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "RMW_IMPLEMENTATION: ${RMW_IMPLEMENTATION_VALUE}"
echo "Runtime namespace: ${RUNTIME_NAMESPACE}"
echo "CPU Affinity: ${CPU_AFFINITY}"
echo "CARLA map: ${CARLA_MAP}"
echo "CARLA vehicle type: ${VEHICLE_TYPE}"
echo "CARLA spawn point: ${SPAWN_POINT}"
echo "CARLA ego role: ${EGO_VEHICLE_ROLE_NAME}"
echo "CARLA sensor kit: ${SENSOR_KIT_NAME}"
echo "CARLA sensor mapping: ${SENSOR_MAPPING_FILE}"
echo "CARLA sensor kit calibration: ${SENSOR_KIT_CALIBRATION_FILE}"
echo "CARLA objects definition: ${OBJECTS_DEFINITION_FILE}"
echo "CARLA use traffic manager: ${USE_TRAFFIC_MANAGER}"
echo "CARLA bridge timeout: ${BRIDGE_TIMEOUT}"
echo "PIX skip wheel steer angle: ${PIX_SKIP_WHEEL_STEER_ANGLE}"
echo "PIX steer gain: ${PIX_STEER_GAIN}"
echo "PIX throttle gain: ${PIX_THROTTLE_GAIN}"
echo "PIX min throttle: ${PIX_MIN_THROTTLE}"
echo "PIX max throttle: ${PIX_MAX_THROTTLE}"
echo "PIX creep throttle: ${PIX_CREEP_THROTTLE}"
echo "PIX creep speed threshold mps: ${PIX_CREEP_SPEED_THRESHOLD_MPS}"
echo "PIX brake gain: ${PIX_BRAKE_GAIN}"
echo "PIX max brake: ${PIX_MAX_BRAKE}"
echo "PIX brake deadband: ${PIX_BRAKE_DEADBAND}"
if [[ "${#SKIPPED_LAUNCH_ARGS[@]}" -gt 0 ]]; then
  echo "Skipped unsupported launch args: ${SKIPPED_LAUNCH_ARGS[*]}"
fi
echo "Command: ${CMD}"

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ ! -f "$AUTOWARE_SETUP" ]]; then
    echo "Autoware setup script not found at ${AUTOWARE_SETUP}" >&2
    exit 1
  fi
  if [[ -n "$AUTOWARE_UNDERLAY_WS" ]]; then
    IFS=':' read -r -a UNDERLAY_WS_LIST <<< "${AUTOWARE_UNDERLAY_WS}"
    for underlay_ws in "${UNDERLAY_WS_LIST[@]}"; do
      if [[ -n "${underlay_ws}" && ! -f "${underlay_ws}/install/setup.bash" ]]; then
        echo "Autoware underlay setup script not found at ${underlay_ws}/install/setup.bash" >&2
        exit 1
      fi
    done
  fi
  source_runtime_environment
  install_sensor_kit_calibration
  export ROS_DOMAIN_ID="${ROS_DOMAIN_ID}"
  if [[ -n "${RMW_IMPLEMENTATION_VALUE}" ]]; then
    export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION_VALUE}"
  fi
  export SIMCTL_RUNTIME_NAMESPACE="${RUNTIME_NAMESPACE}"
  export SIMCTL_TRAFFIC_MANAGER_PORT="${TRAFFIC_MANAGER_PORT}"
  if [[ -n "${PIX_SKIP_WHEEL_STEER_ANGLE}" ]]; then
    export PIX_CARLA_SKIP_WHEEL_STEER_ANGLE="${PIX_SKIP_WHEEL_STEER_ANGLE}"
  fi
  if [[ -n "${PIX_STEER_GAIN}" ]]; then
    export PIX_CARLA_STEER_GAIN="${PIX_STEER_GAIN}"
  fi
  if [[ -n "${PIX_THROTTLE_GAIN}" ]]; then
    export PIX_CARLA_THROTTLE_GAIN="${PIX_THROTTLE_GAIN}"
  fi
  if [[ -n "${PIX_MIN_THROTTLE}" ]]; then
    export PIX_CARLA_MIN_THROTTLE="${PIX_MIN_THROTTLE}"
  fi
  if [[ -n "${PIX_MAX_THROTTLE}" ]]; then
    export PIX_CARLA_MAX_THROTTLE="${PIX_MAX_THROTTLE}"
  fi
  if [[ -n "${PIX_CREEP_THROTTLE}" ]]; then
    export PIX_CARLA_CREEP_THROTTLE="${PIX_CREEP_THROTTLE}"
  fi
  if [[ -n "${PIX_CREEP_SPEED_THRESHOLD_MPS}" ]]; then
    export PIX_CARLA_CREEP_SPEED_THRESHOLD_MPS="${PIX_CREEP_SPEED_THRESHOLD_MPS}"
  fi
  if [[ -n "${PIX_BRAKE_GAIN}" ]]; then
    export PIX_CARLA_BRAKE_GAIN="${PIX_BRAKE_GAIN}"
  fi
  if [[ -n "${PIX_MAX_BRAKE}" ]]; then
    export PIX_CARLA_MAX_BRAKE="${PIX_MAX_BRAKE}"
  fi
  if [[ -n "${PIX_BRAKE_DEADBAND}" ]]; then
    export PIX_CARLA_BRAKE_DEADBAND="${PIX_BRAKE_DEADBAND}"
  fi
  if [[ -n "$CPU_AFFINITY" ]]; then
    exec taskset -c "$CPU_AFFINITY" "${ROS_CMD[@]}"
  fi
  exec "${ROS_CMD[@]}"
fi
