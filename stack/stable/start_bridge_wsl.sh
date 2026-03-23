#!/usr/bin/env bash
set -euo pipefail

SCENARIO=""
RUN_DIR=""
ASSET_BUNDLE=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario) SCENARIO="$2"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --asset-bundle) ASSET_BUNDLE="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

CMD="source /opt/ros/humble/setup.bash && ros2 launch autoware_carla_interface autoware_carla_interface.launch.xml"
echo "Scenario: ${SCENARIO}"
echo "RunDir: ${RUN_DIR}"
echo "AssetBundle: ${ASSET_BUNDLE}"
echo "Command: ${CMD}"

if [[ "$EXECUTE" -eq 1 ]]; then
  bash -lc "${CMD}"
fi
