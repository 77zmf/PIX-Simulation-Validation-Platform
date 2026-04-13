#!/usr/bin/env bash
set -euo pipefail

SCENARIO=""
RUN_DIR=""
ASSET_BUNDLE=""
SLOT_ID=""
ROS_DOMAIN_ID=""
RUNTIME_NAMESPACE=""
CPU_AFFINITY=""
MAP_PATH=""
VEHICLE_MODEL=""
SENSOR_MODEL=""
RVIZ=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario) SCENARIO="$2"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --asset-bundle) ASSET_BUNDLE="$2"; shift 2 ;;
    --slot-id) SLOT_ID="$2"; shift 2 ;;
    --ros-domain-id) ROS_DOMAIN_ID="$2"; shift 2 ;;
    --runtime-namespace) RUNTIME_NAMESPACE="$2"; shift 2 ;;
    --cpu-affinity) CPU_AFFINITY="$2"; shift 2 ;;
    --map-path) MAP_PATH="$2"; shift 2 ;;
    --vehicle-model) VEHICLE_MODEL="$2"; shift 2 ;;
    --sensor-model) SENSOR_MODEL="$2"; shift 2 ;;
    --rviz) RVIZ="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
AUTOWARE_WS="${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/autoware}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-21}"
MAP_PATH="${MAP_PATH:-${AUTOWARE_MAP_PATH:-${REPO_ROOT}}}"
VEHICLE_MODEL="${VEHICLE_MODEL:-${AUTOWARE_VEHICLE_MODEL:-sample_vehicle}}"
SENSOR_MODEL="${SENSOR_MODEL:-${AUTOWARE_SENSOR_MODEL:-carla_sensor_kit}}"
RVIZ="${RVIZ:-${AUTOWARE_RVIZ:-true}}"
CMD="cd ${AUTOWARE_WS} && source install/setup.bash && export ROS_DOMAIN_ID=${ROS_DOMAIN_ID} && export ROS_NAMESPACE='${RUNTIME_NAMESPACE}' && ros2 launch autoware_launch planning_simulator.launch.xml map_path:='${MAP_PATH}' vehicle_model:='${VEHICLE_MODEL}' sensor_model:='${SENSOR_MODEL}' rviz:='${RVIZ}'"
echo "Scenario: ${SCENARIO}"
echo "SlotId: ${SLOT_ID}"
echo "RunDir: ${RUN_DIR}"
echo "AssetBundle: ${ASSET_BUNDLE}"
echo "Autoware workspace: ${AUTOWARE_WS}"
echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "Runtime namespace: ${RUNTIME_NAMESPACE}"
echo "CPU Affinity: ${CPU_AFFINITY}"
echo "MapPath: ${MAP_PATH}"
echo "VehicleModel: ${VEHICLE_MODEL}"
echo "SensorModel: ${SENSOR_MODEL}"
echo "RVIZ: ${RVIZ}"
echo "Command: ${CMD}"

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ ! -f "${AUTOWARE_WS}/install/setup.bash" ]]; then
    echo "Autoware setup script not found at ${AUTOWARE_WS}/install/setup.bash" >&2
    exit 1
  fi
  if [[ -n "$CPU_AFFINITY" ]]; then
    exec taskset -c "$CPU_AFFINITY" bash -lc "${CMD}"
  fi
  exec bash -lc "${CMD}"
fi
