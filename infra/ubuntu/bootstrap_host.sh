#!/usr/bin/env bash
set -euo pipefail

EXECUTE=0
if [[ "${1:-}" == "-Execute" || "${1:-}" == "--execute" ]]; then
  EXECUTE=1
fi

echo "Preparing company Ubuntu host for Autoware Universe + CARLA 0.9.15"
echo "EXECUTE=${EXECUTE}"

COMMANDS=(
  "sudo apt-get update"
  "sudo apt-get install -y curl git python3-pip python3-venv build-essential software-properties-common"
  "sudo apt-get install -y ros-humble-desktop python3-colcon-common-extensions python3-rosdep"
  "sudo rosdep init || true"
  "rosdep update"
)

for cmd in "${COMMANDS[@]}"; do
  echo "$cmd"
  if [[ "$EXECUTE" -eq 1 ]]; then
    eval "$cmd"
  fi
done

echo "Next operator-controlled steps:"
echo "- install or point CARLA_0915_ROOT to the CARLA 0.9.15 host path"
echo "- clone Autoware Universe into AUTOWARE_WS"
echo "- run rosdep install and the first colcon build"
