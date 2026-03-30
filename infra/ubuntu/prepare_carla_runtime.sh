#!/usr/bin/env bash
set -euo pipefail

EXECUTE=0
if [[ "${1:-}" == "-Execute" || "${1:-}" == "--execute" ]]; then
  EXECUTE=1
fi

CARLA_RUNTIME_ROOT="${CARLA_0915_ROOT:-$HOME/CARLA_0.9.15}"
CARLA_RUNTIME_PARENT="$(dirname "$CARLA_RUNTIME_ROOT")"

echo "CARLA runtime root: ${CARLA_RUNTIME_ROOT}"
echo "EXECUTE=${EXECUTE}"

COMMANDS=(
  "mkdir -p '${CARLA_RUNTIME_PARENT}'"
)

for cmd in "${COMMANDS[@]}"; do
  echo "$cmd"
  if [[ "$EXECUTE" -eq 1 ]]; then
    bash -lc "$cmd"
  fi
done

if [[ -d "$CARLA_RUNTIME_ROOT" ]]; then
  echo "[OK] Existing CARLA 0.9.15 runtime found at ${CARLA_RUNTIME_ROOT}"
  if [[ -x "$CARLA_RUNTIME_ROOT/CarlaUE4.sh" ]]; then
    echo "[OK] CarlaUE4.sh is available"
  else
    echo "[WARN] CarlaUE4.sh is missing under ${CARLA_RUNTIME_ROOT}"
  fi
else
  echo "[WARN] CARLA 0.9.15 runtime is not present yet."
  echo "[HINT] Extract the official CARLA 0.9.15 Linux package to ${CARLA_RUNTIME_ROOT}"
fi

echo
echo "Recommended validation command:"
echo "bash '${CARLA_RUNTIME_ROOT}/CarlaUE4.sh' -RenderOffScreen -carla-rpc-port=2000"
