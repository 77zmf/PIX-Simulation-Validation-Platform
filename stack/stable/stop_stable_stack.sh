#!/usr/bin/env bash
set -euo pipefail

RUN_DIR=""
CARLA_PORT=""
TRAFFIC_MANAGER_PORT=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --carla-port) CARLA_PORT="$2"; shift 2 ;;
    --traffic-manager-port) TRAFFIC_MANAGER_PORT="$2"; shift 2 ;;
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
echo "CARLA RPC Port: ${CARLA_PORT}"
echo "Traffic Manager Port: ${TRAFFIC_MANAGER_PORT}"

collect_process_tree() {
  local root_pid="$1"
  local child_pid
  for child_pid in $(pgrep -P "$root_pid" 2>/dev/null || true); do
    collect_process_tree "$child_pid"
  done
  echo "$root_pid"
}

collect_unique_stop_pids() {
  printf '%s\n' "$@" | awk 'NF' | awk '!seen[$0]++'
}

stop_pid_group() {
  local root_pid="$1"
  local signal="$2"
  if [[ -n "$root_pid" ]]; then
    kill "-${signal}" "-${root_pid}" 2>/dev/null || true
  fi
}

stop_pid_list() {
  local signal="$1"
  shift
  local pid
  for pid in "$@"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "-${signal}" "$pid" 2>/dev/null || true
    fi
  done
}

port_listener_pids() {
  local port="$1"
  if [[ -z "$port" ]]; then
    return 0
  fi
  ss -ltnp 2>/dev/null \
    | awk -v port=":${port}" '$4 ~ port "$" {print $0}' \
    | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' \
    | awk '!seen[$0]++'
}

stop_port_listeners() {
  local port="$1"
  local signal="$2"
  local listener_pid
  for listener_pid in $(port_listener_pids "$port"); do
    stop_pid_group "$listener_pid" "$signal"
    stop_pid_list "$signal" "$listener_pid"
  done
}

if [[ "$EXECUTE" -eq 1 ]]; then
  if [[ -z "$PID_DIR" || ! -d "$PID_DIR" ]]; then
    echo "No pid directory found for this run" >&2
    exit 1
  fi

  mapfile -t PID_FILES < <(find "$PID_DIR" -maxdepth 1 -type f -name '*.pid' | sort -r)
  ROOT_PIDS=()
  STOP_PIDS=()
  for pid_file in "${PID_FILES[@]}"; do
    pid="$(tr -d '\r\n' < "$pid_file")"
    if [[ -n "$pid" ]]; then
      ROOT_PIDS+=("$pid")
      stop_pid_group "$pid" TERM
    fi
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      mapfile -t TREE_PIDS < <(collect_process_tree "$pid")
      STOP_PIDS+=("${TREE_PIDS[@]}")
    fi
  done
  mapfile -t STOP_PIDS < <(collect_unique_stop_pids "${STOP_PIDS[@]:-}")
  stop_pid_list TERM "${STOP_PIDS[@]:-}"

  sleep 3

  for pid in "${ROOT_PIDS[@]:-}"; do
    stop_pid_group "$pid" KILL
  done

  for pid in "${STOP_PIDS[@]:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      stop_pid_group "$pid" KILL
    fi
  done
  stop_pid_list KILL "${STOP_PIDS[@]:-}"

  stop_port_listeners "$CARLA_PORT" TERM
  stop_port_listeners "$TRAFFIC_MANAGER_PORT" TERM
  sleep 1
  stop_port_listeners "$CARLA_PORT" KILL
  stop_port_listeners "$TRAFFIC_MANAGER_PORT" KILL

  for pid_file in "${PID_FILES[@]}"; do
    rm -f "$pid_file"
  done
fi
