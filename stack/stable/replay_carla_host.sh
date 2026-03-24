#!/usr/bin/env bash
set -euo pipefail

RECORDER_PATH="${1:-}"
if [[ -z "$RECORDER_PATH" ]]; then
  echo "Usage: $0 <recorder_path>" >&2
  exit 2
fi

echo "Replay CARLA recorder from: ${RECORDER_PATH}"
echo "Use CARLA 0.9.15 PythonAPI or manual replayer on the company Ubuntu host."
