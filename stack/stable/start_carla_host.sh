#!/usr/bin/env bash
set -euo pipefail

RUN_DIR=""
ASSET_ROOT=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --asset-root) ASSET_ROOT="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

CARLA_ROOT="${CARLA_0915_ROOT:-$HOME/CARLA_0.9.15}"
CARLA_SH="${CARLA_ROOT}/CarlaUE4.sh"
CMD="\"${CARLA_SH}\" -RenderOffScreen -carla-rpc-port=2000"

echo "CARLA root: ${CARLA_ROOT}"
echo "RunDir: ${RUN_DIR}"
echo "AssetRoot: ${ASSET_ROOT}"
echo "Command: ${CMD}"

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ ! -x "$CARLA_SH" ]]; then
    echo "CARLA executable not found at ${CARLA_SH}" >&2
    exit 1
  fi
  bash -lc "${CMD}"
fi
