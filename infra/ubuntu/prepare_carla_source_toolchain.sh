#!/usr/bin/env bash
set -euo pipefail

PHASE="preflight"
EXECUTE=0
WORKSPACE_ROOT="${CARLA_SOURCE_WORKSPACE:-$HOME/zmf_ws/source_toolchain}"
UNREAL_SOURCE_DIR="${UNREAL_SOURCE_DIR:-}"
CARLA_SOURCE_DIR="${CARLA_SOURCE_DIR:-}"
UE4_GIT_URL="${UE4_GIT_URL:-git@github.com:CarlaUnreal/UnrealEngine.git}"
UE4_BRANCH="${UE4_BRANCH:-carla}"
CARLA_GIT_URL="${CARLA_GIT_URL:-https://github.com/carla-simulator/carla.git}"
CARLA_TAG="${CARLA_TAG:-0.9.15}"
SWAPFILE="${CARLA_SOURCE_SWAPFILE:-/swapfile_carla_source}"
SWAP_SIZE_GB="${CARLA_SOURCE_SWAP_SIZE_GB:-32}"
BUILD_JOBS="${CARLA_SOURCE_BUILD_JOBS:-4}"
MEMORY_LOG_INTERVAL="${CARLA_SOURCE_MEMORY_LOG_INTERVAL:-30}"

usage() {
  cat <<'USAGE'
Prepare a low-memory-safe CARLA 0.9.15 + UE4.26 source toolchain.

Default mode is dry-run preflight. Add --execute to apply a phase.

Phases:
  preflight    Check CPU, memory, disk, commands, source dirs, and access hints.
  swap         Create/enable a dedicated source-build swapfile.
  deps         Install source build dependencies with apt.
  clone        Clone UnrealEngine 4.26 and CARLA 0.9.15 sources.
  ue-setup     Run UnrealEngine Setup.sh and GenerateProjectFiles.sh.
  ue-build     Build UE4Editor with low parallelism and memory logging.
  carla-setup  Run CARLA source setup using UE4_ROOT.
  carla-build  Build CARLA editor/package targets with memory logging.
  all          Run swap, deps, clone, ue-setup, ue-build, carla-setup, carla-build.

Important:
  - CARLA 0.9.15 requires CARLA's modified UnrealEngine 4.26 fork, not the plain Epic 4.26 branch.
  - UnrealEngine source requires your GitHub account to be linked with Epic Games.
  - 16 GB RAM is not enough for aggressive UE4 builds. Keep --jobs around 4 unless memory is upgraded.
  - sudo is required for swap and apt phases.

Options:
  --execute
  --phase NAME
  --workspace-root PATH
  --unreal-source-dir PATH
  --carla-source-dir PATH
  --ue4-git-url URL
  --ue4-branch NAME
  --carla-git-url URL
  --carla-tag TAG
  --swap-size-gb N
  --swapfile PATH
  --jobs N
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute) EXECUTE=1; shift ;;
    --phase) PHASE="$2"; shift 2 ;;
    --workspace-root) WORKSPACE_ROOT="$2"; shift 2 ;;
    --unreal-source-dir) UNREAL_SOURCE_DIR="$2"; shift 2 ;;
    --carla-source-dir) CARLA_SOURCE_DIR="$2"; shift 2 ;;
    --ue4-git-url) UE4_GIT_URL="$2"; shift 2 ;;
    --ue4-branch) UE4_BRANCH="$2"; shift 2 ;;
    --carla-git-url) CARLA_GIT_URL="$2"; shift 2 ;;
    --carla-tag) CARLA_TAG="$2"; shift 2 ;;
    --swap-size-gb) SWAP_SIZE_GB="$2"; shift 2 ;;
    --swapfile) SWAPFILE="$2"; shift 2 ;;
    --jobs) BUILD_JOBS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FAIL] Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

UNREAL_SOURCE_DIR="${UNREAL_SOURCE_DIR:-${WORKSPACE_ROOT}/UnrealEngine-4.26}"
CARLA_SOURCE_DIR="${CARLA_SOURCE_DIR:-${WORKSPACE_ROOT}/carla-0.9.15}"
MEMORY_LOG_DIR="${WORKSPACE_ROOT}/logs"

run() {
  local cmd="$1"
  echo "+ ${cmd}"
  if [[ "${EXECUTE}" -eq 1 ]]; then
    bash -lc "${cmd}"
  fi
}

run_may_fail() {
  local cmd="$1"
  echo "+ ${cmd}"
  if [[ "${EXECUTE}" -ne 1 ]]; then
    return 0
  fi
  bash -lc "${cmd}"
}

pass() { echo "[PASS] $1"; }
warn() { echo "[WARN] $1"; }
fail() { echo "[FAIL] $1"; }

bytes_to_gib() {
  awk -v bytes="$1" 'BEGIN { printf "%.1f", bytes / 1024 / 1024 / 1024 }'
}

current_swap_gib() {
  if [[ -r /proc/swaps ]]; then
    awk 'NR > 1 { total += $3 } END { printf "%.1f", total / 1024 / 1024 }' /proc/swaps 2>/dev/null
  else
    echo "0.0"
  fi
}

available_bytes_for_path() {
  local path="$1"
  if df -B1 "${path}" >/dev/null 2>&1; then
    df -B1 "${path}" | awk 'NR==2 { print $4 }'
  else
    df -Pk "${path}" | awk 'NR==2 { print $4 * 1024 }'
  fi
}

cpu_count() {
  if command -v nproc >/dev/null 2>&1; then
    nproc
  elif command -v sysctl >/dev/null 2>&1; then
    sysctl -n hw.ncpu 2>/dev/null || echo 4
  else
    echo 4
  fi
}

mem_total_gib() {
  if [[ -r /proc/meminfo ]]; then
    awk '/MemTotal/ { printf "%.0f", $2 / 1024 / 1024 }' /proc/meminfo
  elif command -v sysctl >/dev/null 2>&1; then
    sysctl -n hw.memsize 2>/dev/null | awk '{ printf "%.0f", $1 / 1024 / 1024 / 1024 }'
  else
    echo 16
  fi
}

recommended_jobs() {
  local mem_gib
  mem_gib="$(mem_total_gib)"
  if [[ "${mem_gib}" -lt 24 ]]; then
    echo 4
  elif [[ "${mem_gib}" -lt 48 ]]; then
    echo 8
  else
    cpu_count
  fi
}

memory_monitor_start() {
  local log_file="$1"
  mkdir -p "$(dirname "${log_file}")"
  (
    while true; do
      {
        echo "===== $(date -Iseconds) ====="
        free -h
        echo
        ps -eo pid,ppid,%mem,%cpu,rss,comm,args --sort=-rss | head -20
        echo
      } >> "${log_file}"
      sleep "${MEMORY_LOG_INTERVAL}"
    done
  ) >/dev/null 2>&1 &
  echo "$!"
}

memory_monitor_stop() {
  local pid="$1"
  if [[ -n "${pid}" ]]; then
    kill "${pid}" >/dev/null 2>&1 || true
    wait "${pid}" >/dev/null 2>&1 || true
  fi
}

run_logged() {
  local name="$1"
  local cmd="$2"
  local log_file="${MEMORY_LOG_DIR}/${name}_memory.log"
  echo "+ ${cmd}"
  if [[ "${EXECUTE}" -ne 1 ]]; then
    echo "  memory log: ${log_file}"
    return 0
  fi
  local monitor_pid
  monitor_pid="$(memory_monitor_start "${log_file}")"
  set +e
  bash -lc "${cmd}"
  local status=$?
  set -e
  memory_monitor_stop "${monitor_pid}"
  echo "memory log: ${log_file}"
  return "${status}"
}

phase_preflight() {
  echo "CARLA source toolchain preflight"
  echo "PHASE=${PHASE}"
  echo "EXECUTE=${EXECUTE}"
  echo "WORKSPACE_ROOT=${WORKSPACE_ROOT}"
  echo "UNREAL_SOURCE_DIR=${UNREAL_SOURCE_DIR}"
  echo "CARLA_SOURCE_DIR=${CARLA_SOURCE_DIR}"
  echo "UE4_GIT_URL=${UE4_GIT_URL}"
  echo "UE4_BRANCH=${UE4_BRANCH}"
  echo "CARLA_GIT_URL=${CARLA_GIT_URL}"
  echo "CARLA_TAG=${CARLA_TAG}"
  echo "SWAPFILE=${SWAPFILE}"
  echo "SWAP_SIZE_GB=${SWAP_SIZE_GB}"
  echo "BUILD_JOBS=${BUILD_JOBS}"
  echo "recommended_jobs=$(recommended_jobs)"
  echo

  if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    if [[ "${ID:-}" == "ubuntu" ]]; then
      pass "Ubuntu detected: ${PRETTY_NAME:-unknown}"
    else
      warn "Host OS is not Ubuntu: ${PRETTY_NAME:-unknown}"
    fi
  fi

  echo
  echo "CPU and memory:"
  cpu_count
  if command -v free >/dev/null 2>&1; then
    free -h
  else
    echo "free command not available on this host"
  fi
  echo "swap_gib=$(current_swap_gib)"
  if command -v swapon >/dev/null 2>&1; then
    swapon --show || true
  else
    echo "swapon command not available on this host"
  fi

  echo
  echo "Disk:"
  df -h / "${HOME}" || true
  local avail_bytes
  avail_bytes="$(available_bytes_for_path "${HOME}")"
  local avail_gib
  avail_gib="$(bytes_to_gib "${avail_bytes}")"
  if awk -v x="${avail_gib}" 'BEGIN { exit !(x >= 250) }'; then
    pass "Available disk is likely enough for source toolchain: ${avail_gib} GiB"
  else
    warn "Available disk may be tight for UE4 + CARLA source builds: ${avail_gib} GiB"
  fi

  echo
  echo "Commands:"
  for cmd in git git-lfs cmake make ninja clang clang++ gcc g++ python3 pip3 mono xbuild msbuild; do
    if command -v "${cmd}" >/dev/null 2>&1; then
      pass "${cmd}: $(command -v "${cmd}")"
    else
      warn "${cmd} missing"
    fi
  done

  echo
  if [[ -d "${UNREAL_SOURCE_DIR}/.git" ]]; then
    pass "Unreal source exists: ${UNREAL_SOURCE_DIR}"
  else
    warn "Unreal source missing: ${UNREAL_SOURCE_DIR}"
  fi
  if [[ -d "${CARLA_SOURCE_DIR}/.git" ]]; then
    pass "CARLA source exists: ${CARLA_SOURCE_DIR}"
  else
    warn "CARLA source missing: ${CARLA_SOURCE_DIR}"
  fi

  echo
  echo "Access checks are intentionally shallow. If UE clone fails, link your GitHub account with Epic Games and verify SSH/HTTPS credentials."
  echo "CARLA 0.9.15 expects the CARLA Unreal fork branch: ${UE4_GIT_URL} ${UE4_BRANCH}"
}

phase_swap() {
  local current
  current="$(current_swap_gib)"
  echo "Current swap: ${current} GiB"
  echo "Requested dedicated swapfile: ${SWAPFILE} (${SWAP_SIZE_GB} GiB)"
  run "sudo fallocate -l '${SWAP_SIZE_GB}G' '${SWAPFILE}'"
  run "sudo chmod 600 '${SWAPFILE}'"
  run "sudo mkswap '${SWAPFILE}'"
  run "sudo swapon '${SWAPFILE}'"
  run "grep -q '^${SWAPFILE} ' /etc/fstab || echo '${SWAPFILE} none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null"
  echo "After swap phase:"
  if [[ "${EXECUTE}" -eq 1 ]]; then
    free -h
    swapon --show || true
  else
    echo "Dry-run only; swap not changed."
  fi
}

phase_deps() {
  run "sudo apt-get update"
  run "sudo apt-get install -y build-essential clang lld cmake ninja-build git git-lfs python3 python-is-python3 python3-pip python3-dev python3-venv rsync unzip zip curl wget aria2 dos2unix"
  run "sudo apt-get install -y g++-12 libstdc++-12-dev"
  run "sudo apt-get install -y mono-complete libssl-dev libcurl4-openssl-dev libgtk-3-0 libgtk2.0-dev libglib2.0-dev libxcb-xinerama0 libx11-xcb1 libxi6 libxrandr2 libxinerama1 libxcursor1 libsdl2-2.0-0 libvulkan1 mesa-vulkan-drivers vulkan-tools"
  run "sudo apt-get install -y blender assimp-utils"
  run "git lfs install --skip-repo"
}

ensure_unreal_origin_matches() {
  if [[ ! -d "${UNREAL_SOURCE_DIR}/.git" ]]; then
    return 0
  fi

  local existing_origin
  existing_origin="$(git -C "${UNREAL_SOURCE_DIR}" remote get-url origin 2>/dev/null || true)"
  if [[ "${UE4_GIT_URL}" == *"CarlaUnreal/UnrealEngine"* && "${existing_origin}" != *"CarlaUnreal/UnrealEngine"* ]]; then
    local backup_dir
    backup_dir="${UNREAL_SOURCE_DIR}.pre-carla-fork.$(date +%Y%m%dT%H%M%S)"
    warn "Existing UnrealEngine origin is not CARLA's fork: ${existing_origin:-unknown}"
    warn "Moving it aside before cloning the CARLA fork: ${backup_dir}"
    if [[ "${EXECUTE}" -eq 1 ]]; then
      mv "${UNREAL_SOURCE_DIR}" "${backup_dir}"
    else
      echo "+ mv '${UNREAL_SOURCE_DIR}' '${backup_dir}'"
    fi
  fi
}

phase_clone() {
  local git_env
  local clone_failures=0
  git_env="GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new'"
  run "mkdir -p '${WORKSPACE_ROOT}'"
  ensure_unreal_origin_matches
  if [[ ! -d "${UNREAL_SOURCE_DIR}/.git" ]]; then
    if ! run_may_fail "${git_env} git clone --depth 1 --single-branch --branch '${UE4_BRANCH}' '${UE4_GIT_URL}' '${UNREAL_SOURCE_DIR}'"; then
      warn "UnrealEngine clone failed. Check Epic/GitHub authorization for ${UE4_GIT_URL}."
      clone_failures=$((clone_failures + 1))
    fi
  else
    if ! run_may_fail "${git_env} git -C '${UNREAL_SOURCE_DIR}' fetch --tags --prune origin '${UE4_BRANCH}'"; then
      warn "UnrealEngine fetch failed."
      clone_failures=$((clone_failures + 1))
    else
      run "git -C '${UNREAL_SOURCE_DIR}' checkout '${UE4_BRANCH}' || git -C '${UNREAL_SOURCE_DIR}' checkout -B '${UE4_BRANCH}' 'origin/${UE4_BRANCH}'"
    fi
  fi
  if [[ ! -d "${CARLA_SOURCE_DIR}/.git" ]]; then
    if ! run_may_fail "${git_env} git clone --depth 1 --single-branch --branch '${CARLA_TAG}' '${CARLA_GIT_URL}' '${CARLA_SOURCE_DIR}'"; then
      warn "CARLA clone failed."
      clone_failures=$((clone_failures + 1))
    fi
  else
    if ! run_may_fail "${git_env} git -C '${CARLA_SOURCE_DIR}' fetch --tags --prune"; then
      warn "CARLA fetch failed."
      clone_failures=$((clone_failures + 1))
    else
      run "git -C '${CARLA_SOURCE_DIR}' checkout '${CARLA_TAG}'"
    fi
  fi
  if [[ "${clone_failures}" -gt 0 ]]; then
    return 1
  fi
}

phase_ue_setup() {
  run "cd '${UNREAL_SOURCE_DIR}' && ./Setup.sh --threads='${BUILD_JOBS}'"
  run "cd '${UNREAL_SOURCE_DIR}' && ./GenerateProjectFiles.sh"
}

phase_ue_build() {
  local cmd
  cmd="cd '${UNREAL_SOURCE_DIR}' && Engine/Build/BatchFiles/Linux/Build.sh UE4Editor Linux Development -MaxParallelActions=${BUILD_JOBS}"
  run_logged "ue4editor_build" "${cmd}"
}

patch_carla_boost_setup() {
  local setup_script="${CARLA_SOURCE_DIR}/Util/BuildTools/Setup.sh"
  if [[ ! -f "${setup_script}" ]]; then
    warn "CARLA setup script missing, cannot patch Boost source URL: ${setup_script}"
    return 0
  fi

  if grep -Fq 'boostorg.jfrog.io/artifactory/main/release/${BOOST_VERSION}/source/${BOOST_PACKAGE_BASENAME}.tar.gz' "${setup_script}"; then
    run "sed -i 's#https://boostorg.jfrog.io/artifactory/main/release/\${BOOST_VERSION}/source/\${BOOST_PACKAGE_BASENAME}.tar.gz#https://archives.boost.io/release/\${BOOST_VERSION}/source/\${BOOST_PACKAGE_BASENAME}.tar.gz#g' '${setup_script}'"
  else
    pass "CARLA Boost source URL is already patched or differs from the known CARLA 0.9.15 default."
  fi
}

patch_carla_libpng_setup() {
  local setup_script="${CARLA_SOURCE_DIR}/Util/BuildTools/Setup.sh"
  if [[ ! -f "${setup_script}" ]]; then
    warn "CARLA setup script missing, cannot patch libpng source URL: ${setup_script}"
    return 0
  fi

  if grep -Fq 'LIBPNG_REPO=https://sourceforge.net/projects/libpng/files/libpng16/${LIBPNG_VERSION}/libpng-${LIBPNG_VERSION}.tar.xz' "${setup_script}"; then
    run "sed -i 's#LIBPNG_REPO=https://sourceforge.net/projects/libpng/files/libpng16/\${LIBPNG_VERSION}/libpng-\${LIBPNG_VERSION}.tar.xz#LIBPNG_REPO=https://download.sourceforge.net/libpng/libpng-\${LIBPNG_VERSION}.tar.xz#g' '${setup_script}'"
  else
    pass "CARLA libpng source URL is already patched or differs from the known CARLA 0.9.15 default."
  fi
}

clean_invalid_boost_archive() {
  local archive="${CARLA_SOURCE_DIR}/Build/boost_1_80_0.tar.gz"
  if [[ ! -f "${archive}" ]]; then
    return 0
  fi

  if tar -tzf "${archive}" >/dev/null 2>&1; then
    pass "Existing Boost archive is readable: ${archive}"
  else
    warn "Removing invalid cached Boost archive: ${archive}"
    run "rm -f '${archive}'"
  fi
}

clean_invalid_libpng_archive() {
  local archive="${CARLA_SOURCE_DIR}/Build/libpng-1.6.37.tar.xz"
  if [[ ! -f "${archive}" ]]; then
    return 0
  fi

  if tar -tf "${archive}" >/dev/null 2>&1; then
    pass "Existing libpng archive is readable: ${archive}"
  else
    warn "Removing invalid cached libpng archive: ${archive}"
    run "rm -f '${archive}'"
  fi
}

patch_carla_build_concurrency() {
  local environment_script="${CARLA_SOURCE_DIR}/Util/BuildTools/Environment.sh"
  if [[ ! -f "${environment_script}" ]]; then
    warn "CARLA environment script missing, cannot patch setup concurrency: ${environment_script}"
    return 0
  fi

  if grep -Fxq 'CARLA_BUILD_CONCURRENCY=`nproc --all`' "${environment_script}"; then
    run "sed -i 's#^CARLA_BUILD_CONCURRENCY=.*#CARLA_BUILD_CONCURRENCY=\${CARLA_BUILD_CONCURRENCY:-\$(nproc --all)}#' '${environment_script}'"
  else
    pass "CARLA build concurrency already respects caller override or differs from the known CARLA 0.9.15 default."
  fi
}

patch_carla_ue4_build_script() {
  local build_script="${CARLA_SOURCE_DIR}/Util/BuildTools/BuildCarlaUE4.sh"
  if [[ ! -f "${build_script}" ]]; then
    warn "CARLA UE4 build script missing, cannot patch editor build: ${build_script}"
    return 0
  fi

  if grep -Fq 'python ${PWD}/../../Util/BuildTools/enable_carsim_to_uproject.py' "${build_script}"; then
    run "sed -i 's#python \${PWD}/../../Util/BuildTools/enable_carsim_to_uproject.py#python3 \${PWD}/../../Util/BuildTools/enable_carsim_to_uproject.py#g' '${build_script}'"
  else
    pass "CARLA UE4 build script already uses python3 or differs from the known CARLA 0.9.15 default."
  fi

  if grep -Fxq '  make CarlaUE4Editor' "${build_script}"; then
    run "sed -i '/^  make CarlaUE4Editor\$/c\  make CarlaUE4Editor ARGS=\"-MaxParallelActions=\${CARLA_BUILD_CONCURRENCY:-\$(nproc --all)}\"' '${build_script}'"
  else
    pass "CARLA UE4 editor build parallelism is already patched or differs from the known CARLA 0.9.15 default."
  fi
}

phase_carla_setup() {
  patch_carla_boost_setup
  patch_carla_libpng_setup
  clean_invalid_boost_archive
  clean_invalid_libpng_archive
  patch_carla_build_concurrency
  run "cd '${CARLA_SOURCE_DIR}' && UE4_ROOT='${UNREAL_SOURCE_DIR}' CARLA_BUILD_CONCURRENCY='${BUILD_JOBS}' make setup"
}

phase_carla_build() {
  patch_carla_ue4_build_script
  run_logged "carla_pythonapi_build" "cd '${CARLA_SOURCE_DIR}' && UE4_ROOT='${UNREAL_SOURCE_DIR}' CARLA_BUILD_CONCURRENCY='${BUILD_JOBS}' make PythonAPI ARGS='-j${BUILD_JOBS}'"
  run_logged "carla_libcarla_build" "cd '${CARLA_SOURCE_DIR}' && UE4_ROOT='${UNREAL_SOURCE_DIR}' CARLA_BUILD_CONCURRENCY='${BUILD_JOBS}' make LibCarla ARGS='-j${BUILD_JOBS}'"
  run_logged "carla_ue4editor_build" "cd '${CARLA_SOURCE_DIR}' && UE4_ROOT='${UNREAL_SOURCE_DIR}' CARLA_BUILD_CONCURRENCY='${BUILD_JOBS}' make CarlaUE4Editor ARGS='-j${BUILD_JOBS}'"
}

run_phase() {
  case "$1" in
    preflight) phase_preflight ;;
    swap) phase_swap ;;
    deps) phase_deps ;;
    clone) phase_clone ;;
    ue-setup) phase_ue_setup ;;
    ue-build) phase_ue_build ;;
    carla-setup) phase_carla_setup ;;
    carla-build) phase_carla_build ;;
    all)
      phase_swap
      phase_deps
      phase_clone
      phase_ue_setup
      phase_ue_build
      phase_carla_setup
      phase_carla_build
      ;;
    *) echo "[FAIL] Unknown phase: $1" >&2; usage >&2; exit 2 ;;
  esac
}

run_phase "${PHASE}"
