#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

INSTALL_ROOT="${INSTALL_ROOT:-/home/pixmoving/zmf_ws/projects/autoware_universe/private_autoware/install}"
PARAMETER_ROOT="${PARAMETER_ROOT:-/home/pixmoving/pix/parameter}"
CARLA_ROOT="${CARLA_ROOT:-/home/pixmoving/CARLA_0.9.15}"
OUTPUT_DIR="${OUTPUT_DIR:-${REPO_ROOT}/artifacts/carla_blueprints/robobus117th_source}"

usage() {
  cat <<'USAGE'
Prepare the PixMoving robobus117th CARLA blueprint source package.

Options:
  --install-root PATH    Autoware install root. Defaults to INSTALL_ROOT or company host path.
  --parameter-root PATH  117th parameter root. Defaults to PARAMETER_ROOT or /home/pixmoving/pix/parameter.
  --carla-root PATH      CARLA 0.9.15 root. Defaults to CARLA_ROOT or /home/pixmoving/CARLA_0.9.15.
  --output-dir PATH      Output package directory. Defaults to artifacts/carla_blueprints/robobus117th_source.
  -h, --help             Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root)
      INSTALL_ROOT="$2"
      shift 2
      ;;
    --parameter-root)
      PARAMETER_ROOT="$2"
      shift 2
      ;;
    --carla-root)
      CARLA_ROOT="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

copy_file() {
  local src="$1"
  local dst="$2"
  if [[ -f "${src}" ]]; then
    mkdir -p "$(dirname "${dst}")"
    cp -a "${src}" "${dst}"
    printf 'copied: %s -> %s\n' "${src}" "${dst}"
  else
    printf 'missing: %s\n' "${src}" | tee -a "${OUTPUT_DIR}/missing_files.txt" >/dev/null
  fi
}

copy_tree_files() {
  local src_root="$1"
  local dst_root="$2"
  shift 2
  if [[ ! -d "${src_root}" ]]; then
    printf 'missing: %s\n' "${src_root}" | tee -a "${OUTPUT_DIR}/missing_files.txt" >/dev/null
    return 0
  fi

  while IFS= read -r file; do
    local rel="${file#${src_root}/}"
    copy_file "${file}" "${dst_root}/${rel}"
  done < <(find "${src_root}" -type f "$@" | sort)
}

rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"
: > "${OUTPUT_DIR}/missing_files.txt"

SOURCE_DIR="${OUTPUT_DIR}/source"
REPO_INPUT_DIR="${OUTPUT_DIR}/repo_inputs"
REPORT_DIR="${OUTPUT_DIR}/reports"
mkdir -p "${SOURCE_DIR}" "${REPO_INPUT_DIR}" "${REPORT_DIR}"

VEHICLE_SHARE="${INSTALL_ROOT}/robobus_description/share/robobus_description"
SENSOR_SHARE="${INSTALL_ROOT}/robobus_sensor_kit_description/share/robobus_sensor_kit_description"

copy_tree_files "${VEHICLE_SHARE}" "${SOURCE_DIR}/install/robobus_description" \
  \( -name '*.dae' -o -name '*.obj' -o -name '*.fbx' -o -name '*.stl' -o -name '*.urdf' -o -name '*.xacro' -o -name '*.yaml' -o -name '*.yml' -o -name '*.rviz' \)

copy_tree_files "${SENSOR_SHARE}" "${SOURCE_DIR}/install/robobus_sensor_kit_description" \
  \( -name '*.dae' -o -name '*.obj' -o -name '*.fbx' -o -name '*.stl' -o -name '*.urdf' -o -name '*.xacro' -o -name '*.yaml' -o -name '*.yml' \)

copy_file "${PARAMETER_ROOT}/HMI/vehicle_info.yml" "${SOURCE_DIR}/parameter/HMI/vehicle_info.yml"

if [[ -d "${PARAMETER_ROOT}/sensor_kit/robobus_sensor_kit_description" ]]; then
  copy_tree_files "${PARAMETER_ROOT}/sensor_kit/robobus_sensor_kit_description" "${SOURCE_DIR}/parameter/sensor_kit/robobus_sensor_kit_description" \
    \( -name '*.yaml' -o -name '*.yml' -o -name '*.json' \)
else
  printf 'missing: %s\n' "${PARAMETER_ROOT}/sensor_kit/robobus_sensor_kit_description" | tee -a "${OUTPUT_DIR}/missing_files.txt" >/dev/null
fi

copy_file "${REPO_ROOT}/assets/vehicles/robobus117th/blueprint_source_manifest.yaml" "${REPO_INPUT_DIR}/blueprint_source_manifest.yaml"
copy_file "${REPO_ROOT}/assets/vehicles/robobus117th/blueprint_authoring_requirements.yaml" "${REPO_INPUT_DIR}/blueprint_authoring_requirements.yaml"
copy_file "${REPO_ROOT}/assets/sensors/carla/robobus117th_sensor_mapping.yaml" "${REPO_INPUT_DIR}/robobus117th_sensor_mapping.yaml"
copy_file "${REPO_ROOT}/assets/sensors/carla/robobus117th_sensor_kit_calibration.yaml" "${REPO_INPUT_DIR}/robobus117th_sensor_kit_calibration.yaml"
copy_file "${REPO_ROOT}/assets/sensors/carla/robobus117th_objects.json" "${REPO_INPUT_DIR}/robobus117th_objects.json"
copy_file "${REPO_ROOT}/scenarios/l0/robobus117th_town01_closed_loop.yaml" "${REPO_INPUT_DIR}/robobus117th_town01_closed_loop.yaml"

{
  echo "generated_at: $(date -Iseconds)"
  echo "install_root: ${INSTALL_ROOT}"
  echo "parameter_root: ${PARAMETER_ROOT}"
  echo "carla_root: ${CARLA_ROOT}"
  echo "output_dir: ${OUTPUT_DIR}"
  echo "desired_carla_blueprint_id: vehicle.pixmoving.robobus"
  echo "current_runtime_fallback: vehicle.toyota.prius"
  echo "status: source_package_only"
  echo "notes:"
  echo "  - This package is ready for UE4.26/CARLA authoring, but it is not a cooked CARLA vehicle blueprint."
  echo "  - If no UE4 editor/cook tools are installed, generate/import/cook must happen on another UE4.26-capable workstation."
} > "${OUTPUT_DIR}/PACKAGE_MANIFEST.yaml"

{
  echo "CARLA root: ${CARLA_ROOT}"
  echo "CARLA uproject: ${CARLA_ROOT}/CarlaUE4/CarlaUE4.uproject"
  echo
  echo "Command availability:"
  for cmd in UE4Editor UE4Editor-Cmd UnrealEditor UnrealEditor-Cmd RunUAT.sh blender assimp meshlabserver python3; do
    if command -v "${cmd}" >/dev/null 2>&1; then
      printf '%s: %s\n' "${cmd}" "$(command -v "${cmd}")"
    else
      printf '%s: missing\n' "${cmd}"
    fi
  done
  echo
  if [[ -f "${CARLA_ROOT}/CarlaUE4/CarlaUE4.uproject" ]]; then
    echo "carla_uproject_present: true"
  else
    echo "carla_uproject_present: false"
  fi
} > "${REPORT_DIR}/toolchain_status.txt"

find "${OUTPUT_DIR}" -type f | sort > "${REPORT_DIR}/file_list.txt"

cat > "${OUTPUT_DIR}/README_NEXT_STEPS_CN.md" <<'NEXT_STEPS'
# Robobus117th CARLA 蓝图源包下一步

这个目录已经收集了 Autoware install、117th 参数集和本仓库 CARLA bridge 所需的输入。它还不是 cooked CARLA 蓝图。

UE4.26/CARLA authoring 流程：

1. 用 UE4.26 打开 CARLA 0.9.15 的 `CarlaUE4.uproject`。
2. 导入 `source/install/robobus_description/mesh/robobus.dae`。
3. 在 `/Game/Carla/Blueprints/Vehicles/PixMoving/Robobus117th` 创建车辆蓝图，目标 blueprint id 为 `vehicle.pixmoving.robobus`。
4. 配置材质、碰撞、physics asset、wheel blueprint 和 vehicle movement。
5. 若 DAE 只是静态视觉网格，先做视觉占位；真正可驾驶车辆还需要补齐 rig/physics/wheel。
6. Cook/package 成 Linux runtime 可加载资产。
7. 修改 `scenarios/l0/robobus117th_town01_closed_loop.yaml` 的 `carla_vehicle_type`，从 `vehicle.toyota.prius` 切到 `vehicle.pixmoving.robobus`。
8. 重新跑 L0 smoke，确认 ego actor 类型和传感器话题都正常。

回滚方式：把 `carla_vehicle_type` 改回 `vehicle.toyota.prius`。
NEXT_STEPS

if [[ ! -s "${OUTPUT_DIR}/missing_files.txt" ]]; then
  rm -f "${OUTPUT_DIR}/missing_files.txt"
fi

echo "Prepared robobus117th CARLA blueprint source package:"
echo "  ${OUTPUT_DIR}"
echo "Reports:"
echo "  ${REPORT_DIR}/toolchain_status.txt"
echo "  ${REPORT_DIR}/file_list.txt"
