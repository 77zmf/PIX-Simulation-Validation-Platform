#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

INSTALL_ROOT="${INSTALL_ROOT:-/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware/install}"
PARAMETER_ROOT="${PARAMETER_ROOT:-/home/pixmoving/pix/parameter}"
CARLA_ROOT="${CARLA_ROOT:-/home/pixmoving/CARLA_0.9.15}"
SOURCE_PACKAGE="${SOURCE_PACKAGE:-${REPO_ROOT}/artifacts/carla_blueprints/robobus117th_source}"
BLUEPRINT_ID="${BLUEPRINT_ID:-vehicle.pixmoving.robobus}"
CARLA_HOST="${CARLA_HOST:-127.0.0.1}"
CARLA_PORT="${CARLA_PORT:-2000}"
STRICT_SOURCE=0
STRICT_UNREAL=0
CHECK_RUNTIME=0

usage() {
  cat <<'USAGE'
Check robobus117th CARLA blueprint readiness.

Options:
  --strict-source     Exit non-zero if source package inputs are missing.
  --strict-unreal     Exit non-zero if UE4/cook tooling is missing.
  --check-runtime     Try connecting to CARLA and verifying the blueprint id.
  --install-root PATH
  --parameter-root PATH
  --carla-root PATH
  --source-package PATH
  --blueprint-id ID
  --host HOST
  --port PORT
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict-source) STRICT_SOURCE=1; shift ;;
    --strict-unreal) STRICT_UNREAL=1; shift ;;
    --check-runtime) CHECK_RUNTIME=1; shift ;;
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    --parameter-root) PARAMETER_ROOT="$2"; shift 2 ;;
    --carla-root) CARLA_ROOT="$2"; shift 2 ;;
    --source-package) SOURCE_PACKAGE="$2"; shift 2 ;;
    --blueprint-id) BLUEPRINT_ID="$2"; shift 2 ;;
    --host) CARLA_HOST="$2"; shift 2 ;;
    --port) CARLA_PORT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FAIL] Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

SOURCE_FAILURES=0
UNREAL_FAILURES=0
RUNTIME_FAILURES=0

pass() { echo "[PASS] $1"; }
warn() { echo "[WARN] $1"; }
fail_source() { echo "[FAIL] $1"; SOURCE_FAILURES=$((SOURCE_FAILURES + 1)); }
fail_unreal() { echo "[FAIL] $1"; UNREAL_FAILURES=$((UNREAL_FAILURES + 1)); }
fail_runtime() { echo "[FAIL] $1"; RUNTIME_FAILURES=$((RUNTIME_FAILURES + 1)); }

check_file_source() {
  local label="$1"
  local path="$2"
  if [[ -f "${path}" ]]; then
    pass "${label}: ${path}"
  else
    fail_source "${label} missing: ${path}"
  fi
}

check_dir_source() {
  local label="$1"
  local path="$2"
  if [[ -d "${path}" ]]; then
    pass "${label}: ${path}"
  else
    fail_source "${label} missing: ${path}"
  fi
}

check_cmd_unreal() {
  local label="$1"
  local cmd="$2"
  if command -v "${cmd}" >/dev/null 2>&1; then
    pass "${label}: $(command -v "${cmd}")"
  else
    fail_unreal "${label} missing: ${cmd}"
  fi
}

check_cmd_warn() {
  local label="$1"
  local cmd="$2"
  if command -v "${cmd}" >/dev/null 2>&1; then
    pass "${label}: $(command -v "${cmd}")"
  else
    warn "${label} missing: ${cmd}"
  fi
}

echo "Checking robobus117th CARLA blueprint readiness"
echo "REPO_ROOT=${REPO_ROOT}"
echo "INSTALL_ROOT=${INSTALL_ROOT}"
echo "PARAMETER_ROOT=${PARAMETER_ROOT}"
echo "CARLA_ROOT=${CARLA_ROOT}"
echo "SOURCE_PACKAGE=${SOURCE_PACKAGE}"
echo "BLUEPRINT_ID=${BLUEPRINT_ID}"
echo

check_file_source "vehicle mesh" "${INSTALL_ROOT}/robobus_description/share/robobus_description/mesh/robobus.dae"
check_file_source "vehicle info" "${INSTALL_ROOT}/robobus_description/share/robobus_description/config/vehicle_info.param.yaml"
check_file_source "vehicle xacro" "${INSTALL_ROOT}/robobus_description/share/robobus_description/urdf/vehicle.xacro"
check_dir_source "sensor kit share" "${INSTALL_ROOT}/robobus_sensor_kit_description/share/robobus_sensor_kit_description"
check_file_source "117th vehicle info" "${PARAMETER_ROOT}/HMI/vehicle_info.yml"
check_file_source "117th sensor extrinsics" "${PARAMETER_ROOT}/sensor_kit/robobus_sensor_kit_description/extrinsic_parameters/sensors_calibration.yaml"
check_file_source "repo sensor mapping" "${REPO_ROOT}/assets/sensors/carla/robobus117th_sensor_mapping.yaml"
check_file_source "repo sensor calibration" "${REPO_ROOT}/assets/sensors/carla/robobus117th_sensor_kit_calibration.yaml"
check_file_source "CARLA uproject" "${CARLA_ROOT}/CarlaUE4/CarlaUE4.uproject"

if [[ -d "${SOURCE_PACKAGE}" ]]; then
  pass "source package exists: ${SOURCE_PACKAGE}"
  check_file_source "packaged mesh" "${SOURCE_PACKAGE}/source/install/robobus_description/mesh/robobus.dae"
  check_file_source "packaged manifest" "${SOURCE_PACKAGE}/repo_inputs/blueprint_source_manifest.yaml"
else
  warn "source package missing; run prepare_source_package.sh first: ${SOURCE_PACKAGE}"
fi

echo
echo "Optional mesh conversion tools"
check_cmd_warn "blender" blender
check_cmd_warn "assimp" assimp

echo
echo "UE4 authoring/cook tools"
check_cmd_unreal "UE4Editor" UE4Editor
check_cmd_unreal "UE4Editor-Cmd" UE4Editor-Cmd
check_cmd_unreal "RunUAT.sh" RunUAT.sh
check_cmd_unreal "UnrealPak" UnrealPak

CONTENT_DIR="${CARLA_ROOT}/CarlaUE4/Content/Carla/Blueprints/Vehicles/PixMoving/Robobus117th"
if [[ -d "${CONTENT_DIR}" ]]; then
  pass "candidate CARLA content dir exists: ${CONTENT_DIR}"
  find "${CONTENT_DIR}" -maxdepth 2 -type f | sort
else
  warn "candidate CARLA content dir missing: ${CONTENT_DIR}"
fi

if [[ "${CHECK_RUNTIME}" -eq 1 ]]; then
  echo
  echo "Runtime blueprint library check"
  if python3 "${SCRIPT_DIR}/verify_carla_blueprint.py" --host "${CARLA_HOST}" --port "${CARLA_PORT}" --blueprint-id "${BLUEPRINT_ID}"; then
    pass "runtime blueprint is available: ${BLUEPRINT_ID}"
  else
    fail_runtime "runtime blueprint is not available: ${BLUEPRINT_ID}"
  fi
fi

echo
echo "Summary:"
echo "  source_failures=${SOURCE_FAILURES}"
echo "  unreal_tool_failures=${UNREAL_FAILURES}"
echo "  runtime_failures=${RUNTIME_FAILURES}"

if [[ "${STRICT_SOURCE}" -eq 1 && "${SOURCE_FAILURES}" -gt 0 ]]; then
  exit 1
fi
if [[ "${STRICT_UNREAL}" -eq 1 && "${UNREAL_FAILURES}" -gt 0 ]]; then
  exit 1
fi
if [[ "${CHECK_RUNTIME}" -eq 1 && "${RUNTIME_FAILURES}" -gt 0 ]]; then
  exit 1
fi

exit 0
