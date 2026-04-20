#!/usr/bin/env bash
set -euo pipefail

EXECUTE=0
WITH_ADDITIONAL_MAPS=0
FORCE_DOWNLOAD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -Execute|--execute)
      EXECUTE=1
      shift
      ;;
    --with-additional-maps)
      WITH_ADDITIONAL_MAPS=1
      shift
      ;;
    --force-download)
      FORCE_DOWNLOAD=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: bash infra/ubuntu/prepare_carla_runtime.sh [--execute] [--with-additional-maps] [--force-download]" >&2
      exit 2
      ;;
  esac
done

CARLA_VERSION="0.9.15"
CARLA_RUNTIME_ROOT="${CARLA_0915_ROOT:-$HOME/CARLA_0.9.15}"
CARLA_RUNTIME_PARENT="$(dirname "$CARLA_RUNTIME_ROOT")"
DOWNLOAD_DIR="${CARLA_DOWNLOAD_DIR:-$HOME/.cache/zmf/carla}"
BASE_URL="${CARLA_BASE_URL:-https://tiny.carla.org/carla-0-9-15-linux}"
ADDITIONAL_MAPS_URL="${CARLA_ADDITIONAL_MAPS_URL:-https://tiny.carla.org/additional-maps-0-9-15-linux}"
BASE_ARCHIVE="${DOWNLOAD_DIR}/CARLA_${CARLA_VERSION}.tar.gz"
MAPS_ARCHIVE="${DOWNLOAD_DIR}/AdditionalMaps_${CARLA_VERSION}.tar.gz"

if [[ -z "${http_proxy:-}" && -f "$HOME/.local/share/zmf/clash_proxy_env.sh" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.local/share/zmf/clash_proxy_env.sh"
fi

download_file() {
  local url="$1"
  local output="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --retry-delay 2 -C - -o "$output" "$url"
  else
    wget -c -O "$output" "$url"
  fi
}

archive_ready() {
  local archive="$1"
  [[ -f "$archive" ]] && tar -tzf "$archive" >/dev/null 2>&1
}

extract_archive() {
  local archive="$1"
  local destination="$2"
  mkdir -p "$destination"
  tar -xzf "$archive" -C "$destination"
}

echo "Preparing CARLA runtime ${CARLA_VERSION}"
echo "CARLA runtime root: ${CARLA_RUNTIME_ROOT}"
echo "Download dir: ${DOWNLOAD_DIR}"
echo "Base archive URL: ${BASE_URL}"
echo "Additional maps URL: ${ADDITIONAL_MAPS_URL}"
echo "WITH_ADDITIONAL_MAPS=${WITH_ADDITIONAL_MAPS}"
echo "FORCE_DOWNLOAD=${FORCE_DOWNLOAD}"
echo "EXECUTE=${EXECUTE}"

if [[ -n "${http_proxy:-}" ]]; then
  echo "Using proxy: ${http_proxy}"
else
  echo "Using direct network access"
fi

cat <<EOF

Planned steps:
1. Ensure ${CARLA_RUNTIME_PARENT} and ${DOWNLOAD_DIR} exist
2. Download the official CARLA ${CARLA_VERSION} Linux archive
3. Extract the archive into ${CARLA_RUNTIME_ROOT}
4. Optionally download and extract Additional Maps
5. Verify ${CARLA_RUNTIME_ROOT}/CarlaUE4.sh exists
EOF

if [[ "$EXECUTE" -ne 1 ]]; then
  echo
  echo "Dry run only. Re-run with:"
  echo "  bash infra/ubuntu/prepare_carla_runtime.sh --execute"
  echo
  echo "Optional:"
  echo "  bash infra/ubuntu/prepare_carla_runtime.sh --execute --with-additional-maps"
  exit 0
fi

mkdir -p "$CARLA_RUNTIME_PARENT" "$DOWNLOAD_DIR"

if [[ -x "$CARLA_RUNTIME_ROOT/CarlaUE4.sh" && "$FORCE_DOWNLOAD" -ne 1 ]]; then
  echo "[OK] CarlaUE4.sh already exists at ${CARLA_RUNTIME_ROOT}"
else
  mkdir -p "$CARLA_RUNTIME_ROOT"
  if [[ "$FORCE_DOWNLOAD" -eq 1 ]] || ! archive_ready "$BASE_ARCHIVE"; then
    echo "+ Downloading base runtime"
    download_file "$BASE_URL" "$BASE_ARCHIVE"
  else
    echo "[OK] Reusing existing base archive: ${BASE_ARCHIVE}"
  fi

  echo "+ Extracting base runtime into ${CARLA_RUNTIME_ROOT}"
  extract_archive "$BASE_ARCHIVE" "$CARLA_RUNTIME_ROOT"
fi

if [[ "$WITH_ADDITIONAL_MAPS" -eq 1 ]]; then
  if [[ "$FORCE_DOWNLOAD" -eq 1 ]] || ! archive_ready "$MAPS_ARCHIVE"; then
    echo "+ Downloading additional maps"
    download_file "$ADDITIONAL_MAPS_URL" "$MAPS_ARCHIVE"
  else
    echo "[OK] Reusing existing additional maps archive: ${MAPS_ARCHIVE}"
  fi

  echo "+ Extracting additional maps into ${CARLA_RUNTIME_ROOT}"
  extract_archive "$MAPS_ARCHIVE" "$CARLA_RUNTIME_ROOT"
fi

if [[ -x "$CARLA_RUNTIME_ROOT/CarlaUE4.sh" ]]; then
  echo "[OK] CarlaUE4.sh is available"
else
  echo "[WARN] CarlaUE4.sh is still missing under ${CARLA_RUNTIME_ROOT}"
fi

echo
echo "Recommended validation command:"
echo "bash '${CARLA_RUNTIME_ROOT}/CarlaUE4.sh' -RenderOffScreen -carla-rpc-port=2000"
