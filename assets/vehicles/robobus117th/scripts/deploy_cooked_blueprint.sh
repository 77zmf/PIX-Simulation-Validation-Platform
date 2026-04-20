#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

CARLA_ROOT="${CARLA_ROOT:-/home/pixmoving/CARLA_0.9.15}"
PACKAGE_DIR=""
BLUEPRINT_ID="${BLUEPRINT_ID:-vehicle.pixmoving.robobus}"
SCENARIO_PATH="${SCENARIO_PATH:-${REPO_ROOT}/scenarios/l0/robobus117th_town01_closed_loop.yaml}"
EXECUTE=0
UPDATE_SCENARIO=0

usage() {
  cat <<'USAGE'
Deploy cooked robobus117th CARLA vehicle assets after UE4 authoring is complete.

Options:
  --package-dir PATH     Directory containing cooked/edited CARLA content files.
  --carla-root PATH      CARLA runtime root. Defaults to /home/pixmoving/CARLA_0.9.15.
  --blueprint-id ID      Defaults to vehicle.pixmoving.robobus.
  --scenario PATH        Scenario to update when --update-scenario is set.
  --update-scenario      Replace carla_vehicle_type in the scenario.
  --execute              Actually copy files and update scenario. Default is dry-run.

Accepted package layouts:
  1. PACKAGE/CarlaUE4/Content/Carla/Blueprints/Vehicles/PixMoving/Robobus117th/*.uasset
  2. PACKAGE/Content/Carla/Blueprints/Vehicles/PixMoving/Robobus117th/*.uasset
  3. PACKAGE/*.uasset, PACKAGE/*.uexp, PACKAGE/*.ubulk
  4. PACKAGE/*.pak, copied to CarlaUE4/Content/Paks
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package-dir) PACKAGE_DIR="$2"; shift 2 ;;
    --carla-root) CARLA_ROOT="$2"; shift 2 ;;
    --blueprint-id) BLUEPRINT_ID="$2"; shift 2 ;;
    --scenario) SCENARIO_PATH="$2"; shift 2 ;;
    --update-scenario) UPDATE_SCENARIO=1; shift ;;
    --execute) EXECUTE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FAIL] Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${PACKAGE_DIR}" ]]; then
  echo "[FAIL] --package-dir is required" >&2
  usage >&2
  exit 2
fi
if [[ ! -d "${PACKAGE_DIR}" ]]; then
  echo "[FAIL] package dir not found: ${PACKAGE_DIR}" >&2
  exit 1
fi

DEST_CONTENT="${CARLA_ROOT}/CarlaUE4/Content/Carla/Blueprints/Vehicles/PixMoving/Robobus117th"
DEST_PAKS="${CARLA_ROOT}/CarlaUE4/Content/Paks"

SOURCE_CONTENT=""
for candidate in \
  "${PACKAGE_DIR}/CarlaUE4/Content/Carla/Blueprints/Vehicles/PixMoving/Robobus117th" \
  "${PACKAGE_DIR}/Content/Carla/Blueprints/Vehicles/PixMoving/Robobus117th" \
  "${PACKAGE_DIR}"; do
  if find "${candidate}" -maxdepth 1 -type f \( -name '*.uasset' -o -name '*.uexp' -o -name '*.ubulk' \) >/dev/null 2>&1; then
    SOURCE_CONTENT="${candidate}"
    break
  fi
done

if [[ -z "${SOURCE_CONTENT}" ]]; then
  echo "[FAIL] no uasset/uexp/ubulk files found in accepted package layouts" >&2
  exit 1
fi

if ! find "${SOURCE_CONTENT}" -maxdepth 1 -type f -name 'BP_Robobus117th.uasset' | grep -q .; then
  echo "[WARN] BP_Robobus117th.uasset not found; package may not contain the expected main vehicle blueprint"
fi

echo "CARLA_ROOT=${CARLA_ROOT}"
echo "SOURCE_CONTENT=${SOURCE_CONTENT}"
echo "DEST_CONTENT=${DEST_CONTENT}"
echo "BLUEPRINT_ID=${BLUEPRINT_ID}"
echo "EXECUTE=${EXECUTE}"

echo
echo "Content files to deploy:"
find "${SOURCE_CONTENT}" -maxdepth 1 -type f \( -name '*.uasset' -o -name '*.uexp' -o -name '*.ubulk' \) | sort

PAK_FILES=()
while IFS= read -r pak; do
  PAK_FILES+=("${pak}")
done < <(find "${PACKAGE_DIR}" -maxdepth 2 -type f -name '*.pak' | sort)

if [[ "${#PAK_FILES[@]}" -gt 0 ]]; then
  echo
  echo "Pak files to deploy:"
  printf '%s\n' "${PAK_FILES[@]}"
fi

if [[ "${EXECUTE}" -eq 1 ]]; then
  mkdir -p "${DEST_CONTENT}"
  find "${SOURCE_CONTENT}" -maxdepth 1 -type f \( -name '*.uasset' -o -name '*.uexp' -o -name '*.ubulk' \) -exec cp -a {} "${DEST_CONTENT}/" \;

  if [[ "${#PAK_FILES[@]}" -gt 0 ]]; then
    mkdir -p "${DEST_PAKS}"
    for pak in "${PAK_FILES[@]}"; do
      cp -a "${pak}" "${DEST_PAKS}/"
    done
  fi

  if [[ "${UPDATE_SCENARIO}" -eq 1 ]]; then
    if [[ ! -f "${SCENARIO_PATH}" ]]; then
      echo "[FAIL] scenario not found: ${SCENARIO_PATH}" >&2
      exit 1
    fi
    tmp="${SCENARIO_PATH}.tmp"
    sed "s#^\\([[:space:]]*carla_vehicle_type:\\).*#\\1 ${BLUEPRINT_ID}#" "${SCENARIO_PATH}" > "${tmp}"
    mv "${tmp}" "${SCENARIO_PATH}"
    echo "[PASS] Updated scenario carla_vehicle_type: ${SCENARIO_PATH}"
  fi
else
  echo
  echo "Dry-run only. Re-run with --execute to copy files."
fi

echo
echo "Post-deploy verification command:"
echo "  python3 ${SCRIPT_DIR}/verify_carla_blueprint.py --blueprint-id ${BLUEPRINT_ID}"
