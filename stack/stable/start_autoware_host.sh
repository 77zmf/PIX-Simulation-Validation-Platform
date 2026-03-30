#!/usr/bin/env bash
set -euo pipefail

SCENARIO=""
RUN_DIR=""
ASSET_BUNDLE=""
SLOT_ID=""
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
    --ros-domain-id) ROS_DOMAIN_ID="$2"; shift 2 ;;
    --runtime-namespace) RUNTIME_NAMESPACE="$2"; shift 2 ;;
    --cpu-affinity) CPU_AFFINITY="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

AUTOWARE_WS="${AUTOWARE_WS:-$HOME/autoware_ws}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-21}"
CMD="cd ${AUTOWARE_WS} && source install/setup.bash && export ROS_DOMAIN_ID=${ROS_DOMAIN_ID} && export ROS_NAMESPACE='${RUNTIME_NAMESPACE}' && ros2 launch autoware_launch planning_simulator.launch.xml"
echo "Scenario: ${SCENARIO}"
echo "SlotId: ${SLOT_ID}"
echo "RunDir: ${RUN_DIR}"
echo "AssetBundle: ${ASSET_BUNDLE}"
echo "Autoware workspace: ${AUTOWARE_WS}"
echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "Runtime namespace: ${RUNTIME_NAMESPACE}"
echo "CPU Affinity: ${CPU_AFFINITY}"
echo "Command: ${CMD}"

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ -n "$CPU_AFFINITY" ]]; then
    exec taskset -c "$CPU_AFFINITY" bash -lc "${CMD}"
  fi
  exec bash -lc "${CMD}"
fi
