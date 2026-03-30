#!/usr/bin/env bash
set -euo pipefail

EXECUTE=0
if [[ "${1:-}" == "-Execute" || "${1:-}" == "--execute" ]]; then
  EXECUTE=1
fi

echo "Preparing company Ubuntu host for Autoware Universe + CARLA"
echo "EXECUTE=${EXECUTE}"

if sudo dpkg --audit | grep -q .; then
  echo "[FAIL] dpkg audit reports broken packages. Fix host package state before continuing." >&2
  echo "[HINT] Previous server notes showed agnocast / DKMS conflicts can block Autoware dependency installation." >&2
  sudo dpkg --audit || true
  exit 1
fi

if [[ -n "${CONDA_PREFIX:-}" ]]; then
  echo "[WARN] Conda environment detected: ${CONDA_PREFIX}"
  echo "[WARN] Autoware setup scripts may expect the system Python instead of conda-managed python3."
fi

COMMANDS=(
  "sudo apt-get update"
  "sudo apt-get install -y curl git python3-pip python3-venv build-essential software-properties-common ninja-build"
  "sudo apt-get install -y ros-humble-desktop python3-colcon-common-extensions python3-rosdep python3-vcstool"
  "sudo rosdep init || true"
  "rosdep update"
)

for cmd in "${COMMANDS[@]}"; do
  echo "$cmd"
  if [[ "$EXECUTE" -eq 1 ]]; then
    eval "$cmd"
  fi
done

echo "Recommended workspace defaults for the current stable path:"
echo "- CARLA runtime root: ~/CARLA_0.9.15"
echo "- Autoware workspace: ~/zmf_ws/projects/autoware_universe/autoware"
echo
echo "Next operator-controlled steps:"
echo "- verify or install CARLA 0.9.15 runtime under CARLA_0915_ROOT"
echo "- verify or create AUTOWARE_WS and import autoware.repos"
echo "- keep planning/control and E2E shadow validation on the same UE4.26 runtime baseline"
