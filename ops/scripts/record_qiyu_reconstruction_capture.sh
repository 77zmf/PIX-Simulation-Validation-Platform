#!/usr/bin/env bash
# Qiyu reconstruction field capture helper.
#
# Runs on the vehicle IPC/Orin. The default rgb-map profile matches the RGB
# pointcloud mapping input bag expected by pixmoving-auto/liorf
# robobus_color_ros2 and pixmoving-auto/color_pointscloud orin.
#
# Typical field flow:
#   bash ops/scripts/record_qiyu_reconstruction_capture.sh --out-root /data/pix/road_tests/qiyu_recon --preflight-seconds 8
#   bash ops/scripts/record_qiyu_reconstruction_capture.sh --record --duration 2400 --out-root /data/pix/road_tests/qiyu_recon
#
# Equivalent core rosbag command:
#   ros2 bag record -o ros2bag --max-bag-size $((3*1024*1024*1024)) \
#     /sensing/lidar/front_top/points /sensing/lidar/rear_top/points \
#     /sensing/imu/imu_data /sensing/gnss/fix
#
# color_pointscloud/orin uses the front_3mm and rear_3mm compressed camera
# streams for RGB pointcloud generation. Use rgb-map-camera on the Orin camera
# publisher host when those image frames must be captured with the mapping bag.

set -Eeuo pipefail
shopt -s nullglob

SCRIPT_NAME="$(basename "$0")"

OUT_ROOT="${OUT_ROOT:-/data/pix/road_tests/qiyu_reconstruction_capture}"
RUN_LABEL="${RUN_LABEL:-qiyu_loop_recon}"
MODE="static"
CAPTURE_PROFILE="${CAPTURE_PROFILE:-rgb-map}"
DURATION_SEC=0
PREFLIGHT_SECONDS=8
MIN_FREE_GB="${MIN_FREE_GB:-200}"
BAG_STORAGE="${BAG_STORAGE:-sqlite3}"
MAX_BAG_SIZE="${MAX_BAG_SIZE:-3221225472}"
BAG_NAME="${BAG_NAME:-ros2bag}"
DO_RECORD=false
FORCE=false
SKIP_PREFLIGHT=false
SOURCE_ROS=true
COMPRESS_ZSTD=false
AUTO_DISCOVER="${AUTO_DISCOVER:-}"
INCLUDE_RAW_IMAGES=false
INCLUDE_INDIVIDUAL_LIDAR=false
CAPTURE_TF_EXTRINSICS=true
TOPIC_FILE=""
MIN_CAMERA_COUNT="${MIN_CAMERA_COUNT:-auto}"
MIN_CAMERA_HZ="${MIN_CAMERA_HZ:-9}"
MIN_LIDAR_HZ="${MIN_LIDAR_HZ:-8}"
MIN_OBJECT_HZ="${MIN_OBJECT_HZ:-1}"
TF_BASE_FRAME="${TF_BASE_FRAME:-base_link}"
TF_FRONT_LIDAR_FRAME="${TF_FRONT_LIDAR_FRAME:-front_top}"
TF_REAR_LIDAR_FRAME="${TF_REAR_LIDAR_FRAME:-rear_top}"
TF_WAIT_SECONDS="${TF_WAIT_SECONDS:-3}"

EXTRA_TOPICS=()
EXTRA_TOPICS_SET=false

usage() {
  cat <<EOF
Usage:
  ${SCRIPT_NAME} [options]

Options:
  --record                 Record after preflight. Without this, only preflight is run.
  --mode static|dynamic    Capture intent label. Default: static.
  --capture-profile NAME   rgb-map|rgb-map-camera|rgb-camera-only|rgb-map-camera-full|reconstruction-rich. Default: ${CAPTURE_PROFILE}
  --duration SEC           Record duration. Default 0 means run until Ctrl-C.
  --out-root DIR           Output root. Default: ${OUT_ROOT}
  --label NAME             Run label prefix. Default: ${RUN_LABEL}
  --preflight-seconds SEC  Seconds per topic for hz checks. Default: ${PREFLIGHT_SECONDS}
  --min-free-gb GB         Required free disk before recording. Default: ${MIN_FREE_GB}
  --storage mcap|sqlite3   rosbag2 storage id. Default: ${BAG_STORAGE}
  --max-bag-size BYTES     rosbag2 split size. Default: ${MAX_BAG_SIZE}
  --bag-name NAME          Bag directory name inside the run dir. Default: ${BAG_NAME}
  --extra-topic TOPIC      Add a topic if present. Can be repeated.
  --topic-file FILE        Add non-comment topics from a file if present.
  --include-raw-images     Also auto-capture /sensing/camera/*/image_raw topics.
  --include-individual-lidar
                           Also capture individual /sensing/lidar/*/points topics.
  --base-frame FRAME       Base frame for LiDAR extrinsic snapshot. Default: ${TF_BASE_FRAME}
  --front-lidar-frame FRAME
                           Front LiDAR frame for tf2_echo. Default: ${TF_FRONT_LIDAR_FRAME}
  --rear-lidar-frame FRAME Rear LiDAR frame for tf2_echo. Default: ${TF_REAR_LIDAR_FRAME}
  --tf-wait-seconds SEC    Seconds to sample each tf2_echo command. Default: ${TF_WAIT_SECONDS}
  --skip-tf-extrinsics     Do not capture front/rear LiDAR tf snapshots.
  --min-camera-count N     Required camera image topic count. Default: auto
  --camera-min-hz HZ       Minimum camera image rate. Default: ${MIN_CAMERA_HZ}
  --lidar-min-hz HZ        Minimum pointcloud rate. Default: ${MIN_LIDAR_HZ}
  --object-min-hz HZ       Minimum dynamic object rate. Default: ${MIN_OBJECT_HZ}
  --auto-discover          Add matching topics discovered from ros2 topic list -t.
  --no-auto-discover       Only use built-in candidates, --extra-topic, and --topic-file.
  --compress-zstd          Compress *.mcap after recording.
  --skip-preflight         Skip topic hz checks.
  --force                  Record even when profile-critical preflight is weak/missing.
  --no-source-ros          Do not source ROS setup files.
  -h, --help               Show this help.

Examples:
  # RGB pointcloud map bag for liorf robobus_color_ros2:
  ${SCRIPT_NAME} --record --duration 2400 --out-root /data/pix/road_tests/qiyu_recon

  # RGB pointcloud map bag plus color_pointscloud/orin front/rear 3mm cameras:
  ${SCRIPT_NAME} --record --capture-profile rgb-map-camera --duration 2400 --out-root /data/pix/road_tests/qiyu_recon

  # Orin-side camera-only bag when LiDAR/IMU/GNSS are recorded on the IPC:
  ${SCRIPT_NAME} --record --capture-profile rgb-camera-only --duration 2400 --out-root /home/nvidia/pix/failcase_data_local/qiyu_recon_camera

  # RGB pointcloud map bag plus all six mirror camera streams:
  ${SCRIPT_NAME} --record --capture-profile rgb-map-camera-full --duration 2400 --out-root /data/pix/road_tests/qiyu_recon

  # 1-minute sample before driving the full loop:
  ${SCRIPT_NAME} --record --duration 60 --out-root /data/pix/road_tests/qiyu_recon

  # Rich reconstruction capture with cameras/object topics:
  ${SCRIPT_NAME} --record --capture-profile reconstruction-rich --mode static --out-root /data/pix/road_tests/qiyu_recon

  # Dynamic-obstacle reference pass:
  ${SCRIPT_NAME} --record --capture-profile reconstruction-rich --mode dynamic --duration 2400 --out-root /data/pix/road_tests/qiyu_recon
EOF
}

log() {
  printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

iso_now() {
  date -Is 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ'
}

die() {
  log "FATAL: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --record) DO_RECORD=true; shift ;;
    --mode) MODE="${2:?missing mode}"; shift 2 ;;
    --capture-profile) CAPTURE_PROFILE="${2:?missing capture profile}"; shift 2 ;;
    --duration) DURATION_SEC="${2:?missing duration}"; shift 2 ;;
    --out-root) OUT_ROOT="${2:?missing output root}"; shift 2 ;;
    --label) RUN_LABEL="${2:?missing label}"; shift 2 ;;
    --preflight-seconds) PREFLIGHT_SECONDS="${2:?missing seconds}"; shift 2 ;;
    --min-free-gb) MIN_FREE_GB="${2:?missing GB}"; shift 2 ;;
    --storage) BAG_STORAGE="${2:?missing storage}"; shift 2 ;;
    --max-bag-size) MAX_BAG_SIZE="${2:?missing bytes}"; shift 2 ;;
    --bag-name) BAG_NAME="${2:?missing bag name}"; shift 2 ;;
    --extra-topic) EXTRA_TOPICS+=("${2:?missing topic}"); EXTRA_TOPICS_SET=true; shift 2 ;;
    --topic-file) TOPIC_FILE="${2:?missing topic file}"; shift 2 ;;
    --include-raw-images) INCLUDE_RAW_IMAGES=true; shift ;;
    --include-individual-lidar) INCLUDE_INDIVIDUAL_LIDAR=true; shift ;;
    --base-frame) TF_BASE_FRAME="${2:?missing base frame}"; shift 2 ;;
    --front-lidar-frame) TF_FRONT_LIDAR_FRAME="${2:?missing front lidar frame}"; shift 2 ;;
    --rear-lidar-frame) TF_REAR_LIDAR_FRAME="${2:?missing rear lidar frame}"; shift 2 ;;
    --tf-wait-seconds) TF_WAIT_SECONDS="${2:?missing tf wait seconds}"; shift 2 ;;
    --skip-tf-extrinsics) CAPTURE_TF_EXTRINSICS=false; shift ;;
    --min-camera-count) MIN_CAMERA_COUNT="${2:?missing camera count}"; shift 2 ;;
    --camera-min-hz) MIN_CAMERA_HZ="${2:?missing camera hz}"; shift 2 ;;
    --lidar-min-hz) MIN_LIDAR_HZ="${2:?missing lidar hz}"; shift 2 ;;
    --object-min-hz) MIN_OBJECT_HZ="${2:?missing object hz}"; shift 2 ;;
    --auto-discover) AUTO_DISCOVER=true; shift ;;
    --no-auto-discover) AUTO_DISCOVER=false; shift ;;
    --compress-zstd) COMPRESS_ZSTD=true; shift ;;
    --skip-preflight) SKIP_PREFLIGHT=true; shift ;;
    --force) FORCE=true; shift ;;
    --no-source-ros) SOURCE_ROS=false; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

case "${MODE}" in
  static|dynamic) ;;
  *) die "--mode must be static or dynamic" ;;
esac

case "${CAPTURE_PROFILE}" in
  rgb-map|rgb-map-camera|rgb-camera-only|rgb-map-camera-full|reconstruction-rich) ;;
  *) die "--capture-profile must be rgb-map, rgb-map-camera, rgb-camera-only, rgb-map-camera-full, or reconstruction-rich" ;;
esac

if [[ -z "${AUTO_DISCOVER}" ]]; then
  if [[ "${CAPTURE_PROFILE}" == rgb-map* || "${CAPTURE_PROFILE}" == "rgb-camera-only" ]]; then
    AUTO_DISCOVER=false
  else
    AUTO_DISCOVER=true
  fi
fi

if [[ "${CAPTURE_PROFILE}" == "rgb-camera-only" ]]; then
  CAPTURE_TF_EXTRINSICS=false
fi

source_ros_setup() {
  if [[ "${SOURCE_ROS}" != "true" ]]; then
    return
  fi

  source_setup_file() {
    local setup="$1"
    local had_nounset=false
    case "$-" in
      *u*) had_nounset=true; set +u ;;
    esac
    # shellcheck disable=SC1090
    source "${setup}"
    if [[ "${had_nounset}" == "true" ]]; then
      set -u
    fi
    log "sourced: ${setup}"
  }

  local sourced_any=false
  if [[ -f "/opt/ros/humble/setup.bash" ]]; then
    source_setup_file "/opt/ros/humble/setup.bash"
    sourced_any=true
  fi

  local overlays=(
    "/home/ipc/pix/robobus/autoware-robobus.dev-master/install/setup.bash"
    "/home/nvidia/pix/robobus/autoware-robobus.dev-master/install/setup.bash"
    "/home/ipc/pix/robobus/autoware/install/setup.bash"
    "/home/pixmoving/pix/robobus/autoware/install/setup.bash"
    "${HOME}/pix/robobus/autoware-robobus.dev-master/install/setup.bash"
    "${HOME}/pix/robobus/autoware-robobus.dev-master-1/install/setup.bash"
    "${HOME}/pix/robobus/autoware-robobus.dev-master-20260326/install/setup.bash"
    "${HOME}/pix/robobus/autoware/install/setup.bash"
    "${HOME}/autoware/install/setup.bash"
  )

  local setup
  for setup in "${overlays[@]}"; do
    if [[ -f "${setup}" ]]; then
      source_setup_file "${setup}"
      sourced_any=true
      break
    fi
  done

  if [[ "${sourced_any}" != "true" ]]; then
    log "WARN: no ROS setup file found in the known paths"
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

running_ros_env_values() {
  local key="$1"
  command -v pgrep >/dev/null 2>&1 || return

  local had_pipefail=false
  case "$(set -o | awk '$1 == "pipefail" {print $2}')" in
    on) had_pipefail=true; set +o pipefail ;;
  esac
  (pgrep -u "$(id -u)" -f 'component_container|ros2 launch|autoware|perception|planning|sensing|localization|zenoh-bridge' || true) |
    while IFS= read -r pid; do
      [[ -r "/proc/${pid}/environ" ]] || continue
      tr '\0' '\n' < "/proc/${pid}/environ" 2>/dev/null |
        awk -F= -v key="${key}" '$1 == key && $2 != "" {print substr($0, length(key) + 2); exit}'
    done |
    sort -u
  if [[ "${had_pipefail}" == "true" ]]; then
    set -o pipefail
  fi
}

detect_ros_runtime_env() {
  local key values value_count value current_value
  for key in ROS_DOMAIN_ID RMW_IMPLEMENTATION CYCLONEDDS_URI ROS_LOCALHOST_ONLY; do
    current_value="${!key:-}"
    if [[ -n "${current_value}" ]]; then
      log "${key}: ${current_value}"
      continue
    fi

    values="$(running_ros_env_values "${key}")"
    value_count="$(printf '%s\n' "${values}" | sed '/^$/d' | wc -l | tr -d ' ')"
    case "${value_count}" in
      0)
        if [[ "${key}" == "ROS_DOMAIN_ID" ]]; then
          log "WARN: ${key} is not set and no running ROS process value was detected"
        fi
        ;;
      1)
        value="$(printf '%s\n' "${values}" | sed -n '1p')"
        export "${key}=${value}"
        log "detected ${key} from running ROS processes: ${value}"
        ;;
      *)
        log "WARN: multiple ${key} candidates detected; set it explicitly: $(printf '%s' "${values}" | tr '\n' ',')"
        ;;
    esac
  done
}

safe_name() {
  printf '%s' "$1" | sed 's#[^A-Za-z0-9_.-]#_#g'
}

is_camera_topic() {
  local topic="$1"
  [[ "${topic}" == *camera_image* || "${topic}" == *image_raw* || "${topic}" == *compressed* || "${topic}" == *image_jpeg* ]]
}

is_lidar_topic() {
  local topic="$1"
  [[ "${topic}" == *pointcloud* || "${topic}" == *"/points"* || "${topic}" == *points_rgb* ]]
}

is_rgb_map_core_topic() {
  local topic="$1"
  [[ "${topic}" == "/sensing/lidar/front_top/points" ||
     "${topic}" == "/sensing/lidar/rear_top/points" ||
     "${topic}" == "/sensing/imu/imu_data" ||
     "${topic}" == "/sensing/gnss/fix" ]]
}

is_capture_lidar_topic() {
  local topic="$1"
  if [[ "${CAPTURE_PROFILE}" == rgb-map* ]]; then
    [[ "${topic}" == "/sensing/lidar/front_top/points" ||
       "${topic}" == "/sensing/lidar/rear_top/points" ]] && return 0
    return 1
  fi

  [[ "${topic}" == "/sensing/lidar/concatenated/pointcloud" ||
     "${topic}" == "/sensing/lidar/points_rgb" ||
     "${topic}" == "/colored_pointcloud" ]] && return 0

  if [[ "${INCLUDE_INDIVIDUAL_LIDAR}" == "true" ]]; then
    [[ "${topic}" == /sensing/lidar/*/points ||
       "${topic}" == /sensing/lidar/*/pointcloud_before_sync ]] && return 0
  fi

  return 1
}

is_preflight_lidar_topic() {
  local topic="$1"
  if [[ "${CAPTURE_PROFILE}" == rgb-map* ]]; then
    [[ "${topic}" == "/sensing/lidar/front_top/points" ||
       "${topic}" == "/sensing/lidar/rear_top/points" ]]
    return
  fi

  [[ "${topic}" == "/sensing/lidar/concatenated/pointcloud" ||
     "${topic}" == "/sensing/lidar/points_rgb" ||
     "${topic}" == "/colored_pointcloud" ]]
}

is_capture_camera_topic() {
  local topic="$1"
  [[ "${topic}" == /electronic_rearview_mirror/*/camera_image_jpeg ]] && return 0

  if [[ "${INCLUDE_RAW_IMAGES}" == "true" ]]; then
    [[ "${topic}" == /sensing/camera/*/image_raw ||
       "${topic}" == /sensing/camera/*/image_raw/compressed ]] && return 0
  fi

  return 1
}

is_object_topic() {
  local topic="$1"
  [[ "${topic}" == *objects* || "${topic}" == *occupancy_grid_map* || "${topic}" == *perception_data* ]]
}

is_capture_object_topic() {
  local topic="$1"
  [[ "${topic}" == "/perception/object_recognition/objects" ||
     "${topic}" == "/perception/object_recognition/tracking/objects" ||
     "${topic}" == "/perception/object_recognition/detection/bevfusion/objects" ||
     "${topic}" == "/perception/object_recognition/detection/objects" ||
     "${topic}" == "/api/perception/objects" ||
     "${topic}" == "/hmi_input/perception/object_recognition/objects" ||
     "${topic}" == "/app/cloud_control_platform/perception_data" ]]
}

is_preflight_object_topic() {
  local topic="$1"
  [[ "${topic}" == "/perception/object_recognition/objects" ||
     "${topic}" == "/perception/object_recognition/tracking/objects" ||
     "${topic}" == "/perception/object_recognition/detection/bevfusion/objects" ]]
}

topic_min_hz() {
  local topic="$1"
  if is_camera_topic "${topic}"; then
    printf '%s' "${MIN_CAMERA_HZ}"
  elif is_lidar_topic "${topic}"; then
    printf '%s' "${MIN_LIDAR_HZ}"
  elif is_object_topic "${topic}"; then
    printf '%s' "${MIN_OBJECT_HZ}"
  else
    printf '1'
  fi
}

add_present_topic() {
  local topic="$1"
  local group="$2"
  if ! topic_already_recorded "${topic}"; then
    RECORD_TOPICS+=("${topic}")
    RECORD_TOPICS_SET=true
  fi
  printf 'present\t%s\t%s\n' "${group}" "${topic}" >> "${RUN_DIR}/topic_presence.tsv"
}

topic_already_recorded() {
  local topic="$1"
  local existing
  [[ "${RECORD_TOPICS_SET:-false}" == "true" ]] || return 1
  for existing in "${RECORD_TOPICS[@]}"; do
    [[ "${existing}" == "${topic}" ]] && return 0
  done
  return 1
}

add_topic_if_present() {
  local topic="$1"
  local group="$2"
  if grep -Fxq "${topic}" "${TOPIC_LIST_FILE}"; then
    add_present_topic "${topic}" "${group}"
  else
    printf 'missing\t%s\t%s\n' "${group}" "${topic}" >> "${RUN_DIR}/topic_presence.tsv"
  fi
}

add_topics_from_file() {
  local file="$1"
  [[ -f "${file}" ]] || die "topic file not found: ${file}"

  local topic
  while IFS= read -r topic || [[ -n "${topic}" ]]; do
    topic="${topic%%#*}"
    topic="$(printf '%s' "${topic}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    [[ -n "${topic}" ]] || continue
    add_topic_if_present "${topic}" "topic_file"
  done < "${file}"
}

auto_group_for_topic_type() {
  local topic="$1"
  local type="$2"

  case "${type}" in
    sensor_msgs/msg/Image|sensor_msgs/msg/CompressedImage)
      if is_capture_camera_topic "${topic}"; then
        printf 'auto_camera_image'
      fi
      return
      ;;
    sensor_msgs/msg/CameraInfo)
      if [[ "${topic}" == /sensing/camera/*/camera_info ]]; then
        printf 'auto_camera_info'
      fi
      return
      ;;
    sensor_msgs/msg/PointCloud2)
      if is_capture_lidar_topic "${topic}"; then
        printf 'auto_lidar'
      fi
      return
      ;;
    tf2_msgs/msg/TFMessage)
      printf 'auto_pose_tf'
      return
      ;;
    autoware_perception_msgs/msg/PredictedObjects|autoware_perception_msgs/msg/TrackedObjects|autoware_perception_msgs/msg/DetectedObjects|cloud_control_platform_msgs/msg/Perception)
      if is_capture_object_topic "${topic}"; then
        printf 'auto_dynamic_object'
      fi
      return
      ;;
    sensor_msgs/msg/NavSatFix|sensor_msgs/msg/Imu|autoware_sensing_msgs/msg/GnssInsOrientationStamped|std_msgs/msg/Float32)
      if [[ "${topic}" == /sensing/gnss/* || "${topic}" == /sensing/imu/* || "${topic}" == /autoware_orientation ]]; then
        printf 'auto_pose_tf'
      fi
      return
      ;;
    geometry_msgs/msg/TwistStamped|geometry_msgs/msg/TwistWithCovarianceStamped)
      if [[ "${topic}" == /localization/* || "${topic}" == /sensing/vehicle_velocity_converter/* ]]; then
        printf 'auto_vehicle_dynamics'
      fi
      return
      ;;
  esac

  return 0
}

auto_discover_topics() {
  local typed_file="${RUN_DIR}/topic_list_typed.txt"
  [[ -s "${typed_file}" ]] || return 0

  local line topic type group
  while IFS= read -r line || [[ -n "${line}" ]]; do
    topic="${line%% *}"
    type="$(printf '%s' "${line}" | sed -n 's/.*\[\([^]]*\)\].*/\1/p')"
    [[ -n "${topic}" && -n "${type}" ]] || continue
    grep -Fxq "${topic}" "${TOPIC_LIST_FILE}" || continue

    group="$(auto_group_for_topic_type "${topic}" "${type}")"
    [[ -n "${group}" ]] || continue
    add_present_topic "${topic}" "${group}"
  done < "${typed_file}"
}

preflight_topic() {
  local topic="$1"
  local out_file="$2"
  local raw_file="$3"
  local min_hz
  min_hz="$(topic_min_hz "${topic}")"

  timeout --signal=INT "${PREFLIGHT_SECONDS}" ros2 topic hz "${topic}" >"${raw_file}" 2>&1 || true
  local rate
  rate="$(awk '/average rate:/ {rate=$3} END {print rate}' "${raw_file}")"
  if [[ -z "${rate}" ]]; then
    if is_camera_topic "${topic}"; then
      local sample_timeout="${PREFLIGHT_SECONDS}"
      if (( sample_timeout < 15 )); then
        sample_timeout=15
      fi
      if timeout --signal=TERM "${sample_timeout}" ros2 topic echo "${topic}" --once >"${raw_file}.once.txt" 2>&1; then
        printf '%s\t%s\t%s\t%s\t%s\n' "${topic}" "sampled_once" "" "${min_hz}" "OK" > "${out_file}"
        return
      fi
    fi
    printf '%s\t%s\t%s\t%s\t%s\n' "${topic}" "no_samples" "" "${min_hz}" "FAIL" > "${out_file}"
    return
  fi

  local verdict
  verdict="$(awk -v rate="${rate}" -v min="${min_hz}" 'BEGIN { if (rate + 0 >= min + 0) print "OK"; else print "FAIL" }')"
  printf '%s\t%s\t%s\t%s\t%s\n' "${topic}" "sampled" "${rate}" "${min_hz}" "${verdict}" > "${out_file}"
}

check_free_space() {
  mkdir -p "${OUT_ROOT}"
  local free_kb
  free_kb="$(df -Pk "${OUT_ROOT}" | awk 'NR==2 {print $4}')"
  local min_kb=$((MIN_FREE_GB * 1024 * 1024))
  if (( free_kb < min_kb )); then
    die "free space under ${OUT_ROOT} is below ${MIN_FREE_GB}GB"
  fi
}

write_tf_command_file() {
  local out_dir="$1"
  cat > "${out_dir}/tf2_echo_commands.txt" <<EOF
ros2 run tf2_ros tf2_echo ${TF_BASE_FRAME} ${TF_FRONT_LIDAR_FRAME}
ros2 run tf2_ros tf2_echo ${TF_BASE_FRAME} ${TF_REAR_LIDAR_FRAME}
EOF
}

append_liorf_transform_fragment() {
  local raw_file="$1"
  local key="$2"
  local out_file="$3"

  awk -v key="${key}" '
    /Translation:/ && !seen_t {
      line = $0
      sub(/^.*\[/, "", line)
      sub(/\].*$/, "", line)
      gsub(/,/, "", line)
      split(line, t, /[[:space:]]+/)
      seen_t = 1
    }
    /Quaternion/ && !seen_q {
      line = $0
      sub(/^.*\[/, "", line)
      sub(/\].*$/, "", line)
      gsub(/,/, "", line)
      split(line, q, /[[:space:]]+/)
      seen_q = 1
    }
    END {
      if (!seen_t || !seen_q || t[1] == "" || q[1] == "") {
        exit 1
      }
      x = q[1] + 0.0
      y = q[2] + 0.0
      z = q[3] + 0.0
      w = q[4] + 0.0
      n = sqrt(x*x + y*y + z*z + w*w)
      if (n == 0) {
        exit 1
      }
      x /= n
      y /= n
      z /= n
      w /= n
      r00 = 1 - 2*y*y - 2*z*z
      r01 = 2*x*y - 2*z*w
      r02 = 2*x*z + 2*y*w
      r10 = 2*x*y + 2*z*w
      r11 = 1 - 2*x*x - 2*z*z
      r12 = 2*y*z - 2*x*w
      r20 = 2*x*z - 2*y*w
      r21 = 2*y*z + 2*x*w
      r22 = 1 - 2*x*x - 2*y*y
      printf "      %s_trans: [%.9g, %.9g, %.9g]\n", key, t[1], t[2], t[3]
      printf "      %s_rot: [%.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g]\n", key, r00, r01, r02, r10, r11, r12, r20, r21, r22
    }
  ' "${raw_file}" >> "${out_file}"
}

capture_tf_echo_once() {
  local frame="$1"
  local raw_file="$2"
  local status_file="$3"

  set +e
  timeout --signal=INT "${TF_WAIT_SECONDS}" \
    ros2 run tf2_ros tf2_echo "${TF_BASE_FRAME}" "${frame}" \
    > "${raw_file}" 2>&1
  local status="$?"
  set -e
  printf '%s\n' "${status}" > "${status_file}"
}

capture_lidar_tf_extrinsics() {
  if [[ "${CAPTURE_TF_EXTRINSICS}" != "true" ]]; then
    log "tf extrinsic capture skipped"
    return
  fi

  local tf_dir="${RUN_DIR}/tf_extrinsics"
  local fragment_file="${RUN_DIR}/liorf_lidar_extrinsics_from_tf.yaml"
  mkdir -p "${tf_dir}"
  write_tf_command_file "${tf_dir}"

  log "capturing tf extrinsics relative to ${TF_BASE_FRAME}: ${TF_FRONT_LIDAR_FRAME}, ${TF_REAR_LIDAR_FRAME}"
  capture_tf_echo_once "${TF_FRONT_LIDAR_FRAME}" "${tf_dir}/front_lidar_to_${TF_BASE_FRAME}.txt" "${tf_dir}/front_status.txt"
  capture_tf_echo_once "${TF_REAR_LIDAR_FRAME}" "${tf_dir}/rear_lidar_to_${TF_BASE_FRAME}.txt" "${tf_dir}/rear_status.txt"

  cat > "${fragment_file}" <<EOF
/**:
  ros__parameters:
    liorf:
EOF
  local parsed_any=false
  if append_liorf_transform_fragment "${tf_dir}/front_lidar_to_${TF_BASE_FRAME}.txt" "lidar_front" "${fragment_file}"; then
    parsed_any=true
  else
    log "WARN: could not parse front LiDAR tf; inspect ${tf_dir}/front_lidar_to_${TF_BASE_FRAME}.txt"
  fi
  if append_liorf_transform_fragment "${tf_dir}/rear_lidar_to_${TF_BASE_FRAME}.txt" "lidar_rear" "${fragment_file}"; then
    parsed_any=true
  else
    log "WARN: could not parse rear LiDAR tf; inspect ${tf_dir}/rear_lidar_to_${TF_BASE_FRAME}.txt"
  fi

  if [[ "${parsed_any}" == "true" ]]; then
    log "liorf extrinsic fragment: ${fragment_file}"
  else
    rm -f "${fragment_file}"
    if [[ "${FORCE}" != "true" && "${DO_RECORD}" == "true" ]]; then
      die "front/rear LiDAR tf extrinsics were not available; use --force or --skip-tf-extrinsics only after confirming the liorf config separately"
    fi
  fi
}

source_ros_setup
require_command ros2
detect_ros_runtime_env
if [[ "${SKIP_PREFLIGHT}" != "true" ||
      ( "${DO_RECORD}" == "true" && "${DURATION_SEC}" -gt 0 ) ||
      "${CAPTURE_TF_EXTRINSICS}" == "true" ]]; then
  require_command timeout
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
HOST="$(hostname | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_.-' '-')"
RUN_ID="${RUN_LABEL}_${MODE}_${STAMP}_${HOST}"
RUN_DIR="${OUT_ROOT}/${RUN_ID}"
PREFLIGHT_DIR="${RUN_DIR}/preflight"
BAG_DIR="${RUN_DIR}/${BAG_NAME}"

mkdir -p "${PREFLIGHT_DIR}"

log "run_id: ${RUN_ID}"
log "mode: ${MODE}"
log "capture_profile: ${CAPTURE_PROFILE}"
log "out: ${RUN_DIR}"

iso_now > "${RUN_DIR}/started_at.txt"
uname -a > "${RUN_DIR}/uname.txt"
df -h "${OUT_ROOT}" > "${RUN_DIR}/disk_before.txt"
env | sort > "${RUN_DIR}/env_snapshot.txt"

TOPIC_LIST_FILE="${RUN_DIR}/topic_list.txt"
ros2 topic list --no-daemon | sort > "${TOPIC_LIST_FILE}"
ros2 topic list -t --no-daemon | sort > "${RUN_DIR}/topic_list_typed.txt" || true

RECORD_TOPICS=()
RECORD_TOPICS_SET=false

RGB_MAP_CORE_TOPICS=(
  "/sensing/lidar/front_top/points"
  "/sensing/lidar/rear_top/points"
  "/sensing/imu/imu_data"
  "/sensing/gnss/fix"
)

if [[ "${CAPTURE_PROFILE}" == "rgb-map" ]]; then
  CAMERA_IMAGE_TOPICS=()
  CAMERA_INFO_TOPICS=()
  LIDAR_TOPICS=(
    "/sensing/lidar/front_top/points"
    "/sensing/lidar/rear_top/points"
  )
  POSE_TOPICS=(
    "/sensing/imu/imu_data"
    "/sensing/gnss/fix"
  )
  DYNAMIC_OBJECT_TOPICS=()
  PLANNING_CONTROL_TOPICS=()
elif [[ "${CAPTURE_PROFILE}" == "rgb-map-camera" ]]; then
  CAMERA_IMAGE_TOPICS=(
    "/electronic_rearview_mirror/front_3mm/camera_image_jpeg"
    "/electronic_rearview_mirror/rear_3mm/camera_image_jpeg"
  )
  CAMERA_INFO_TOPICS=(
    "/sensing/camera/front_3mm/camera_info"
    "/sensing/camera/rear_3mm/camera_info"
  )
  LIDAR_TOPICS=(
    "/sensing/lidar/front_top/points"
    "/sensing/lidar/rear_top/points"
  )
  POSE_TOPICS=(
    "/sensing/imu/imu_data"
    "/sensing/gnss/fix"
  )
  DYNAMIC_OBJECT_TOPICS=()
  PLANNING_CONTROL_TOPICS=()
elif [[ "${CAPTURE_PROFILE}" == "rgb-camera-only" ]]; then
  CAMERA_IMAGE_TOPICS=(
    "/electronic_rearview_mirror/front_3mm/camera_image_jpeg"
    "/electronic_rearview_mirror/rear_3mm/camera_image_jpeg"
  )
  CAMERA_INFO_TOPICS=(
    "/sensing/camera/front_3mm/camera_info"
    "/sensing/camera/rear_3mm/camera_info"
  )
  LIDAR_TOPICS=()
  POSE_TOPICS=()
  DYNAMIC_OBJECT_TOPICS=()
  PLANNING_CONTROL_TOPICS=()
elif [[ "${CAPTURE_PROFILE}" == "rgb-map-camera-full" ]]; then
  CAMERA_IMAGE_TOPICS=(
    "/electronic_rearview_mirror/front_3mm/camera_image_jpeg"
    "/electronic_rearview_mirror/front_left/camera_image_jpeg"
    "/electronic_rearview_mirror/front_right/camera_image_jpeg"
    "/electronic_rearview_mirror/rear_3mm/camera_image_jpeg"
    "/electronic_rearview_mirror/rear_left/camera_image_jpeg"
    "/electronic_rearview_mirror/rear_right/camera_image_jpeg"
  )
  CAMERA_INFO_TOPICS=(
    "/sensing/camera/front_3mm/camera_info"
    "/sensing/camera/front_left/camera_info"
    "/sensing/camera/front_right/camera_info"
    "/sensing/camera/rear_3mm/camera_info"
    "/sensing/camera/rear_left/camera_info"
    "/sensing/camera/rear_right/camera_info"
  )
  LIDAR_TOPICS=(
    "/sensing/lidar/front_top/points"
    "/sensing/lidar/rear_top/points"
  )
  POSE_TOPICS=(
    "/sensing/imu/imu_data"
    "/sensing/gnss/fix"
  )
  DYNAMIC_OBJECT_TOPICS=()
  PLANNING_CONTROL_TOPICS=()
else
  CAMERA_IMAGE_TOPICS=(
    "/electronic_rearview_mirror/front_3mm/camera_image_jpeg"
    "/electronic_rearview_mirror/front_left/camera_image_jpeg"
    "/electronic_rearview_mirror/front_right/camera_image_jpeg"
    "/electronic_rearview_mirror/rear_3mm/camera_image_jpeg"
    "/electronic_rearview_mirror/rear_left/camera_image_jpeg"
    "/electronic_rearview_mirror/rear_right/camera_image_jpeg"
    "/sensing/camera/CAM_FRONT/image_raw"
    "/sensing/camera/CAM_FRONT_LEFT/image_raw"
    "/sensing/camera/CAM_FRONT_RIGHT/image_raw"
    "/sensing/camera/CAM_BACK/image_raw"
    "/sensing/camera/CAM_BACK_LEFT/image_raw"
    "/sensing/camera/CAM_BACK_RIGHT/image_raw"
  )

  CAMERA_INFO_TOPICS=(
    "/sensing/camera/front_3mm/camera_info"
    "/sensing/camera/front_left/camera_info"
    "/sensing/camera/front_right/camera_info"
    "/sensing/camera/rear_3mm/camera_info"
    "/sensing/camera/rear_left/camera_info"
    "/sensing/camera/rear_right/camera_info"
    "/sensing/camera/CAM_FRONT/camera_info"
    "/sensing/camera/CAM_FRONT_LEFT/camera_info"
    "/sensing/camera/CAM_FRONT_RIGHT/camera_info"
    "/sensing/camera/CAM_BACK/camera_info"
    "/sensing/camera/CAM_BACK_LEFT/camera_info"
    "/sensing/camera/CAM_BACK_RIGHT/camera_info"
  )

  LIDAR_TOPICS=(
    "/sensing/lidar/concatenated/pointcloud"
    "/sensing/lidar/points_rgb"
    "/colored_pointcloud"
  )

  if [[ "${INCLUDE_INDIVIDUAL_LIDAR}" == "true" ]]; then
    LIDAR_TOPICS+=(
      "/sensing/lidar/front_top/points"
      "/sensing/lidar/rear_top/points"
      "/sensing/lidar/front_left/points"
      "/sensing/lidar/front_right/points"
      "/sensing/lidar/rear/points"
      "/sensing/lidar/top/pointcloud_before_sync"
      "/sensing/lidar/rear_top/pointcloud_before_sync"
      "/sensing/lidar/left/pointcloud_before_sync"
      "/sensing/lidar/right/pointcloud_before_sync"
      "/sensing/lidar/rear/pointcloud_before_sync"
    )
  fi

  POSE_TOPICS=(
    "/tf"
    "/tf_static"
    "/tf_static_relay"
    "/localization/kinematic_state"
    "/localization/pose_estimator/pose"
    "/localization/twist_estimator/twist_with_covariance"
    "/localization/twist_estimator/gyro_twist"
    "/sensing/vehicle_velocity_converter/twist_with_covariance"
    "/sensing/gnss/fix"
    "/sensing/gnss/heading"
    "/sensing/gnss/imu"
    "/sensing/imu/imu_data"
    "/autoware_orientation"
  )

  DYNAMIC_OBJECT_TOPICS=(
    "/perception/object_recognition/objects"
    "/perception/object_recognition/tracking/objects"
    "/perception/object_recognition/detection/bevfusion/objects"
    "/perception/object_recognition/detection/objects"
    "/hmi_input/perception/object_recognition/objects"
    "/app/cloud_control_platform/perception_data"
    "/perception/obstacle_segmentation/pointcloud"
    "/perception/occupancy_grid_map/map"
  )

  PLANNING_CONTROL_TOPICS=(
    "/planning/mission_planning/route"
    "/planning/scenario_planning/trajectory"
    "/control/command/control_cmd"
    "/control/command/actuation_cmd"
    "/vehicle/status/control_mode"
    "/vehicle/status/velocity_status"
    "/vehicle/status/steering_status"
    "/vehicle/status/gear_status"
    "/vehicle/status/actuation_status"
    "/pix_robobus/va_chassis_wheel_rpm_fb"
  )
fi

if [[ "${MIN_CAMERA_COUNT}" == "auto" ]]; then
  case "${CAPTURE_PROFILE}" in
    rgb-map) MIN_CAMERA_COUNT=0 ;;
    rgb-map-camera|rgb-camera-only) MIN_CAMERA_COUNT=2 ;;
    rgb-map-camera-full|reconstruction-rich) MIN_CAMERA_COUNT=6 ;;
  esac
fi

: > "${RUN_DIR}/topic_presence.tsv"
for topic in "${CAMERA_IMAGE_TOPICS[@]}"; do add_topic_if_present "${topic}" "camera_image"; done
for topic in "${CAMERA_INFO_TOPICS[@]}"; do add_topic_if_present "${topic}" "camera_info"; done
for topic in "${LIDAR_TOPICS[@]}"; do add_topic_if_present "${topic}" "lidar"; done
for topic in "${POSE_TOPICS[@]}"; do add_topic_if_present "${topic}" "pose_tf"; done
for topic in "${DYNAMIC_OBJECT_TOPICS[@]}"; do add_topic_if_present "${topic}" "dynamic_object"; done
for topic in "${PLANNING_CONTROL_TOPICS[@]}"; do add_topic_if_present "${topic}" "planning_control"; done
if [[ "${EXTRA_TOPICS_SET}" == "true" ]]; then
  for topic in "${EXTRA_TOPICS[@]}"; do add_topic_if_present "${topic}" "extra"; done
fi
if [[ -n "${TOPIC_FILE}" ]]; then add_topics_from_file "${TOPIC_FILE}"; fi
if [[ "${AUTO_DISCOVER}" == "true" ]]; then auto_discover_topics; fi

if [[ "${RECORD_TOPICS_SET}" == "true" ]]; then
  printf '%s\n' "${RECORD_TOPICS[@]}" > "${RUN_DIR}/topics_to_record.txt"
else
  : > "${RUN_DIR}/topics_to_record.txt"
fi

if [[ "${RECORD_TOPICS_SET}" != "true" ]]; then
  die "no configured topics are present; inspect ${TOPIC_LIST_FILE}"
fi

if [[ "${CAPTURE_PROFILE}" == rgb-map* ]]; then
  MISSING_CORE_TOPICS=()
  for topic in "${RGB_MAP_CORE_TOPICS[@]}"; do
    if ! topic_already_recorded "${topic}"; then
      MISSING_CORE_TOPICS+=("${topic}")
    fi
  done
  if [[ "${#MISSING_CORE_TOPICS[@]}" -gt 0 ]]; then
    printf '%s\n' "${MISSING_CORE_TOPICS[@]}" > "${RUN_DIR}/missing_rgb_map_core_topics.txt"
    log "WARN: missing rgb-map core topics: ${MISSING_CORE_TOPICS[*]}"
    if [[ "${FORCE}" != "true" && "${DO_RECORD}" == "true" ]]; then
      die "rgb-map capture requires front_top/rear_top LiDAR, IMU, and GNSS; use --force only after confirming the replacement topics"
    fi
  fi
fi

if [[ "${CAPTURE_PROFILE}" != "rgb-map" ]]; then
  CAMERA_RECORD_COUNT=0
  for topic in "${RECORD_TOPICS[@]}"; do
    if is_camera_topic "${topic}"; then
      CAMERA_RECORD_COUNT=$((CAMERA_RECORD_COUNT + 1))
    fi
  done
  if (( CAMERA_RECORD_COUNT < MIN_CAMERA_COUNT )); then
    log "WARN: only ${CAMERA_RECORD_COUNT} camera image topics are present; dense 3DGS capture expects ${MIN_CAMERA_COUNT}"
    if [[ "${FORCE}" != "true" && "${DO_RECORD}" == "true" ]]; then
      die "not enough camera image topics; use --force only after confirming alternate camera topics are covered"
    fi
  fi
fi

PREFLIGHT_TOPICS=()
for topic in "${RECORD_TOPICS[@]}"; do
  if is_capture_camera_topic "${topic}" || is_preflight_lidar_topic "${topic}" || is_preflight_object_topic "${topic}"; then
    PREFLIGHT_TOPICS+=("${topic}")
  fi
done

if [[ "${SKIP_PREFLIGHT}" != "true" ]]; then
  log "preflight: sampling ${#PREFLIGHT_TOPICS[@]} topic rates for ${PREFLIGHT_SECONDS}s each"
  if [[ "${#PREFLIGHT_TOPICS[@]}" -gt 0 ]]; then
    for topic in "${PREFLIGHT_TOPICS[@]}"; do
      safe="$(safe_name "${topic}")"
      preflight_topic "${topic}" "${PREFLIGHT_DIR}/${safe}.tsv" "${PREFLIGHT_DIR}/${safe}.hz.txt"
    done
  fi

  TSV_FILES=("${PREFLIGHT_DIR}"/*.tsv)
  {
    printf 'topic\tstatus\tavg_hz\tmin_hz\tverdict\n'
    if [[ "${#TSV_FILES[@]}" -gt 0 ]]; then
      cat "${TSV_FILES[@]}" | sort
    fi
  } > "${RUN_DIR}/preflight_summary.tsv"

  CAMERA_FAILS="$(
    awk -F '\t' 'NR > 1 && $5 != "OK" && ($1 ~ /camera_image/ || $1 ~ /image_raw/ || $1 ~ /compressed/) {print $0}' \
      "${RUN_DIR}/preflight_summary.tsv"
  )"
  RGB_MAP_FAILS="$(
    awk -F '\t' 'NR > 1 && $5 != "OK" && ($1 == "/sensing/lidar/front_top/points" || $1 == "/sensing/lidar/rear_top/points") {print $0}' \
      "${RUN_DIR}/preflight_summary.tsv"
  )"

  log "preflight summary: ${RUN_DIR}/preflight_summary.tsv"
  if [[ "${CAPTURE_PROFILE}" == rgb-map* && -n "${RGB_MAP_FAILS}" ]]; then
    log "WARN: one or more rgb-map LiDAR topics are below minimum rate:"
    printf '%s\n' "${RGB_MAP_FAILS}" >&2
    if [[ "${FORCE}" != "true" && "${DO_RECORD}" == "true" ]]; then
      die "rgb-map LiDAR preflight failed; use --force only if you intentionally want a weak mapping bag"
    fi
  fi
  if [[ -n "${CAMERA_FAILS}" ]]; then
    log "WARN: one or more camera image topics are below minimum rate:"
    printf '%s\n' "${CAMERA_FAILS}" >&2
    if [[ "${FORCE}" != "true" && "${DO_RECORD}" == "true" ]]; then
      die "camera preflight failed; use --force only if you intentionally want a weak reconstruction bag"
    fi
  fi
else
  log "preflight skipped"
fi

capture_lidar_tf_extrinsics

if [[ "${DO_RECORD}" != "true" ]]; then
  log "preflight-only mode complete"
  log "to record: ${SCRIPT_NAME} --record --out-root ${OUT_ROOT}"
  exit 0
fi

check_free_space

cat > "${RUN_DIR}/capture_manifest.json" <<EOF
{
  "run_id": "${RUN_ID}",
  "mode": "${MODE}",
  "capture_profile": "${CAPTURE_PROFILE}",
  "started_at": "$(iso_now)",
  "bag_storage": "${BAG_STORAGE}",
  "bag_dir": "${BAG_DIR}",
  "max_bag_size_bytes": ${MAX_BAG_SIZE},
  "duration_sec": ${DURATION_SEC},
  "output_dir": "${RUN_DIR}",
  "auto_discover": ${AUTO_DISCOVER},
  "topic_file": "${TOPIC_FILE}",
  "include_raw_images": ${INCLUDE_RAW_IMAGES},
  "include_individual_lidar": ${INCLUDE_INDIVIDUAL_LIDAR},
  "tf_extrinsics": {
    "enabled": ${CAPTURE_TF_EXTRINSICS},
    "base_frame": "${TF_BASE_FRAME}",
    "front_lidar_frame": "${TF_FRONT_LIDAR_FRAME}",
    "rear_lidar_frame": "${TF_REAR_LIDAR_FRAME}",
    "fragment_file": "${RUN_DIR}/liorf_lidar_extrinsics_from_tf.yaml"
  },
  "min_camera_count": ${MIN_CAMERA_COUNT},
  "camera_min_hz": ${MIN_CAMERA_HZ},
  "lidar_min_hz": ${MIN_LIDAR_HZ},
  "object_min_hz": ${MIN_OBJECT_HZ},
  "reconstruction_target": "rgb_pointcloud_lio_mapping_and_reconstruction_handoff",
  "reference_command": "ros2 bag record -o ros2bag --max-bag-size $((3*1024*1024*1024)) /sensing/lidar/front_top/points /sensing/lidar/rear_top/points /sensing/imu/imu_data /sensing/gnss/fix",
  "source_repositories": {
    "rgb_pointcloud_cache": "https://github.com/pixmoving-auto/color_pointscloud/tree/orin",
    "rgb_pointcloud_slam": "https://github.com/pixmoving-auto/liorf/tree/robobus_color_ros2"
  },
  "notes": [
    "rgb-map profile records only front_top LiDAR, rear_top LiDAR, IMU, and GNSS by default.",
    "rgb-map-camera profile additionally records the color_pointscloud/orin front_3mm and rear_3mm compressed camera_image_jpeg streams and camera_info topics.",
    "rgb-camera-only profile records only the color_pointscloud/orin front_3mm and rear_3mm compressed camera streams for Orin-side capture.",
    "rgb-map-camera-full profile records all six electronic_rearview_mirror compressed camera_image_jpeg streams and camera_info topics.",
    "front/rear LiDAR to base_link tf snapshots are saved for liorf lidar_front/lidar_rear extrinsic config.",
    "color_pointscloud orin can generate/cache RGB pointcloud input and ros2bag through local record or TCP trigger.",
    "liorf robobus_color_ros2 consumes GlobalMap.pcdrgb as the complete RGB pointcloud map before tile-map generation.",
    "CARLA 0.9.15 import remains mesh + OpenDRIVE + collision proxy.",
    "Use --capture-profile reconstruction-rich when camera/object topics are needed for Gaussian/NuRec handoff."
  ]
}
EOF

log "recording ${#RECORD_TOPICS[@]} topics"
log "bag: ${BAG_DIR}"

set +e
if (( DURATION_SEC > 0 )); then
  timeout --foreground --signal=INT "${DURATION_SEC}" \
    ros2 bag record \
      -s "${BAG_STORAGE}" \
      --max-bag-size "${MAX_BAG_SIZE}" \
      -o "${BAG_DIR}" \
      "${RECORD_TOPICS[@]}" \
    2>&1 | tee "${RUN_DIR}/rosbag_record.log"
  RECORD_STATUS="${PIPESTATUS[0]}"
else
  ros2 bag record \
    -s "${BAG_STORAGE}" \
    --max-bag-size "${MAX_BAG_SIZE}" \
    -o "${BAG_DIR}" \
    "${RECORD_TOPICS[@]}" \
    2>&1 | tee "${RUN_DIR}/rosbag_record.log"
  RECORD_STATUS="${PIPESTATUS[0]}"
fi
set -e

printf '%s\n' "${RECORD_STATUS}" > "${RUN_DIR}/record_exit_status.txt"
if [[ "${RECORD_STATUS}" != "0" && "${RECORD_STATUS}" != "124" && "${RECORD_STATUS}" != "130" ]]; then
  log "WARN: ros2 bag record exited with status ${RECORD_STATUS}; check ${RUN_DIR}/rosbag_record.log"
fi

iso_now > "${RUN_DIR}/finished_at.txt"
df -h "${OUT_ROOT}" > "${RUN_DIR}/disk_after.txt"

if command -v ros2 >/dev/null 2>&1 && [[ -d "${BAG_DIR}" ]]; then
  ros2 bag info "${BAG_DIR}" > "${RUN_DIR}/rosbag_info.txt" 2>&1 || true
fi

if [[ "${COMPRESS_ZSTD}" == "true" ]]; then
  require_command zstd
  find "${BAG_DIR}" -type f -name '*.mcap' -print0 | while IFS= read -r -d '' file; do
    zstd -T0 -19 --rm "${file}"
  done
fi

log "capture complete: ${RUN_DIR}"
