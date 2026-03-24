#!/usr/bin/env bash
set -euo pipefail

EXECUTE=0
if [[ "${1:-}" == "-Execute" || "${1:-}" == "--execute" ]]; then
  EXECUTE=1
fi

CARLA_SOURCE_PARENT="${CARLA_SOURCE_PARENT:-$HOME/zmf_ws/projects/carla_source}"
CARLA_SOURCE_ROOT="${CARLA_SOURCE_ROOT:-$CARLA_SOURCE_PARENT/CarlaUE5}"
CARLA_UNREAL_ENGINE_PATH_DEFAULT="${CARLA_UNREAL_ENGINE_PATH:-$CARLA_SOURCE_PARENT/UnrealEngine5_carla}"

echo "CARLA source parent: ${CARLA_SOURCE_PARENT}"
echo "CARLA source root: ${CARLA_SOURCE_ROOT}"
echo "CARLA Unreal Engine path: ${CARLA_UNREAL_ENGINE_PATH_DEFAULT}"
echo "EXECUTE=${EXECUTE}"

COMMANDS=(
  "mkdir -p '${CARLA_SOURCE_PARENT}'"
  "cd '${CARLA_SOURCE_PARENT}' && if [[ ! -d '${CARLA_SOURCE_ROOT}' ]]; then git clone -b ue5-dev https://github.com/carla-simulator/carla.git CarlaUE5; fi"
  "cd '${CARLA_SOURCE_ROOT}' && ./CarlaSetup.sh --interactive"
)

for cmd in "${COMMANDS[@]}"; do
  echo "$cmd"
  if [[ "$EXECUTE" -eq 1 ]]; then
    bash -lc "$cmd"
  fi
done

echo
echo "After setup, export the Unreal path if needed:"
echo "export CARLA_UNREAL_ENGINE_PATH='${CARLA_UNREAL_ENGINE_PATH_DEFAULT}'"
echo
echo "Recommended build commands:"
echo "cd '${CARLA_SOURCE_ROOT}'"
echo "cmake -G Ninja -S . -B Build --toolchain=\$PWD/CMake/Toolchain.cmake -DCMAKE_BUILD_TYPE=Release -DENABLE_ROS2=ON"
echo "cmake --build Build"
echo "cmake --build Build --target carla-python-api-install"
echo "cmake --build Build --target launch"
