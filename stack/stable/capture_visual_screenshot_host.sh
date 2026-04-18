#!/usr/bin/env bash
set -euo pipefail

RUN_DIR=""
RENDER_MODE=""
RVIZ=""
DISPLAY_ARG=""
XAUTHORITY_ARG=""
WAIT_SEC=""
OUTPUT_NAME="visual_startup.png"
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --render-mode) RENDER_MODE="$2"; shift 2 ;;
    --rviz) RVIZ="$2"; shift 2 ;;
    --display) DISPLAY_ARG="$2"; shift 2 ;;
    --xauthority) XAUTHORITY_ARG="$2"; shift 2 ;;
    --wait-sec) WAIT_SEC="$2"; shift 2 ;;
    --output-name) OUTPUT_NAME="$2"; shift 2 ;;
    -Execute|--execute) EXECUTE=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

truthy() {
  local normalized
  normalized="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$normalized" in
    1|true|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

VISUAL_REQUESTED=0
RENDER_MODE_NORMALIZED="$(printf '%s' "${RENDER_MODE:-}" | tr '[:upper:]' '[:lower:]')"
case "$RENDER_MODE_NORMALIZED" in
  visual|windowed) VISUAL_REQUESTED=1 ;;
esac
if truthy "${RVIZ:-}"; then
  VISUAL_REQUESTED=1
fi

if [[ "$VISUAL_REQUESTED" -ne 1 ]]; then
  echo "Visual screenshot skipped: render_mode=${RENDER_MODE:-unset}, rviz=${RVIZ:-unset}"
  exit 0
fi

if [[ -z "$RUN_DIR" ]]; then
  echo "--run-dir is required for visual screenshot capture" >&2
  exit 2
fi

WAIT_SEC="${WAIT_SEC:-${SIMCTL_VISUAL_SCREENSHOT_WAIT_SEC:-8}}"
DISPLAY_ARG="${DISPLAY_ARG:-${DISPLAY:-:0}}"
if [[ -z "$XAUTHORITY_ARG" ]]; then
  if [[ -n "${XAUTHORITY:-}" ]]; then
    XAUTHORITY_ARG="$XAUTHORITY"
  elif [[ -f "/run/user/$(id -u)/gdm/Xauthority" ]]; then
    XAUTHORITY_ARG="/run/user/$(id -u)/gdm/Xauthority"
  elif [[ -f "$HOME/.Xauthority" ]]; then
    XAUTHORITY_ARG="$HOME/.Xauthority"
  fi
fi

SCREENSHOT_DIR="${RUN_DIR}/screenshots"
OUTPUT_PATH="${SCREENSHOT_DIR}/${OUTPUT_NAME}"
METADATA_PATH="${SCREENSHOT_DIR}/${OUTPUT_NAME%.*}.json"

echo "Visual screenshot requested"
echo "RunDir: ${RUN_DIR}"
echo "Render mode: ${RENDER_MODE:-unset}"
echo "RViz: ${RVIZ:-unset}"
echo "DISPLAY: ${DISPLAY_ARG}"
echo "XAUTHORITY: ${XAUTHORITY_ARG:-unset}"
echo "Wait seconds: ${WAIT_SEC}"
echo "Output: ${OUTPUT_PATH}"

if [[ "$EXECUTE" -ne 1 ]]; then
  exit 0
fi

mkdir -p "$SCREENSHOT_DIR"
export DISPLAY="$DISPLAY_ARG"
if [[ -n "$XAUTHORITY_ARG" ]]; then
  export XAUTHORITY="$XAUTHORITY_ARG"
fi

if [[ "$WAIT_SEC" != "0" ]]; then
  sleep "$WAIT_SEC"
fi

CAPTURE_TOOL=""
if command -v gnome-screenshot >/dev/null 2>&1 && gnome-screenshot -f "$OUTPUT_PATH"; then
  CAPTURE_TOOL="gnome-screenshot"
elif command -v import >/dev/null 2>&1 && import -window root "$OUTPUT_PATH"; then
  CAPTURE_TOOL="import"
elif command -v scrot >/dev/null 2>&1 && scrot "$OUTPUT_PATH"; then
  CAPTURE_TOOL="scrot"
else
  echo "Unable to capture visual screenshot; install gnome-screenshot, ImageMagick import, or scrot." >&2
  exit 1
fi

if [[ ! -s "$OUTPUT_PATH" ]]; then
  echo "Screenshot command succeeded but output is empty: ${OUTPUT_PATH}" >&2
  exit 1
fi

cat > "$METADATA_PATH" <<JSON
{
  "captured_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "path": "${OUTPUT_PATH}",
  "tool": "${CAPTURE_TOOL}",
  "display": "${DISPLAY_ARG}",
  "xauthority": "${XAUTHORITY_ARG:-}",
  "render_mode": "${RENDER_MODE:-}",
  "rviz": "${RVIZ:-}",
  "wait_sec": "${WAIT_SEC}"
}
JSON

echo "Visual screenshot captured: ${OUTPUT_PATH}"
