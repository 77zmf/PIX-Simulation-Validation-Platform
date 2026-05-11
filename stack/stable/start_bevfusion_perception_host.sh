#!/usr/bin/env bash
set -euo pipefail

SCENARIO=""
RUN_DIR=""
SLOT_ID=""
ROS_DOMAIN_ID=""
RMW_IMPLEMENTATION_ARG=""
CPU_AFFINITY=""
AUTOWARE_WS_ARG=""
EXTRA_SETUP=""
INPUT_POINTCLOUD=""
OUTPUT_OBJECTS=""
DATA_PATH=""
MODEL_NAME=""
LOG_LEVEL=""
BUILD_ONLY=""
MODEL_PARAM_PATH=""
ML_PACKAGE_PARAM_PATH=""
CLASS_REMAPPER_PARAM_PATH=""
COMMON_PARAM_PATH=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario) SCENARIO="$2"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --slot-id) SLOT_ID="$2"; shift 2 ;;
    --ros-domain-id) ROS_DOMAIN_ID="$2"; shift 2 ;;
    --rmw-implementation) RMW_IMPLEMENTATION_ARG="$2"; shift 2 ;;
    --cpu-affinity) CPU_AFFINITY="$2"; shift 2 ;;
    --autoware-ws) AUTOWARE_WS_ARG="$2"; shift 2 ;;
    --extra-setup) EXTRA_SETUP="$2"; shift 2 ;;
    --input-pointcloud) INPUT_POINTCLOUD="$2"; shift 2 ;;
    --output-objects) OUTPUT_OBJECTS="$2"; shift 2 ;;
    --data-path) DATA_PATH="$2"; shift 2 ;;
    --model-name) MODEL_NAME="$2"; shift 2 ;;
    --log-level) LOG_LEVEL="$2"; shift 2 ;;
    --build-only) BUILD_ONLY="$2"; shift 2 ;;
    --model-param-path) MODEL_PARAM_PATH="$2"; shift 2 ;;
    --ml-package-param-path) ML_PACKAGE_PARAM_PATH="$2"; shift 2 ;;
    --class-remapper-param-path) CLASS_REMAPPER_PARAM_PATH="$2"; shift 2 ;;
    --common-param-path) COMMON_PARAM_PATH="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

AUTOWARE_WS="${AUTOWARE_WS_ARG:-${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/private_autoware}}"
EXTRA_SETUP="${EXTRA_SETUP:-${BEVFUSION_EXTRA_SETUP:-}}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-21}"
RMW_IMPLEMENTATION_VALUE="${RMW_IMPLEMENTATION_ARG:-${RMW_IMPLEMENTATION:-}}"
INPUT_POINTCLOUD="${INPUT_POINTCLOUD:-/sensing/lidar/top/pointcloud_before_sync}"
OUTPUT_OBJECTS="${OUTPUT_OBJECTS:-/perception/object_recognition/detection/bevfusion/objects}"
DATA_PATH="${DATA_PATH:-${BEVFUSION_DATA_PATH:-$HOME/autoware_data}}"
MODEL_NAME="${MODEL_NAME:-${BEVFUSION_MODEL_NAME:-bevfusion_lidar}}"
LOG_LEVEL="${LOG_LEVEL:-${BEVFUSION_LOG_LEVEL:-info}}"
BUILD_ONLY="${BUILD_ONLY:-${BEVFUSION_BUILD_ONLY:-false}}"
MODEL_PARAM_PATH="${MODEL_PARAM_PATH:-${BEVFUSION_MODEL_PARAM_PATH:-}}"
ML_PACKAGE_PARAM_PATH="${ML_PACKAGE_PARAM_PATH:-${BEVFUSION_ML_PACKAGE_PARAM_PATH:-}}"
CLASS_REMAPPER_PARAM_PATH="${CLASS_REMAPPER_PARAM_PATH:-${BEVFUSION_CLASS_REMAPPER_PARAM_PATH:-}}"
COMMON_PARAM_PATH="${COMMON_PARAM_PATH:-${BEVFUSION_COMMON_PARAM_PATH:-}}"

RMW_EXPORT=""
if [[ -n "$RMW_IMPLEMENTATION_VALUE" ]]; then
  RMW_EXPORT="export RMW_IMPLEMENTATION='${RMW_IMPLEMENTATION_VALUE}' && "
fi

MODEL_PARAM_ARG=""
if [[ -n "$MODEL_PARAM_PATH" ]]; then
  MODEL_PARAM_ARG=" model_param_path:='${MODEL_PARAM_PATH}'"
fi
ML_PACKAGE_PARAM_ARG=""
if [[ -n "$ML_PACKAGE_PARAM_PATH" ]]; then
  ML_PACKAGE_PARAM_ARG=" ml_package_param_path:='${ML_PACKAGE_PARAM_PATH}'"
fi
CLASS_REMAPPER_PARAM_ARG=""
if [[ -n "$CLASS_REMAPPER_PARAM_PATH" ]]; then
  CLASS_REMAPPER_PARAM_ARG=" class_remapper_param_path:='${CLASS_REMAPPER_PARAM_PATH}'"
fi
COMMON_PARAM_ARG=""
if [[ -n "$COMMON_PARAM_PATH" ]]; then
  COMMON_PARAM_ARG=" common_param_path:='${COMMON_PARAM_PATH}'"
fi

EXTRA_SETUP_CHAIN=""
if [[ -n "$EXTRA_SETUP" ]]; then
  IFS=':' read -r -a EXTRA_SETUP_PATHS <<< "$EXTRA_SETUP"
  for setup_path in "${EXTRA_SETUP_PATHS[@]}"; do
    if [[ -n "$setup_path" ]]; then
      EXTRA_SETUP_CHAIN+="source '${setup_path}' && "
    fi
  done
fi

CMD="cd ${AUTOWARE_WS} && ${EXTRA_SETUP_CHAIN}source install/setup.bash && export ROS_DOMAIN_ID=${ROS_DOMAIN_ID} && export ROS2CLI_DISABLE_DAEMON=1 && export PYTHONNOUSERSITE=1 && ${RMW_EXPORT}ros2 launch autoware_bevfusion bevfusion.launch.xml input/pointcloud:='${INPUT_POINTCLOUD}' output/objects:='${OUTPUT_OBJECTS}' data_path:='${DATA_PATH}' model_name:='${MODEL_NAME}' build_only:='${BUILD_ONLY}' log_level:='${LOG_LEVEL}'${MODEL_PARAM_ARG}${ML_PACKAGE_PARAM_ARG}${CLASS_REMAPPER_PARAM_ARG}${COMMON_PARAM_ARG}"

echo "Scenario: ${SCENARIO}"
echo "SlotId: ${SLOT_ID}"
echo "RunDir: ${RUN_DIR}"
echo "Autoware workspace: ${AUTOWARE_WS}"
echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "RMW_IMPLEMENTATION: ${RMW_IMPLEMENTATION_VALUE}"
echo "CPU Affinity: ${CPU_AFFINITY}"
echo "BEVFusion extra setup: ${EXTRA_SETUP}"
echo "BEVFusion input pointcloud: ${INPUT_POINTCLOUD}"
echo "BEVFusion output objects: ${OUTPUT_OBJECTS}"
echo "BEVFusion data path: ${DATA_PATH}"
echo "BEVFusion model name: ${MODEL_NAME}"
echo "BEVFusion build only: ${BUILD_ONLY}"
echo "BEVFusion model param path: ${MODEL_PARAM_PATH}"
echo "BEVFusion ml package param path: ${ML_PACKAGE_PARAM_PATH}"
echo "BEVFusion class remapper param path: ${CLASS_REMAPPER_PARAM_PATH}"
echo "BEVFusion common param path: ${COMMON_PARAM_PATH}"
echo "Command: ${CMD}"

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ ! -f "${AUTOWARE_WS}/install/setup.bash" ]]; then
    echo "Autoware setup script not found at ${AUTOWARE_WS}/install/setup.bash" >&2
    exit 1
  fi
  if [[ -n "$EXTRA_SETUP" ]]; then
    IFS=':' read -r -a EXTRA_SETUP_PATHS <<< "$EXTRA_SETUP"
    for setup_path in "${EXTRA_SETUP_PATHS[@]}"; do
      if [[ -n "$setup_path" && ! -f "$setup_path" ]]; then
        echo "BEVFusion extra setup script not found at ${setup_path}" >&2
        exit 1
      fi
    done
  fi
  if [[ -n "$CPU_AFFINITY" ]]; then
    exec taskset -c "$CPU_AFFINITY" bash -lc "${CMD}"
  fi
  exec bash -lc "${CMD}"
fi
