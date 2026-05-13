#!/usr/bin/env bash
# No-ROS reconstruction capture helper for vehicle-side field data.
#
# This script intentionally does not call ros2, rosbag2, tf2, or any ROS graph
# API. It captures only side-channel evidence:
#   - IPC: raw UDP LiDAR packets with tcpdump.
#   - Orin: RGBA camera socket frames with GStreamer nvunixfdsrc.
#
# Use this when ROS subscriptions on the live vehicle must be avoided.

set -Eeuo pipefail
shopt -s nullglob

SCRIPT_NAME="$(basename "$0")"
SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"

ACTION="${1:-}"
if [[ -n "${ACTION}" ]]; then
  shift || true
fi

HOST="$(hostname | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_.-' '-')"
OWNER_USER="${SUDO_USER:-${USER:-$(id -un)}}"
if command -v getent >/dev/null 2>&1; then
  OWNER_HOME="$(getent passwd "${OWNER_USER}" | cut -d: -f6)"
else
  OWNER_HOME="$(eval "printf '%s' ~${OWNER_USER}" 2>/dev/null || printf '%s' "${HOME}")"
fi
if [[ -z "${OWNER_HOME}" || "${OWNER_HOME}" == "~${OWNER_USER}" ]]; then
  OWNER_HOME="${HOME}"
fi
STATE_DIR="${STATE_DIR:-${OWNER_HOME}/pix/.no_ros_reconstruction_capture}"

ROLE="auto"
OUT_ROOT=""
RUN_ID=""
LABEL="117_no_ros_recon"
DURATION_SEC=0

IFACE="any"
TCPDUMP_FILTER="${TCPDUMP_FILTER:-udp}"
TCPDUMP_BUFFER_KB="${TCPDUMP_BUFFER_KB:-262144}"
ROTATE_SECONDS="${ROTATE_SECONDS:-60}"
DISCOVER_SECONDS="${DISCOVER_SECONDS:-10}"

FPS=10
QUALITY=92
CAMERA_CHANNELS=()

FORCE=false

usage() {
  cat <<EOF
Usage:
  ${SCRIPT_NAME} discover --role ipc-lidar [--iface IFACE] [--seconds SEC] [--filter BPF]
  ${SCRIPT_NAME} start    --role ipc-lidar|orin-camera [options]
  ${SCRIPT_NAME} stop     --role ipc-lidar|orin-camera [--force]
  ${SCRIPT_NAME} status   --role ipc-lidar|orin-camera
  ${SCRIPT_NAME} summarize --run-dir DIR

Roles:
  ipc-lidar      Capture raw UDP packets to local PCAP files with tcpdump.
  orin-camera    Capture JPEG frames from Orin RGBA camera sockets.

Common options:
  --out-root DIR       Local output root.
                       ipc-lidar default:  /home/ipc/pix/road_tests/no_ros_reconstruction_capture
                       orin-camera default:/home/nvidia/pix/road_tests/no_ros_reconstruction_capture
  --label NAME         Run label prefix. Default: ${LABEL}
  --run-id NAME        Exact run id. Default: label_timestamp_host
  --duration SEC       0 means run until stop. Default: ${DURATION_SEC}

LiDAR options:
  --iface IFACE        tcpdump interface. Default: ${IFACE}
  --filter BPF         tcpdump BPF filter. Default: "${TCPDUMP_FILTER}"
  --rotate-sec SEC     PCAP file rotation interval. Default: ${ROTATE_SECONDS}
  --buffer-kb KB       tcpdump kernel buffer. Default: ${TCPDUMP_BUFFER_KB}
  --seconds SEC        discover duration. Default: ${DISCOVER_SECONDS}

Camera options:
  --channel NAME       Camera channel. Repeatable. Default: front_3mm,rear_3mm
  --all-channels       Capture front_3mm,front_left,front_right,rear_3mm,rear_left,rear_right
  --fps N              JPEG sampling rate. Default: ${FPS}
  --quality N          JPEG quality 1..100. Default: ${QUALITY}

Examples:
  # IPC passive discovery, no ROS:
  sudo ${SCRIPT_NAME} discover --role ipc-lidar --iface any --seconds 10

  # IPC local raw LiDAR capture:
  sudo ${SCRIPT_NAME} start --role ipc-lidar --duration 600
  sudo ${SCRIPT_NAME} stop --role ipc-lidar

  # Orin local front/rear 3mm camera capture:
  ${SCRIPT_NAME} start --role orin-camera --duration 600 --fps 10
  ${SCRIPT_NAME} stop --role orin-camera
EOF
}

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

die() {
  log "FATAL: $*" >&2
  exit 1
}

iso_now() {
  date -Is 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ'
}

safe_name() {
  printf '%s' "$1" | sed 's#[^A-Za-z0-9_.-]#_#g'
}

shell_join() {
  local out=()
  local item
  for item in "$@"; do
    out+=("$(printf '%q' "${item}")")
  done
  printf '%s ' "${out[@]}"
}

default_out_root() {
  case "$1" in
    ipc-lidar) printf '/home/ipc/pix/road_tests/no_ros_reconstruction_capture' ;;
    orin-camera) printf '/home/nvidia/pix/road_tests/no_ros_reconstruction_capture' ;;
    *) printf '%s/pix/road_tests/no_ros_reconstruction_capture' "${OWNER_HOME}" ;;
  esac
}

session_name() {
  case "$1" in
    ipc-lidar) printf 'no_ros_lidar_capture' ;;
    orin-camera) printf 'no_ros_camera_capture' ;;
    *) die "unknown role: $1" ;;
  esac
}

socket_for_channel() {
  case "$1" in
    front_3mm) printf '/tmp/camera_front_3mm_rgba_sink_1' ;;
    front_left) printf '/tmp/camera_front_left_rgba_sink_1' ;;
    front_right) printf '/tmp/camera_front_right_rgba_sink_1' ;;
    rear_3mm) printf '/tmp/camera_rear_3mm_rgba_sink_1' ;;
    rear_left) printf '/tmp/camera_rear_left_rgba_sink_1' ;;
    rear_right) printf '/tmp/camera_rear_right_rgba_sink_1' ;;
    *) return 1 ;;
  esac
}

all_camera_channels() {
  printf '%s\n' front_3mm front_left front_right rear_3mm rear_left rear_right
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --role) ROLE="${2:?missing role}"; shift 2 ;;
      --out-root) OUT_ROOT="${2:?missing output root}"; shift 2 ;;
      --label) LABEL="${2:?missing label}"; shift 2 ;;
      --run-id) RUN_ID="${2:?missing run id}"; shift 2 ;;
      --duration) DURATION_SEC="${2:?missing duration}"; shift 2 ;;
      --iface) IFACE="${2:?missing iface}"; shift 2 ;;
      --filter) TCPDUMP_FILTER="${2:?missing BPF filter}"; shift 2 ;;
      --rotate-sec) ROTATE_SECONDS="${2:?missing seconds}"; shift 2 ;;
      --buffer-kb) TCPDUMP_BUFFER_KB="${2:?missing KB}"; shift 2 ;;
      --seconds) DISCOVER_SECONDS="${2:?missing seconds}"; shift 2 ;;
      --channel) CAMERA_CHANNELS+=("${2:?missing channel}"); shift 2 ;;
      --all-channels) mapfile -t CAMERA_CHANNELS < <(all_camera_channels); shift ;;
      --fps) FPS="${2:?missing fps}"; shift 2 ;;
      --quality) QUALITY="${2:?missing quality}"; shift 2 ;;
      --force) FORCE=true; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown argument: $1" ;;
    esac
  done

  if [[ "${ROLE}" == "auto" ]]; then
    if [[ -S /tmp/camera_front_3mm_rgba_sink_1 || -S /tmp/camera_rear_3mm_rgba_sink_1 ]]; then
      ROLE="orin-camera"
    else
      ROLE="ipc-lidar"
    fi
  fi

  case "${ROLE}" in
    ipc-lidar|orin-camera) ;;
    *) die "--role must be ipc-lidar or orin-camera" ;;
  esac

  if [[ -z "${OUT_ROOT}" ]]; then
    OUT_ROOT="$(default_out_root "${ROLE}")"
  fi

  if [[ -z "${RUN_ID}" ]]; then
    RUN_ID="$(safe_name "${LABEL}")_$(date '+%Y%m%d_%H%M%S')_${HOST}"
  else
    RUN_ID="$(safe_name "${RUN_ID}")"
  fi

  if [[ "${ROLE}" == "orin-camera" && "${#CAMERA_CHANNELS[@]}" -eq 0 ]]; then
    CAMERA_CHANNELS=(front_3mm rear_3mm)
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

write_state() {
  mkdir -p "${STATE_DIR}"
  printf '%s\n' "$2" > "${STATE_DIR}/$1"
}

read_state() {
  local key="$1"
  [[ -r "${STATE_DIR}/${key}" ]] || return 1
  sed -n '1p' "${STATE_DIR}/${key}"
}

status_role() {
  parse_args "$@"
  local session
  session="$(session_name "${ROLE}")"
  printf 'role=%s\n' "${ROLE}"
  printf 'session=%s\n' "${session}"
  if tmux has-session -t "${session}" 2>/dev/null; then
    printf 'running=true\n'
  else
    printf 'running=false\n'
  fi
  if run_dir="$(read_state "${ROLE}.run_dir" 2>/dev/null)"; then
    printf 'run_dir=%s\n' "${run_dir}"
    summarize_run_dir "${run_dir}" || true
  fi
}

discover_lidar() {
  parse_args "$@"
  [[ "${ROLE}" == "ipc-lidar" ]] || die "discover currently supports --role ipc-lidar"
  [[ "${EUID}" -eq 0 ]] || die "LiDAR discovery needs packet capture privileges; run with sudo"
  require_command tcpdump

  mkdir -p "${OUT_ROOT}"
  local out="${OUT_ROOT}/discover_$(date '+%Y%m%d_%H%M%S')_${HOST}.log"
  log "passive UDP discovery: iface=${IFACE}, seconds=${DISCOVER_SECONDS}, filter=${TCPDUMP_FILTER}"
  set +e
  timeout --foreground --signal=INT "${DISCOVER_SECONDS}" \
    tcpdump -i "${IFACE}" -nn -tttt "${TCPDUMP_FILTER}" > "${out}" 2>&1
  local status="$?"
  set -e
  chown "${OWNER_USER}:${OWNER_USER}" "${out}" 2>/dev/null || true
  log "discover output: ${out} (status=${status})"
  awk '
    / IP / {
      src=$4; dst=$6; sub(/:$/, "", dst);
      pair=src " -> " dst;
      count[pair]++;
    }
    END {
      for (pair in count) print count[pair], pair;
    }
  ' "${out}" | sort -nr | head -30
}

start_role() {
  parse_args "$@"
  require_command tmux
  local session run_dir cmd channels_csv
  session="$(session_name "${ROLE}")"
  if tmux has-session -t "${session}" 2>/dev/null; then
    die "session already running: ${session}"
  fi

  run_dir="${OUT_ROOT}/${RUN_ID}"
  mkdir -p "${run_dir}" "${STATE_DIR}"
  write_state "${ROLE}.run_dir" "${run_dir}"
  write_state "${ROLE}.session" "${session}"

  {
    printf 'run_id=%s\n' "${RUN_ID}"
    printf 'role=%s\n' "${ROLE}"
    printf 'host=%s\n' "$(hostname)"
    printf 'owner_user=%s\n' "${OWNER_USER}"
    printf 'out_root=%s\n' "${OUT_ROOT}"
    printf 'run_dir=%s\n' "${run_dir}"
    printf 'duration_sec=%s\n' "${DURATION_SEC}"
    printf 'created_at=%s\n' "$(iso_now)"
    printf 'ros_policy=%s\n' "no ros2/rosbag/tf2 commands used by this script"
  } > "${run_dir}/capture_manifest.env"

  case "${ROLE}" in
    ipc-lidar)
      [[ "${EUID}" -eq 0 ]] || die "LiDAR capture needs packet capture privileges; run start with sudo"
      cmd="$(shell_join env RUN_DIR="${run_dir}" OWNER_USER="${OWNER_USER}" IFACE="${IFACE}" TCPDUMP_FILTER="${TCPDUMP_FILTER}" TCPDUMP_BUFFER_KB="${TCPDUMP_BUFFER_KB}" ROTATE_SECONDS="${ROTATE_SECONDS}" DURATION_SEC="${DURATION_SEC}" bash "${SCRIPT_PATH}" _lidar_worker)"
      ;;
    orin-camera)
      channels_csv="$(IFS=,; printf '%s' "${CAMERA_CHANNELS[*]}")"
      cmd="$(shell_join env RUN_DIR="${run_dir}" OWNER_USER="${OWNER_USER}" CAMERA_CHANNELS_CSV="${channels_csv}" FPS="${FPS}" QUALITY="${QUALITY}" DURATION_SEC="${DURATION_SEC}" bash "${SCRIPT_PATH}" _camera_worker)"
      ;;
    *) die "unknown role: ${ROLE}" ;;
  esac

  tmux new-session -d -s "${session}" "${cmd}"
  log "started ${ROLE}: session=${session}, run_dir=${run_dir}"
}

stop_role() {
  parse_args "$@"
  require_command tmux
  local session run_dir
  session="$(session_name "${ROLE}")"
  if ! tmux has-session -t "${session}" 2>/dev/null; then
    log "session not running: ${session}"
    return 0
  fi
  tmux send-keys -t "${session}" C-c
  for _ in $(seq 1 20); do
    if ! tmux has-session -t "${session}" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  if tmux has-session -t "${session}" 2>/dev/null; then
    if [[ "${FORCE}" == "true" ]]; then
      tmux kill-session -t "${session}"
      log "force killed session: ${session}"
    else
      die "session still running after Ctrl-C: ${session}; rerun stop --force if needed"
    fi
  fi
  if run_dir="$(read_state "${ROLE}.run_dir" 2>/dev/null)"; then
    summarize_run_dir "${run_dir}" || true
  fi
}

summarize_run_dir() {
  local run_dir="$1"
  [[ -d "${run_dir}" ]] || die "run dir not found: ${run_dir}"
  printf 'summary_run_dir=%s\n' "${run_dir}"
  find "${run_dir}" -maxdepth 2 -type f \( -name '*.pcap' -o -name '*.jpg' -o -name '*.log' -o -name '*.txt' -o -name '*.env' \) \
    -printf '%s %p\n' 2>/dev/null | awk '
      /\.pcap$/ {pcap_count++; pcap_bytes += $1}
      /\.jpg$/ {jpg_count++; jpg_bytes += $1}
      END {
        printf "pcap_count=%d\npcap_bytes=%d\njpg_count=%d\njpg_bytes=%d\n", pcap_count+0, pcap_bytes+0, jpg_count+0, jpg_bytes+0
      }
    '
  if [[ -r "${run_dir}/started_at.txt" ]]; then
    printf 'started_at=%s\n' "$(sed -n '1p' "${run_dir}/started_at.txt")"
  fi
  if [[ -r "${run_dir}/finished_at.txt" ]]; then
    printf 'finished_at=%s\n' "$(sed -n '1p' "${run_dir}/finished_at.txt")"
  fi
  find "${run_dir}" -maxdepth 2 -name 'frame_count.txt' -type f -print -exec cat {} \; 2>/dev/null | sed 's/^/frame_count: /' || true
}

lidar_worker() {
  local status=0
  mkdir -p "${RUN_DIR}"
  exec >> "${RUN_DIR}/worker.log" 2>&1
  trap 'log "interrupt received"; status=130' INT TERM

  log "LiDAR worker start"
  require_command tcpdump
  [[ "${EUID}" -eq 0 ]] || die "LiDAR worker must run as root"
  ip -o addr > "${RUN_DIR}/ip_addr_before.txt" 2>&1 || true
  ip -s link > "${RUN_DIR}/ip_link_stats_before.txt" 2>&1 || true
  df -h "${RUN_DIR}" > "${RUN_DIR}/disk_before.txt" 2>&1 || true
  iso_now > "${RUN_DIR}/started_at.txt"

  {
    printf 'iface=%s\n' "${IFACE}"
    printf 'tcpdump_filter=%s\n' "${TCPDUMP_FILTER}"
    printf 'tcpdump_buffer_kb=%s\n' "${TCPDUMP_BUFFER_KB}"
    printf 'rotate_seconds=%s\n' "${ROTATE_SECONDS}"
    printf 'duration_sec=%s\n' "${DURATION_SEC}"
  } >> "${RUN_DIR}/capture_manifest.env"

  log "tcpdump iface=${IFACE}, filter=${TCPDUMP_FILTER}, rotate=${ROTATE_SECONDS}s"
  set +e
  if (( DURATION_SEC > 0 )); then
    timeout --foreground --signal=INT "${DURATION_SEC}" \
      tcpdump -i "${IFACE}" -s 0 -B "${TCPDUMP_BUFFER_KB}" -nn \
        -G "${ROTATE_SECONDS}" -w "${RUN_DIR}/lidar_udp_%Y%m%d_%H%M%S.pcap" \
        "${TCPDUMP_FILTER}"
    status="$?"
  else
    tcpdump -i "${IFACE}" -s 0 -B "${TCPDUMP_BUFFER_KB}" -nn \
      -G "${ROTATE_SECONDS}" -w "${RUN_DIR}/lidar_udp_%Y%m%d_%H%M%S.pcap" \
      "${TCPDUMP_FILTER}"
    status="$?"
  fi
  set -e

  ip -s link > "${RUN_DIR}/ip_link_stats_after.txt" 2>&1 || true
  df -h "${RUN_DIR}" > "${RUN_DIR}/disk_after.txt" 2>&1 || true
  iso_now > "${RUN_DIR}/finished_at.txt"
  printf '%s\n' "${status}" > "${RUN_DIR}/capture_exit_status.txt"
  if [[ "${status}" == "124" || "${status}" == "130" ]]; then
    status=0
  fi
  chown -R "${OWNER_USER}:${OWNER_USER}" "${RUN_DIR}" 2>/dev/null || true
  log "LiDAR worker done status=${status}"
  exit "${status}"
}

camera_worker() {
  local status=0
  local pids=()
  mkdir -p "${RUN_DIR}"
  exec >> "${RUN_DIR}/worker.log" 2>&1

  cleanup_camera() {
    log "camera interrupt received"
    local pid
    for pid in "${pids[@]:-}"; do
      kill -INT "${pid}" 2>/dev/null || true
    done
    wait || true
    camera_finish 130
    exit 130
  }
  trap cleanup_camera INT TERM

  log "Camera worker start"
  require_command gst-launch-1.0
  require_command gst-inspect-1.0
  for element in nvunixfdsrc nvvideoconvert videoconvert videorate jpegenc multifilesink; do
    gst-inspect-1.0 "${element}" >/dev/null 2>&1 || die "missing GStreamer element: ${element}"
  done

  IFS=',' read -r -a channels <<< "${CAMERA_CHANNELS_CSV:-front_3mm,rear_3mm}"
  iso_now > "${RUN_DIR}/started_at.txt"
  df -h "${RUN_DIR}" > "${RUN_DIR}/disk_before.txt" 2>&1 || true
  camera_socket_status "${RUN_DIR}/socket_status.tsv" "${channels[@]}"
  {
    printf 'fps=%s\n' "${FPS}"
    printf 'quality=%s\n' "${QUALITY}"
    printf 'duration_sec=%s\n' "${DURATION_SEC}"
    printf 'camera_channels=%s\n' "${channels[*]}"
  } >> "${RUN_DIR}/capture_manifest.env"

  local channel
  for channel in "${channels[@]}"; do
    record_camera_channel "${channel}" &
    pids+=("$!")
  done
  for pid in "${pids[@]}"; do
    wait "${pid}" || status=1
  done
  camera_finish "${status}"
  exit "${status}"
}

camera_socket_status() {
  local out="$1"
  shift
  local channel socket status
  printf 'channel\tsocket\tstatus\n' > "${out}"
  for channel in "$@"; do
    socket="$(socket_for_channel "${channel}")" || socket="unknown"
    if [[ -S "${socket}" ]]; then
      status="present"
    else
      status="missing"
    fi
    printf '%s\t%s\t%s\n' "${channel}" "${socket}" "${status}" >> "${out}"
  done
}

record_camera_channel() {
  local channel="$1"
  local socket channel_dir status_file
  socket="$(socket_for_channel "${channel}")" || die "unknown channel: ${channel}"
  [[ -S "${socket}" ]] || die "socket not found for ${channel}: ${socket}"
  channel_dir="${RUN_DIR}/${channel}"
  mkdir -p "${channel_dir}"
  status_file="${channel_dir}/record_exit_status.txt"
  log "record camera ${channel}: ${DURATION_SEC}s @ ${FPS} fps -> ${channel_dir}"
  set +e
  if (( DURATION_SEC > 0 )); then
    timeout --foreground --signal=INT "${DURATION_SEC}" \
      gst-launch-1.0 -e \
        nvunixfdsrc socket-path="${socket}" \
        ! 'video/x-raw(memory:NVMM),format=RGB' \
        ! nvvideoconvert compute-hw=1 \
        ! 'video/x-raw,format=RGBA' \
        ! videoconvert \
        ! videorate \
        ! "video/x-raw,framerate=${FPS}/1" \
        ! jpegenc quality="${QUALITY}" \
        ! multifilesink location="${channel_dir}/frame_%06d.jpg" sync=false \
      > "${channel_dir}/gst_record.log" 2>&1
  else
    gst-launch-1.0 -e \
      nvunixfdsrc socket-path="${socket}" \
      ! 'video/x-raw(memory:NVMM),format=RGB' \
      ! nvvideoconvert compute-hw=1 \
      ! 'video/x-raw,format=RGBA' \
      ! videoconvert \
      ! videorate \
      ! "video/x-raw,framerate=${FPS}/1" \
      ! jpegenc quality="${QUALITY}" \
      ! multifilesink location="${channel_dir}/frame_%06d.jpg" sync=false \
      > "${channel_dir}/gst_record.log" 2>&1
  fi
  local status="$?"
  set -e
  printf '%s\n' "${status}" > "${status_file}"
  find "${channel_dir}" -maxdepth 1 -name 'frame_*.jpg' | sort > "${channel_dir}/frames.txt"
  wc -l "${channel_dir}/frames.txt" > "${channel_dir}/frame_count.txt"
  if [[ "${status}" == "0" || "${status}" == "124" || "${status}" == "130" ]]; then
    return 0
  fi
  return "${status}"
}

camera_finish() {
  local status="$1"
  df -h "${RUN_DIR}" > "${RUN_DIR}/disk_after.txt" 2>&1 || true
  iso_now > "${RUN_DIR}/finished_at.txt"
  printf '%s\n' "${status}" > "${RUN_DIR}/capture_exit_status.txt"
  summarize_run_dir "${RUN_DIR}" > "${RUN_DIR}/summary.env" 2>/dev/null || true
  chown -R "${OWNER_USER}:${OWNER_USER}" "${RUN_DIR}" 2>/dev/null || true
  log "Camera worker done status=${status}"
}

case "${ACTION}" in
  discover) discover_lidar "$@" ;;
  start) start_role "$@" ;;
  stop) stop_role "$@" ;;
  status) status_role "$@" ;;
  summarize)
    run_dir=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --run-dir) run_dir="${2:?missing run dir}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown argument: $1" ;;
      esac
    done
    [[ -n "${run_dir}" ]] || die "summarize needs --run-dir"
    summarize_run_dir "${run_dir}"
    ;;
  _lidar_worker) lidar_worker ;;
  _camera_worker) camera_worker ;;
  -h|--help|"") usage ;;
  *) die "unknown action: ${ACTION}" ;;
esac
