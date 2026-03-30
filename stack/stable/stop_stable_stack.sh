#!/usr/bin/env bash
set -euo pipefail

RUN_DIR=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

PID_DIR=""
if [[ -n "$RUN_DIR" ]]; then
  PID_DIR="${RUN_DIR}/pids"
fi

echo "Stopping stable stack"
echo "RunDir: ${RUN_DIR}"
echo "PidDir: ${PID_DIR}"

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ -z "$PID_DIR" || ! -d "$PID_DIR" ]]; then
    echo "No pid directory found for this run" >&2
    exit 1
  fi

  mapfile -t PID_FILES < <(find "$PID_DIR" -maxdepth 1 -type f -name '*.pid' | sort -r)
  for pid_file in "${PID_FILES[@]}"; do
    pid="$(tr -d '\r\n' < "$pid_file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done

  sleep 1

  for pid_file in "${PID_FILES[@]}"; do
    pid="$(tr -d '\r\n' < "$pid_file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  done
fi
