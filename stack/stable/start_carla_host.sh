#!/usr/bin/env bash
set -euo pipefail

RUN_DIR=""
ASSET_ROOT=""
SLOT_ID=""
CARLA_PORT=""
TRAFFIC_MANAGER_PORT=""
GPU_ID=""
CPU_AFFINITY=""
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
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

CARLA_ROOT="${CARLA_0915_ROOT:-$HOME/CARLA_0.9.15}"
CARLA_SH="${CARLA_ROOT}/CarlaUE4.sh"
CARLA_PORT="${CARLA_PORT:-2000}"
TRAFFIC_MANAGER_PORT="${TRAFFIC_MANAGER_PORT:-8000}"
CMD="\"${CARLA_SH}\" -RenderOffScreen -carla-rpc-port=${CARLA_PORT}"

echo "CARLA root: ${CARLA_ROOT}"
echo "SlotId: ${SLOT_ID}"
echo "RunDir: ${RUN_DIR}"
echo "AssetRoot: ${ASSET_ROOT}"
echo "CARLA RPC Port: ${CARLA_PORT}"
echo "Traffic Manager Port: ${TRAFFIC_MANAGER_PORT}"
echo "GPU: ${GPU_ID}"
echo "CPU Affinity: ${CPU_AFFINITY}"
echo "Command: ${CMD}"

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ ! -x "$CARLA_SH" ]]; then
    echo "CARLA executable not found at ${CARLA_SH}" >&2
    exit 1
  fi
  if [[ -n "$GPU_ID" ]]; then
    export CUDA_VISIBLE_DEVICES="$GPU_ID"
  fi
  if [[ -n "$CPU_AFFINITY" ]]; then
    exec taskset -c "$CPU_AFFINITY" bash -lc "${CMD}"
  fi
  exec bash -lc "${CMD}"
fi
