#!/usr/bin/env bash
set -euo pipefail

RUN_DIR=""
CARLA_ROOT_ARG=""
CARLA_PORT=""
TRAFFIC_MANAGER_PORT=""
SUMO_ENABLED=""
SUMO_HOME_ARG=""
SUMO_CONFIG_FILE=""
SUMO_NET_FILE=""
SUMO_ROUTE_FILE=""
SUMO_HOST=""
SUMO_TRACI_PORT=""
SUMO_BINARY=""
SUMO_GUI=""
SUMO_STEP_LENGTH=""
SUMO_SYNC_VEHICLE_LIGHTS=""
SUMO_SYNC_VEHICLE_COLOR=""
SUMO_TLS_MANAGER=""
SUMO_ADDITIONAL_ARGS=""
SUMO_COSIM_SCRIPT_ARG=""
CPU_AFFINITY=""
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --carla-root) CARLA_ROOT_ARG="$2"; shift 2 ;;
    --carla-port) CARLA_PORT="$2"; shift 2 ;;
    --traffic-manager-port) TRAFFIC_MANAGER_PORT="$2"; shift 2 ;;
    --sumo-enabled) SUMO_ENABLED="$2"; shift 2 ;;
    --sumo-home) SUMO_HOME_ARG="$2"; shift 2 ;;
    --sumo-config-file) SUMO_CONFIG_FILE="$2"; shift 2 ;;
    --sumo-net-file) SUMO_NET_FILE="$2"; shift 2 ;;
    --sumo-route-file) SUMO_ROUTE_FILE="$2"; shift 2 ;;
    --sumo-host) SUMO_HOST="$2"; shift 2 ;;
    --sumo-traci-port) SUMO_TRACI_PORT="$2"; shift 2 ;;
    --sumo-binary) SUMO_BINARY="$2"; shift 2 ;;
    --sumo-gui) SUMO_GUI="$2"; shift 2 ;;
    --sumo-step-length) SUMO_STEP_LENGTH="$2"; shift 2 ;;
    --sumo-sync-vehicle-lights) SUMO_SYNC_VEHICLE_LIGHTS="$2"; shift 2 ;;
    --sumo-sync-vehicle-color) SUMO_SYNC_VEHICLE_COLOR="$2"; shift 2 ;;
    --sumo-tls-manager) SUMO_TLS_MANAGER="$2"; shift 2 ;;
    --sumo-additional-args) SUMO_ADDITIONAL_ARGS="$2"; shift 2 ;;
    --sumo-cosim-script) SUMO_COSIM_SCRIPT_ARG="$2"; shift 2 ;;
    --cpu-affinity) CPU_AFFINITY="$2"; shift 2 ;;
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

shell_quote() {
  printf "%q" "$1"
}

CARLA_ROOT="${CARLA_ROOT_ARG:-${CARLA_0915_ROOT:-$HOME/CARLA_0.9.15}}"
CARLA_PORT="${CARLA_PORT:-2000}"
TRAFFIC_MANAGER_PORT="${TRAFFIC_MANAGER_PORT:-8000}"
SUMO_ENABLED="${SUMO_ENABLED:-${SIMCTL_SUMO_ENABLED:-false}}"
SUMO_HOST="${SUMO_HOST:-${SIMCTL_SUMO_HOST:-127.0.0.1}}"
SUMO_TRACI_PORT="${SUMO_TRACI_PORT:-${SIMCTL_SUMO_TRACI_PORT:-9000}}"
SUMO_BINARY="${SUMO_BINARY:-${SIMCTL_SUMO_BINARY:-sumo}}"
SUMO_GUI="${SUMO_GUI:-${SIMCTL_SUMO_GUI:-false}}"
SUMO_STEP_LENGTH="${SUMO_STEP_LENGTH:-${SIMCTL_SUMO_STEP_LENGTH:-0.05}}"
SUMO_SYNC_VEHICLE_LIGHTS="${SUMO_SYNC_VEHICLE_LIGHTS:-${SIMCTL_SUMO_SYNC_VEHICLE_LIGHTS:-false}}"
SUMO_SYNC_VEHICLE_COLOR="${SUMO_SYNC_VEHICLE_COLOR:-${SIMCTL_SUMO_SYNC_VEHICLE_COLOR:-true}}"
SUMO_TLS_MANAGER="${SUMO_TLS_MANAGER:-${SIMCTL_SUMO_TLS_MANAGER:-none}}"
SUMO_COSIM_SCRIPT="${SUMO_COSIM_SCRIPT_ARG:-${SIMCTL_SUMO_COSIM_SCRIPT:-}}"
SUMO_HOME_VALUE="${SUMO_HOME_ARG:-${SUMO_HOME:-}}"

if [[ -z "${SUMO_HOME_VALUE}" && -d /usr/share/sumo ]]; then
  SUMO_HOME_VALUE="/usr/share/sumo"
fi

resolve_sumo_config() {
  if [[ -n "${SUMO_CONFIG_FILE}" ]]; then
    printf '%s\n' "${SUMO_CONFIG_FILE}"
    return
  fi
  local map_name="${SIMCTL_CARLA_MAP:-Town01}"
  local candidate="${CARLA_ROOT}/Co-Simulation/Sumo/examples/${map_name}.sumocfg"
  if [[ -f "${candidate}" ]]; then
    printf '%s\n' "${candidate}"
    return
  fi
  candidate="${CARLA_ROOT}/Co-Simulation/Sumo/examples/Town01.sumocfg"
  if [[ -f "${candidate}" ]]; then
    printf '%s\n' "${candidate}"
    return
  fi
  candidate="${CARLA_ROOT}/Co-Simulation/Sumo/examples/${map_name}/${map_name}.sumocfg"
  if [[ -f "${candidate}" ]]; then
    printf '%s\n' "${candidate}"
    return
  fi
  candidate="${CARLA_ROOT}/Co-Simulation/Sumo/examples/Town01/Town01.sumocfg"
  printf '%s\n' "${candidate}"
}

resolve_cosim_script() {
  if [[ -n "${SUMO_COSIM_SCRIPT}" ]]; then
    printf '%s\n' "${SUMO_COSIM_SCRIPT}"
    return
  fi
  local candidate="${CARLA_ROOT}/Co-Simulation/Sumo/run_synchronization.py"
  if [[ -f "${candidate}" ]]; then
    printf '%s\n' "${candidate}"
    return
  fi
  candidate="${CARLA_ROOT}/PythonAPI/examples/sumo/run_synchronization.py"
  printf '%s\n' "${candidate}"
}

SUMO_CONFIG_FILE="$(resolve_sumo_config)"
SUMO_COSIM_SCRIPT="$(resolve_cosim_script)"
PYTHONPATH_ENTRIES=(
  "${CARLA_ROOT}/PythonAPI/carla/dist/carla-0.9.15-py3.10-linux-x86_64.egg"
  "${CARLA_ROOT}/PythonAPI/carla"
  "$(dirname "${SUMO_COSIM_SCRIPT}")"
)
if [[ -n "${SUMO_HOME_VALUE}" ]]; then
  PYTHONPATH_ENTRIES+=("${SUMO_HOME_VALUE}/tools")
fi

CMD=("python3" "${SUMO_COSIM_SCRIPT}" "${SUMO_CONFIG_FILE}" "--sumo-host" "${SUMO_HOST}" "--sumo-port" "${SUMO_TRACI_PORT}" "--carla-host" "127.0.0.1" "--carla-port" "${CARLA_PORT}" "--step-length" "${SUMO_STEP_LENGTH}" "--tls-manager" "${SUMO_TLS_MANAGER}")
if truthy "${SUMO_GUI}"; then
  CMD+=("--sumo-gui")
fi
if truthy "${SUMO_SYNC_VEHICLE_LIGHTS}"; then
  CMD+=("--sync-vehicle-lights")
fi
if truthy "${SUMO_SYNC_VEHICLE_COLOR}"; then
  CMD+=("--sync-vehicle-color")
fi
if [[ -n "${SUMO_ADDITIONAL_ARGS}" ]]; then
  # shellcheck disable=SC2206
  EXTRA_ARG_ARRAY=(${SUMO_ADDITIONAL_ARGS})
  CMD+=("${EXTRA_ARG_ARRAY[@]}")
fi

CMD_DISPLAY=""
for cmd_part in "${CMD[@]}"; do
  CMD_DISPLAY+=" $(shell_quote "${cmd_part}")"
done
CMD_DISPLAY="${CMD_DISPLAY# }"

echo "RunDir: ${RUN_DIR}"
echo "CARLA root: ${CARLA_ROOT}"
echo "CARLA RPC Port: ${CARLA_PORT}"
echo "Traffic Manager Port: ${TRAFFIC_MANAGER_PORT}"
echo "SUMO enabled: ${SUMO_ENABLED}"
echo "SUMO_HOME: ${SUMO_HOME_VALUE}"
echo "SUMO binary: ${SUMO_BINARY}"
echo "SUMO GUI: ${SUMO_GUI}"
echo "SUMO config file: ${SUMO_CONFIG_FILE}"
echo "SUMO net file: ${SUMO_NET_FILE}"
echo "SUMO route file: ${SUMO_ROUTE_FILE}"
echo "SUMO host: ${SUMO_HOST}"
echo "SUMO TraCI port: ${SUMO_TRACI_PORT}"
echo "SUMO step length: ${SUMO_STEP_LENGTH}"
echo "SUMO sync vehicle lights: ${SUMO_SYNC_VEHICLE_LIGHTS}"
echo "SUMO sync vehicle color: ${SUMO_SYNC_VEHICLE_COLOR}"
echo "SUMO TLS manager: ${SUMO_TLS_MANAGER}"
echo "SUMO co-sim script: ${SUMO_COSIM_SCRIPT}"
echo "CPU Affinity: ${CPU_AFFINITY}"
echo "Command: ${CMD_DISPLAY}"

if ! truthy "${SUMO_ENABLED}"; then
  echo "SUMO co-simulation disabled; set scenario stable_runtime.sumo_enabled=true to enable."
  exit 0
fi

if [[ "${EXECUTE}" -ne 1 ]]; then
  exit 0
fi

if [[ ! -f "${SUMO_COSIM_SCRIPT}" ]]; then
  echo "CARLA SUMO co-simulation script not found at ${SUMO_COSIM_SCRIPT}" >&2
  exit 1
fi
if [[ ! -f "${SUMO_CONFIG_FILE}" ]]; then
  echo "SUMO config file not found at ${SUMO_CONFIG_FILE}" >&2
  echo "Provide stable_runtime.sumo_config_file or install CARLA Co-Simulation/Sumo examples." >&2
  exit 1
fi
if [[ -n "${SUMO_NET_FILE}" && ! -f "${SUMO_NET_FILE}" ]]; then
  echo "SUMO net file not found at ${SUMO_NET_FILE}" >&2
  exit 1
fi
if [[ -n "${SUMO_ROUTE_FILE}" && ! -f "${SUMO_ROUTE_FILE}" ]]; then
  echo "SUMO route file not found at ${SUMO_ROUTE_FILE}" >&2
  exit 1
fi
if ! command -v "${SUMO_BINARY}" >/dev/null 2>&1; then
  echo "SUMO binary not found: ${SUMO_BINARY}" >&2
  exit 1
fi

SUMO_CARLA_CLIENT_TIMEOUT_SEC="${SIMCTL_SUMO_CARLA_CLIENT_TIMEOUT_SEC:-20.0}"
if ! [[ "${SUMO_CARLA_CLIENT_TIMEOUT_SEC}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "Invalid SIMCTL_SUMO_CARLA_CLIENT_TIMEOUT_SEC: ${SUMO_CARLA_CLIENT_TIMEOUT_SEC}" >&2
  exit 1
fi

if [[ -n "${RUN_DIR}" ]]; then
  SUMO_COSIM_SOURCE_DIR="$(dirname "${SUMO_COSIM_SCRIPT}")"
  SUMO_COSIM_OVERLAY_DIR="${RUN_DIR}/sumo_cosim_overlay"
  rm -rf "${SUMO_COSIM_OVERLAY_DIR}"
  mkdir -p "${SUMO_COSIM_OVERLAY_DIR}"
  cp -a "${SUMO_COSIM_SOURCE_DIR}/." "${SUMO_COSIM_OVERLAY_DIR}/"
  SUMO_CARLA_SIMULATION_FILE="${SUMO_COSIM_OVERLAY_DIR}/sumo_integration/carla_simulation.py"
  if [[ -f "${SUMO_CARLA_SIMULATION_FILE}" ]]; then
    sed -i -E "s/self\\.client\\.set_timeout\\([0-9.]+\\)/self.client.set_timeout(${SUMO_CARLA_CLIENT_TIMEOUT_SEC})/" "${SUMO_CARLA_SIMULATION_FILE}"
  fi
  SUMO_BRIDGE_HELPER_FILE="${SUMO_COSIM_OVERLAY_DIR}/sumo_integration/bridge_helper.py"
  if [[ -f "${SUMO_BRIDGE_HELPER_FILE}" ]]; then
    sed -i -E "s/traci\\.vehicletype\\.setLength\\(type_id, 2\\.0 \\* extent\\.x\\)/traci.vehicletype.setLength(type_id, max(0.1, 2.0 * extent.x))/" "${SUMO_BRIDGE_HELPER_FILE}"
    sed -i -E "s/traci\\.vehicletype\\.setWidth\\(type_id, 2\\.0 \\* extent\\.y\\)/traci.vehicletype.setWidth(type_id, max(0.1, 2.0 * extent.y))/" "${SUMO_BRIDGE_HELPER_FILE}"
    sed -i -E "s/traci\\.vehicletype\\.setHeight\\(type_id, 2\\.0 \\* extent\\.z\\)/traci.vehicletype.setHeight(type_id, max(0.1, 2.0 * extent.z))/" "${SUMO_BRIDGE_HELPER_FILE}"
  fi
  SUMO_COSIM_SCRIPT="${SUMO_COSIM_OVERLAY_DIR}/$(basename "${SUMO_COSIM_SCRIPT}")"
  PYTHONPATH_ENTRIES[2]="${SUMO_COSIM_OVERLAY_DIR}"
  CMD[1]="${SUMO_COSIM_SCRIPT}"
  CMD_DISPLAY=""
  for cmd_part in "${CMD[@]}"; do
    CMD_DISPLAY+=" $(shell_quote "${cmd_part}")"
  done
  CMD_DISPLAY="${CMD_DISPLAY# }"
  echo "SUMO co-sim overlay: ${SUMO_COSIM_OVERLAY_DIR}"
  echo "SUMO CARLA client timeout seconds: ${SUMO_CARLA_CLIENT_TIMEOUT_SEC}"
  echo "Execute command: ${CMD_DISPLAY}"
fi

if [[ -n "${SUMO_HOME_VALUE}" ]]; then
  export SUMO_HOME="${SUMO_HOME_VALUE}"
fi
export SUMO_BINARY="${SUMO_BINARY}"
PYTHONPATH_JOINED="$(IFS=:; printf '%s' "${PYTHONPATH_ENTRIES[*]}")"
export PYTHONPATH="${PYTHONPATH_JOINED}:${PYTHONPATH:-}"
export SIMCTL_SUMO_TRACI_PORT="${SUMO_TRACI_PORT}"
export SIMCTL_TRAFFIC_MANAGER_PORT="${TRAFFIC_MANAGER_PORT}"

SUMO_SERVER_BINARY="${SUMO_BINARY}"
if truthy "${SUMO_GUI}" && [[ "${SUMO_SERVER_BINARY}" == "sumo" ]]; then
  SUMO_SERVER_BINARY="sumo-gui"
fi
if ! command -v "${SUMO_SERVER_BINARY}" >/dev/null 2>&1; then
  echo "SUMO server binary not found: ${SUMO_SERVER_BINARY}" >&2
  exit 1
fi

SUMO_SERVER_CMD=(
  "${SUMO_SERVER_BINARY}"
  "--configuration-file" "${SUMO_CONFIG_FILE}"
  "--step-length" "${SUMO_STEP_LENGTH}"
  "--lateral-resolution" "0.25"
  "--collision.check-junctions"
  "--remote-port" "${SUMO_TRACI_PORT}"
)

if [[ -n "${RUN_DIR}" ]]; then
  mkdir -p "${RUN_DIR}/pids"
fi

SUMO_SERVER_PID=""
cleanup_sumo_server() {
  if [[ -n "${SUMO_SERVER_PID}" ]] && kill -0 "${SUMO_SERVER_PID}" >/dev/null 2>&1; then
    kill "${SUMO_SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SUMO_SERVER_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup_sumo_server EXIT INT TERM

SUMO_SERVER_DISPLAY=""
for cmd_part in "${SUMO_SERVER_CMD[@]}"; do
  SUMO_SERVER_DISPLAY+=" $(shell_quote "${cmd_part}")"
done
SUMO_SERVER_DISPLAY="${SUMO_SERVER_DISPLAY# }"
echo "SUMO server command: ${SUMO_SERVER_DISPLAY}"

if [[ -n "${CPU_AFFINITY}" ]]; then
  taskset -c "${CPU_AFFINITY}" "${SUMO_SERVER_CMD[@]}" &
else
  "${SUMO_SERVER_CMD[@]}" &
fi
SUMO_SERVER_PID="$!"
if [[ -n "${RUN_DIR}" ]]; then
  printf '%s\n' "${SUMO_SERVER_PID}" > "${RUN_DIR}/pids/sumo-server.pid"
fi

SUMO_PORT_READY=0
for _ in $(seq 1 30); do
  if ! kill -0 "${SUMO_SERVER_PID}" >/dev/null 2>&1; then
    echo "SUMO server exited before TraCI port ${SUMO_TRACI_PORT} became ready" >&2
    wait "${SUMO_SERVER_PID}" || true
    exit 1
  fi
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(:|\\.)${SUMO_TRACI_PORT}$"; then
    SUMO_PORT_READY=1
    break
  fi
  sleep 1
done
if [[ "${SUMO_PORT_READY}" -ne 1 ]]; then
  echo "Timed out waiting for SUMO TraCI port ${SUMO_TRACI_PORT}" >&2
  exit 1
fi
echo "SUMO TraCI port ready: ${SUMO_HOST}:${SUMO_TRACI_PORT}"

if [[ -n "${CPU_AFFINITY}" ]]; then
  taskset -c "${CPU_AFFINITY}" "${CMD[@]}"
else
  "${CMD[@]}"
fi
