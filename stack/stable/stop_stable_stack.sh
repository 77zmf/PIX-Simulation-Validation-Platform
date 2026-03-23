#!/usr/bin/env bash
set -euo pipefail

EXECUTE=0
if [[ "${1:-}" == "-Execute" || "${1:-}" == "--execute" ]]; then
  EXECUTE=1
fi

echo "Stopping Autoware and bridge processes"
if [[ "$EXECUTE" -eq 1 ]]; then
  pkill -f autoware || true
  pkill -f autoware_carla_interface || true
fi
