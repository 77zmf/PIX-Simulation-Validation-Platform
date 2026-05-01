#!/usr/bin/env bash
set -euo pipefail

CARLA_ROOT="${CARLA_ROOT:-/home/pixmoving/zmf_ws/source_toolchain/carla-0.9.15}"
MODE="apply"

usage() {
  cat <<'USAGE'
Apply the PIX Robobus117th CARLA 0.9.15 runtime patch set.

Usage:
  assets/vehicles/robobus117th/scripts/apply_robobus_bbox_override_to_carla.sh [--carla-root PATH] [--dry-run|--reverse]

The patch set changes CARLA's runtime VehicleBounds registration for
vehicle.pixmoving.robobus and guards the editor-only Robobus visual authoring
commandlet out of Shipping builds. It does not regenerate UE4 PhysicsAsset
collision.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --carla-root) CARLA_ROOT="$2"; shift 2 ;;
    --dry-run) MODE="dry-run"; shift ;;
    --reverse) MODE="reverse"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
PATCH_PATH="${REPO_ROOT}/assets/vehicles/robobus117th/patches/carla_0_9_15_robobus_bbox_override.patch"
COMMANDLET_PATCH_PATH="${REPO_ROOT}/assets/vehicles/robobus117th/patches/carla_0_9_15_robobus_editor_commandlet_guard.patch"
TARGET_FILE="${CARLA_ROOT}/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Actor/ActorDispatcher.cpp"
COMMANDLET_TARGET_FILE="${CARLA_ROOT}/Unreal/CarlaUE4/Source/CarlaUE4/RobobusVisualAuthorCommandlet.cpp"

if [[ ! -f "${PATCH_PATH}" ]]; then
  echo "Patch file missing: ${PATCH_PATH}" >&2
  exit 1
fi
if [[ ! -f "${COMMANDLET_PATCH_PATH}" ]]; then
  echo "Patch file missing: ${COMMANDLET_PATCH_PATH}" >&2
  exit 1
fi

if [[ ! -f "${TARGET_FILE}" ]]; then
  echo "CARLA target file missing: ${TARGET_FILE}" >&2
  exit 1
fi
if [[ ! -f "${COMMANDLET_TARGET_FILE}" ]]; then
  echo "CARLA target file missing: ${COMMANDLET_TARGET_FILE}" >&2
  exit 1
fi

cd "${CARLA_ROOT}"

patch_if_needed() {
  local name="$1"
  local patch_path="$2"
  local target_file="$3"
  local marker="$4"
  case "${MODE}" in
    dry-run)
      if grep -q "${marker}" "${target_file}"; then
        echo "Patch already appears to be applied: ${name}"
      else
        patch --dry-run -p1 < "${patch_path}"
      fi
      ;;
    reverse)
      if grep -q "${marker}" "${target_file}"; then
        patch -R -p1 < "${patch_path}"
      else
        echo "Patch does not appear to be applied, skipping reverse: ${name}"
      fi
      ;;
    apply)
      if grep -q "${marker}" "${target_file}"; then
        echo "Patch already appears to be applied: ${name}"
      else
        patch -p1 < "${patch_path}"
      fi
      ;;
  esac
}

case "${MODE}" in
  dry-run)
    patch_if_needed "robobus-bbox-override" "${PATCH_PATH}" "${TARGET_FILE}" "PIX_ROBOBUS_BBOX_OVERRIDE"
    patch_if_needed "robobus-editor-commandlet-guard" "${COMMANDLET_PATCH_PATH}" "${COMMANDLET_TARGET_FILE}" "commandlet is editor-only"
    ;;
  reverse)
    patch_if_needed "robobus-editor-commandlet-guard" "${COMMANDLET_PATCH_PATH}" "${COMMANDLET_TARGET_FILE}" "commandlet is editor-only"
    patch_if_needed "robobus-bbox-override" "${PATCH_PATH}" "${TARGET_FILE}" "PIX_ROBOBUS_BBOX_OVERRIDE"
    ;;
  apply)
    patch_if_needed "robobus-bbox-override" "${PATCH_PATH}" "${TARGET_FILE}" "PIX_ROBOBUS_BBOX_OVERRIDE"
    patch_if_needed "robobus-editor-commandlet-guard" "${COMMANDLET_PATCH_PATH}" "${COMMANDLET_TARGET_FILE}" "commandlet is editor-only"
    ;;
esac

echo "robobus CARLA runtime patch set ${MODE} complete for ${CARLA_ROOT}"
