#!/usr/bin/env bash
set -euo pipefail

RUN_DIR=""
ASSET_ROOT=""
SLOT_ID=""
CARLA_PORT=""
TRAFFIC_MANAGER_PORT=""
GPU_ID=""
CPU_AFFINITY=""
CARLA_MAP_ARG=""
RENDER_MODE=""
RES_X=""
RES_Y=""
QUALITY_LEVEL=""
EXTRA_ARGS=""
DISPLAY_ARG=""
XAUTHORITY_ARG=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --asset-root) ASSET_ROOT="$2"; shift 2 ;;
    --slot-id) SLOT_ID="$2"; shift 2 ;;
    --carla-port) CARLA_PORT="$2"; shift 2 ;;
    --traffic-manager-port) TRAFFIC_MANAGER_PORT="$2"; shift 2 ;;
    --gpu-id) GPU_ID="$2"; shift 2 ;;
    --cpu-affinity) CPU_AFFINITY="$2"; shift 2 ;;
    --carla-map) CARLA_MAP_ARG="$2"; shift 2 ;;
    --render-mode) RENDER_MODE="$2"; shift 2 ;;
    --render-offscreen)
      if [[ "${2:-}" == "false" || "${2:-}" == "0" || "${2:-}" == "no" ]]; then
        RENDER_MODE="visual"
      else
        RENDER_MODE="offscreen"
      fi
      shift 2
      ;;
    --visual) RENDER_MODE="visual"; shift ;;
    --res-x) RES_X="$2"; shift 2 ;;
    --res-y) RES_Y="$2"; shift 2 ;;
    --quality-level) QUALITY_LEVEL="$2"; shift 2 ;;
    --extra-args) EXTRA_ARGS="$2"; shift 2 ;;
    --display) DISPLAY_ARG="$2"; shift 2 ;;
    --xauthority) XAUTHORITY_ARG="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

CARLA_ROOT="${CARLA_0915_ROOT:-$HOME/CARLA_0.9.15}"
CARLA_SH="${CARLA_ROOT}/CarlaUE4.sh"
CARLA_PORT="${CARLA_PORT:-2000}"
TRAFFIC_MANAGER_PORT="${TRAFFIC_MANAGER_PORT:-8000}"
CARLA_MAP_ARG="${CARLA_MAP_ARG:-${CARLA_MAP:-}}"
RENDER_MODE="${RENDER_MODE:-${CARLA_RENDER_MODE:-offscreen}}"
RES_X="${RES_X:-${CARLA_RES_X:-}}"
RES_Y="${RES_Y:-${CARLA_RES_Y:-}}"
QUALITY_LEVEL="${QUALITY_LEVEL:-${CARLA_QUALITY_LEVEL:-}}"
EXTRA_ARGS="${EXTRA_ARGS:-${CARLA_EXTRA_ARGS:-}}"
DISPLAY_ARG="${DISPLAY_ARG:-${CARLA_DISPLAY:-}}"
XAUTHORITY_ARG="${XAUTHORITY_ARG:-${CARLA_XAUTHORITY:-}}"

resolve_carla_map() {
  local map_ref="$1"
  if [[ -z "$map_ref" ]]; then
    return 0
  fi
  if [[ "$map_ref" == /* || "$map_ref" == /Game/* ]]; then
    printf '%s\n' "$map_ref"
    return 0
  fi
  if [[ "$map_ref" == Town* ]]; then
    printf '/Game/Carla/Maps/%s\n' "$map_ref"
    return 0
  fi
  printf '%s\n' "$map_ref"
}

CARLA_MAP_PATH="$(resolve_carla_map "$CARLA_MAP_ARG")"
CMD=("${CARLA_SH}")
if [[ -n "$CARLA_MAP_PATH" ]]; then
  CMD+=("$CARLA_MAP_PATH")
fi

case "$RENDER_MODE" in
  ""|offscreen)
    RENDER_MODE="offscreen"
    CMD+=("-RenderOffScreen")
    ;;
  visual|windowed)
    RENDER_MODE="visual"
    RES_X="${RES_X:-1280}"
    RES_Y="${RES_Y:-720}"
    QUALITY_LEVEL="${QUALITY_LEVEL:-Low}"
    DISPLAY_ARG="${DISPLAY_ARG:-${DISPLAY:-:0}}"
    CMD+=("-windowed" "-ResX=${RES_X}" "-ResY=${RES_Y}")
    ;;
  *)
    echo "Unsupported render mode: ${RENDER_MODE}. Use offscreen or visual." >&2
    exit 2
    ;;
esac

CMD+=("-carla-rpc-port=${CARLA_PORT}")
if [[ -n "$QUALITY_LEVEL" ]]; then
  CMD+=("-quality-level=${QUALITY_LEVEL}")
fi
if [[ -n "$EXTRA_ARGS" ]]; then
  # shellcheck disable=SC2206
  EXTRA_ARG_ARRAY=($EXTRA_ARGS)
  CMD+=("${EXTRA_ARG_ARRAY[@]}")
fi
CMD_DISPLAY="$(printf '%q ' "${CMD[@]}")"

echo "CARLA root: ${CARLA_ROOT}"
echo "SlotId: ${SLOT_ID}"
echo "RunDir: ${RUN_DIR}"
echo "AssetRoot: ${ASSET_ROOT}"
echo "CARLA RPC Port: ${CARLA_PORT}"
echo "Traffic Manager Port: ${TRAFFIC_MANAGER_PORT}"
echo "GPU: ${GPU_ID}"
echo "CPU Affinity: ${CPU_AFFINITY}"
echo "CARLA map: ${CARLA_MAP_PATH}"
echo "Render mode: ${RENDER_MODE}"
echo "Resolution: ${RES_X:-default}x${RES_Y:-default}"
echo "Quality level: ${QUALITY_LEVEL:-default}"
echo "DISPLAY: ${DISPLAY_ARG:-${DISPLAY:-}}"
echo "XAUTHORITY: ${XAUTHORITY_ARG:-${XAUTHORITY:-}}"
echo "Command: ${CMD_DISPLAY}"

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ ! -x "$CARLA_SH" ]]; then
    echo "CARLA executable not found at ${CARLA_SH}" >&2
    exit 1
  fi
  if [[ -n "$GPU_ID" ]]; then
    export CUDA_VISIBLE_DEVICES="$GPU_ID"
  fi
  if [[ -n "$DISPLAY_ARG" ]]; then
    export DISPLAY="$DISPLAY_ARG"
  fi
  if [[ -n "$XAUTHORITY_ARG" ]]; then
    export XAUTHORITY="$XAUTHORITY_ARG"
  fi
  if [[ -n "$CPU_AFFINITY" ]]; then
    exec taskset -c "$CPU_AFFINITY" "${CMD[@]}"
  fi
  exec "${CMD[@]}"
fi
