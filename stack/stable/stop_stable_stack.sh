#!/usr/bin/env bash
set -euo pipefail

RUN_DIR=""
CARLA_PORT=""
TRAFFIC_MANAGER_PORT=""
SUMO_TRACI_PORT=""
ROS_DOMAIN_ID=""
RMW_IMPLEMENTATION_ARG=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --carla-port) CARLA_PORT="$2"; shift 2 ;;
    --traffic-manager-port) TRAFFIC_MANAGER_PORT="$2"; shift 2 ;;
    --sumo-traci-port) SUMO_TRACI_PORT="$2"; shift 2 ;;
    --ros-domain-id) ROS_DOMAIN_ID="$2"; shift 2 ;;
    --rmw-implementation) RMW_IMPLEMENTATION_ARG="$2"; shift 2 ;;
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
echo "SUMO TraCI Port: ${SUMO_TRACI_PORT}"
echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "RMW_IMPLEMENTATION: ${RMW_IMPLEMENTATION_ARG}"

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

matching_pids() {
  local pattern="$1"
  ps -eo pid=,cmd= \
    | awk -v pattern="$pattern" '$0 ~ pattern {print $1}' \
    | awk '!seen[$0]++'
}

collect_stable_auxiliary_ros_pids() {
  matching_pids '/opt/ros/humble/lib/topic_tools/relay /sensing/camera'
  matching_pids '/opt/ros/humble/lib/image_transport/republish raw compressed'
  matching_pids '/opt/ros/humble/lib/robot_state_publisher/robot_state_publisher .*__node:=robot_state_publisher'
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

cleanup_fastdds_shm() {
  if [[ "${SIMCTL_CLEAN_FASTDDS_SHM:-1}" == "0" ]]; then
    echo "Skipping FastDDS shared-memory cleanup because SIMCTL_CLEAN_FASTDDS_SHM=0"
    return
  fi
  local removed_count
  removed_count="$(
    find /dev/shm -maxdepth 1 -user "$(id -u)" \( -name 'fastrtps_*' -o -name 'sem.fastrtps_*' -o -name 'fastdds*' \) -print -delete 2>/dev/null \
      | wc -l
  )"
  echo "FastDDS shared-memory files removed: ${removed_count//[[:space:]]/}"
}

stop_ros2_daemon() {
  if [[ "${SIMCTL_STOP_ROS2_DAEMON:-1}" == "0" ]]; then
    echo "Skipping ROS 2 daemon stop because SIMCTL_STOP_ROS2_DAEMON=0"
    return
  fi
  if [[ ! -f /opt/ros/humble/setup.bash ]] || ! command -v bash >/dev/null 2>&1; then
    echo "Skipping ROS 2 daemon stop because ROS 2 setup is unavailable"
    return
  fi
  local rmw_values=("${RMW_IMPLEMENTATION_ARG}" "rmw_cyclonedds_cpp" "rmw_fastrtps_cpp" "")
  local rmw_value
  for rmw_value in "${rmw_values[@]}"; do
    local daemon_cmd="source /opt/ros/humble/setup.bash >/dev/null 2>&1 && "
    if [[ -n "${ROS_DOMAIN_ID}" ]]; then
      daemon_cmd+="export ROS_DOMAIN_ID=${ROS_DOMAIN_ID} && "
    fi
    if [[ -n "${rmw_value}" ]]; then
      daemon_cmd+="export RMW_IMPLEMENTATION='${rmw_value}' && "
    fi
    daemon_cmd+="ros2 daemon stop >/dev/null 2>&1 || true"
    bash -lc "${daemon_cmd}"
  done
  echo "ROS 2 daemon stop requested"
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
    fi
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      mapfile -t TREE_PIDS < <(collect_process_tree "$pid")
      STOP_PIDS+=("${TREE_PIDS[@]}")
    fi
  done
  mapfile -t AUXILIARY_ROS_PIDS < <(collect_stable_auxiliary_ros_pids)
  STOP_PIDS+=("${AUXILIARY_ROS_PIDS[@]:-}")
  mapfile -t STOP_PIDS < <(collect_unique_stop_pids "${STOP_PIDS[@]:-}")
  for pid in "${ROOT_PIDS[@]:-}"; do
    stop_pid_group "$pid" TERM
  done
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
  stop_port_listeners "$SUMO_TRACI_PORT" TERM
  sleep 1
  stop_port_listeners "$CARLA_PORT" KILL
  stop_port_listeners "$TRAFFIC_MANAGER_PORT" KILL
  stop_port_listeners "$SUMO_TRACI_PORT" KILL

  for pid_file in "${PID_FILES[@]}"; do
    rm -f "$pid_file"
  done
  stop_ros2_daemon
  cleanup_fastdds_shm
fi
