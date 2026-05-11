#!/usr/bin/env bash
# Auxiliary Orin-side visual QC capture for PixRover RGBA camera sockets.
#
# This is not a replacement for the timestamped ROS 2 reconstruction bag.
# Use it to preview camera coverage or save a low-rate JPEG sample from the
# live /tmp/*_rgba_sink_1 sockets before/after a field run.
#
# Typical 82th flow:
#   bash -ilc 'bash ops/scripts/record_orin_rgba_socket_frames.sh --list-sockets'
#   bash -ilc 'bash ops/scripts/record_orin_rgba_socket_frames.sh --preview --channel front_right'
#   bash -ilc 'bash ops/scripts/record_orin_rgba_socket_frames.sh --record --duration 20 --fps 2 --channel front_right'

set -Eeuo pipefail
shopt -s nullglob

SCRIPT_NAME="$(basename "$0")"
OUT_ROOT="${OUT_ROOT:-/home/nvidia/pix/road_tests/qiyu_rgba_socket_frames}"
RUN_LABEL="${RUN_LABEL:-qiyu_rgba_socket_qc}"
DURATION_SEC=20
FPS=2
QUALITY=92
MODE="sequential"
DO_RECORD=false
DO_PREVIEW=false
DO_LIST=false
CHANNELS=()

usage() {
  cat <<EOF
Usage:
  ${SCRIPT_NAME} [options]

Options:
  --list-sockets          List known RGBA sockets and GStreamer plugins.
  --preview              Open nveglglessink preview for one channel.
  --record               Save low-rate JPEG frames from selected sockets.
  --channel NAME         Camera channel. Repeatable. Default: front_right.
  --all-channels         Use all known channels.
  --duration SEC         Capture duration for --record. Default: ${DURATION_SEC}
  --fps N                JPEG sampling rate for --record. Default: ${FPS}
  --quality N            JPEG quality. Default: ${QUALITY}
  --out-root DIR         Output root. Default: ${OUT_ROOT}
  --label NAME           Run label prefix. Default: ${RUN_LABEL}
  --mode sequential|parallel
                         Multiple-channel capture mode. Default: ${MODE}
                         Keep sequential unless Orin NV/VIC resources were smoke-tested.
  -h, --help             Show this help.

Channels:
  front_3mm front_left front_right rear_3mm rear_left rear_right

Notes:
  Run from an interactive/login shell on the Orin, or wrap with bash -ilc,
  so the PixRover GStreamer plugin paths are loaded.
EOF
}

log() {
  printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

die() {
  log "FATAL: $*" >&2
  exit 1
}

safe_name() {
  printf '%s' "$1" | sed 's#[^A-Za-z0-9_.-]#_#g'
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

all_channels() {
  printf '%s\n' front_3mm front_left front_right rear_3mm rear_left rear_right
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list-sockets) DO_LIST=true; shift ;;
    --preview) DO_PREVIEW=true; shift ;;
    --record) DO_RECORD=true; shift ;;
    --channel) CHANNELS+=("${2:?missing channel}"); shift 2 ;;
    --all-channels) mapfile -t CHANNELS < <(all_channels); shift ;;
    --duration) DURATION_SEC="${2:?missing duration}"; shift 2 ;;
    --fps) FPS="${2:?missing fps}"; shift 2 ;;
    --quality) QUALITY="${2:?missing quality}"; shift 2 ;;
    --out-root) OUT_ROOT="${2:?missing output root}"; shift 2 ;;
    --label) RUN_LABEL="${2:?missing label}"; shift 2 ;;
    --mode) MODE="${2:?missing mode}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

if [[ "${#CHANNELS[@]}" -eq 0 ]]; then
  CHANNELS=(front_right)
fi

case "${MODE}" in
  sequential|parallel) ;;
  *) die "--mode must be sequential or parallel" ;;
esac

if (( FPS < 1 )); then
  die "--fps must be >= 1"
fi
if (( QUALITY < 1 || QUALITY > 100 )); then
  die "--quality must be between 1 and 100"
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

require_gst_element() {
  gst-inspect-1.0 "$1" >/dev/null 2>&1 || die "missing GStreamer element: $1"
}

check_runtime() {
  require_command gst-launch-1.0
  require_command gst-inspect-1.0
  require_gst_element nvunixfdsrc
  require_gst_element nvvideoconvert
  require_gst_element videoconvert
  require_gst_element videorate
  require_gst_element jpegenc
  require_gst_element multifilesink
}

validate_channels() {
  local channel socket
  for channel in "${CHANNELS[@]}"; do
    socket="$(socket_for_channel "${channel}")" || die "unknown channel: ${channel}"
    [[ -S "${socket}" ]] || die "socket not found for ${channel}: ${socket}"
  done
}

list_sockets() {
  local channel socket status
  printf 'channel\tsocket\tstatus\n'
  while IFS= read -r channel; do
    socket="$(socket_for_channel "${channel}")"
    if [[ -S "${socket}" ]]; then
      status="present"
    else
      status="missing"
    fi
    printf '%s\t%s\t%s\n' "${channel}" "${socket}" "${status}"
  done < <(all_channels)

  printf '\nplugins:\n'
  for element in nvunixfdsrc nvvideoconvert nvegltransform nveglglessink videoconvert videorate jpegenc multifilesink; do
    if gst-inspect-1.0 "${element}" >/dev/null 2>&1; then
      printf 'present\t%s\n' "${element}"
    else
      printf 'missing\t%s\n' "${element}"
    fi
  done
}

preview_channel() {
  local channel="$1"
  local socket
  socket="$(socket_for_channel "${channel}")"
  log "preview ${channel}: ${socket}"
  gst-launch-1.0 \
    nvunixfdsrc socket-path="${socket}" \
    ! 'video/x-raw(memory:NVMM),format=RGB' \
    ! nvvideoconvert compute-hw=1 \
    ! 'video/x-raw(memory:NVMM),format=RGBA' \
    ! nvegltransform \
    ! nveglglessink sync=false
}

record_channel() {
  local channel="$1"
  local run_dir="$2"
  local socket channel_dir status_file command_file
  socket="$(socket_for_channel "${channel}")"
  channel_dir="${run_dir}/${channel}"
  status_file="${channel_dir}/record_exit_status.txt"
  command_file="${channel_dir}/gst_command.txt"
  mkdir -p "${channel_dir}"

  cat > "${command_file}" <<EOF
gst-launch-1.0 -e nvunixfdsrc socket-path=${socket} ! video/x-raw\\(memory:NVMM\\),format=RGB ! nvvideoconvert compute-hw=1 ! video/x-raw,format=RGBA ! videoconvert ! videorate ! video/x-raw,framerate=${FPS}/1 ! jpegenc quality=${QUALITY} ! multifilesink location=${channel_dir}/frame_%06d.jpg sync=false
EOF

  log "record ${channel}: ${DURATION_SEC}s @ ${FPS} fps -> ${channel_dir}"
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
  if [[ "${status}" != "0" && "${status}" != "124" && "${status}" != "130" ]]; then
    log "WARN: ${channel} GStreamer capture exited with ${status}; see ${channel_dir}/gst_record.log"
  fi
}

check_runtime

if [[ "${DO_LIST}" == "true" || ( "${DO_RECORD}" != "true" && "${DO_PREVIEW}" != "true" ) ]]; then
  list_sockets
  if [[ "${DO_RECORD}" != "true" && "${DO_PREVIEW}" != "true" ]]; then
    exit 0
  fi
fi

validate_channels

if [[ "${DO_PREVIEW}" == "true" ]]; then
  if [[ "${#CHANNELS[@]}" -gt 1 ]]; then
    die "--preview accepts one channel at a time"
  fi
  preview_channel "${CHANNELS[0]}"
  exit 0
fi

if [[ "${DO_RECORD}" != "true" ]]; then
  exit 0
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
HOST="$(hostname | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_.-' '-')"
RUN_ID="${RUN_LABEL}_${STAMP}_${HOST}"
RUN_DIR="${OUT_ROOT}/${RUN_ID}"
mkdir -p "${RUN_DIR}"

{
  printf 'run_id=%s\n' "${RUN_ID}"
  printf 'host=%s\n' "$(hostname)"
  printf 'started_at=%s\n' "$(date -Is 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'duration_sec=%s\n' "${DURATION_SEC}"
  printf 'fps=%s\n' "${FPS}"
  printf 'quality=%s\n' "${QUALITY}"
  printf 'mode=%s\n' "${MODE}"
  printf 'channels=%s\n' "${CHANNELS[*]}"
  printf 'note=%s\n' "visual QC only; use ROS bag for timestamped reconstruction source"
} > "${RUN_DIR}/capture_manifest.env"
list_sockets > "${RUN_DIR}/socket_and_plugin_status.tsv"
df -h "${OUT_ROOT}" > "${RUN_DIR}/disk_before.txt"

if [[ "${MODE}" == "parallel" && "${#CHANNELS[@]}" -gt 1 ]]; then
  log "WARN: parallel socket capture may hit Orin NV/VIC resource limits; sequential is the safer default"
  pids=()
  for channel in "${CHANNELS[@]}"; do
    record_channel "${channel}" "${RUN_DIR}" &
    pids+=("$!")
  done
  status=0
  for pid in "${pids[@]}"; do
    wait "${pid}" || status=1
  done
  if [[ "${status}" != "0" ]]; then
    log "WARN: one or more parallel captures failed"
  fi
else
  for channel in "${CHANNELS[@]}"; do
    record_channel "${channel}" "${RUN_DIR}"
  done
fi

df -h "${OUT_ROOT}" > "${RUN_DIR}/disk_after.txt"
date -Is > "${RUN_DIR}/finished_at.txt" 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ' > "${RUN_DIR}/finished_at.txt"
log "capture complete: ${RUN_DIR}"
