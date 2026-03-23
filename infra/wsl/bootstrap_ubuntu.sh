#!/usr/bin/env bash
set -euo pipefail

EXECUTE=0
if [[ "${1:-}" == "-Execute" || "${1:-}" == "--execute" ]]; then
  EXECUTE=1
fi

echo "Preparing Ubuntu 22.04 / ROS 2 Humble / Autoware host"
echo "EXECUTE=${EXECUTE}"

COMMANDS=(
  "sudo apt-get update"
  "sudo apt-get install -y curl git python3-pip python3-venv build-essential"
  "sudo apt-get install -y software-properties-common"
  "sudo apt-get install -y ros-humble-desktop python3-colcon-common-extensions"
)

for cmd in "${COMMANDS[@]}"; do
  echo "$cmd"
  if [[ "$EXECUTE" -eq 1 ]]; then
    eval "$cmd"
  fi
done

echo "Autoware source checkout and workspace-specific tuning should happen after ROS 2 is verified."
