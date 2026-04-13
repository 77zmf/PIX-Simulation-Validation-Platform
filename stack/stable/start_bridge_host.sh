#!/usr/bin/env bash
set -euo pipefail

SCENARIO=""
RUN_DIR=""
ASSET_BUNDLE=""
SLOT_ID=""
CARLA_PORT=""
TRAFFIC_MANAGER_PORT=""
ROS_DOMAIN_ID=""
RUNTIME_NAMESPACE=""
CPU_AFFINITY=""
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
    --runtime-namespace) RUNTIME_NAMESPACE="$2"; shift 2 ;;
    --cpu-affinity) CPU_AFFINITY="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

AUTOWARE_WS="${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/autoware}"
AUTOWARE_SETUP="${AUTOWARE_WS}/install/setup.bash"
CARLA_PORT="${CARLA_PORT:-2000}"
TRAFFIC_MANAGER_PORT="${TRAFFIC_MANAGER_PORT:-8000}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-21}"
CMD="source /opt/ros/humble/setup.bash && source '${AUTOWARE_SETUP}' && export ROS_DOMAIN_ID=${ROS_DOMAIN_ID} && export SIMCTL_RUNTIME_NAMESPACE='${RUNTIME_NAMESPACE}' && export SIMCTL_TRAFFIC_MANAGER_PORT=${TRAFFIC_MANAGER_PORT} && ros2 launch autoware_carla_interface autoware_carla_interface.launch.xml host:=127.0.0.1 port:=${CARLA_PORT}"
echo "Scenario: ${SCENARIO}"
echo "SlotId: ${SLOT_ID}"
echo "RunDir: ${RUN_DIR}"
echo "AssetBundle: ${ASSET_BUNDLE}"
echo "Autoware workspace: ${AUTOWARE_WS}"
echo "CARLA RPC Port: ${CARLA_PORT}"
echo "Traffic Manager Port: ${TRAFFIC_MANAGER_PORT}"
echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "Runtime namespace: ${RUNTIME_NAMESPACE}"
echo "CPU Affinity: ${CPU_AFFINITY}"
echo "Command: ${CMD}"

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ ! -f "$AUTOWARE_SETUP" ]]; then
    echo "Autoware setup script not found at ${AUTOWARE_SETUP}" >&2
    exit 1
  fi
  if [[ -n "$CPU_AFFINITY" ]]; then
    exec taskset -c "$CPU_AFFINITY" bash -lc "${CMD}"
  fi
  exec bash -lc "${CMD}"
fi
