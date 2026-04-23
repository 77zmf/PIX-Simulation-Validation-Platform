#!/usr/bin/env bash
set -euo pipefail

STRICT=0
VISUAL=0
SUMO=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict) STRICT=1; shift ;;
    --visual) VISUAL=1; shift ;;
    --sumo) SUMO=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

FAILURES=0

pass() {
  echo "[PASS] $1"
}

warn() {
  echo "[WARN] $1"
}

fail() {
  echo "[FAIL] $1"
  FAILURES=$((FAILURES + 1))
}

check_cmd() {
  local name="$1"
  local cmd="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$name available: $(command -v "$cmd")"
  else
    fail "$name missing"
  fi
}

check_optional_cmd() {
  local name="$1"
  local cmd="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$name available: $(command -v "$cmd")"
  else
    warn "$name missing"
  fi
}

check_ros2_cli() {
  if command -v ros2 >/dev/null 2>&1; then
    pass "ros2 available: $(command -v ros2)"
    if ros2 --help >/dev/null 2>&1; then
      pass "ROS 2 CLI responds"
    else
      fail "ROS 2 CLI found but not responding correctly"
    fi
    return
  fi

  if [[ -f /opt/ros/humble/setup.bash ]] && bash -lc "source /opt/ros/humble/setup.bash >/dev/null 2>&1 && command -v ros2 >/dev/null 2>&1 && ros2 --help >/dev/null 2>&1"; then
    pass "ros2 available after sourcing /opt/ros/humble/setup.bash"
    pass "ROS 2 CLI responds"
    return
  fi

  fail "ros2 missing"
}

echo "Checking company Ubuntu host readiness for Autoware + CARLA stable stack"

if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  if [[ "${ID:-}" == "ubuntu" ]]; then
    pass "Ubuntu detected: ${PRETTY_NAME:-unknown}"
  else
    fail "Host OS is not Ubuntu: ${PRETTY_NAME:-unknown}"
  fi
else
  fail "Cannot detect OS from /etc/os-release"
fi

check_cmd "git" git
check_cmd "python3" python3
check_cmd "pip" pip3
check_cmd "colcon" colcon
check_cmd "rosdep" rosdep
check_cmd "vcs" vcs

if command -v nvidia-smi >/dev/null 2>&1; then
  pass "nvidia-smi available"
  if command -v nvcc >/dev/null 2>&1; then
    pass "nvcc available: $(command -v nvcc)"
  else
    warn "nvcc missing; CUDA toolkit is not ready"
  fi
  LDCONFIG_CACHE="$(ldconfig -p 2>/dev/null || true)"
  if grep -q 'libnvinfer' <<<"$LDCONFIG_CACHE"; then
    pass "TensorRT runtime libraries registered"
  else
    warn "TensorRT runtime libraries missing"
  fi
else
  warn "nvidia-smi missing; GPU checks unavailable"
fi

if dpkg --audit | grep -q .; then
  fail "dpkg audit reports broken packages"
else
  pass "dpkg audit clean"
fi

if [[ -n "${CONDA_PREFIX:-}" ]]; then
  warn "Conda environment active: ${CONDA_PREFIX}"
fi

check_ros2_cli

AUTOWARE_WS="${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/autoware}"
if [[ -d "$AUTOWARE_WS" ]]; then
  pass "AUTOWARE_WS exists: $AUTOWARE_WS"
  if [[ -d "$AUTOWARE_WS/src" ]]; then
    pass "Autoware src directory present"
  else
    warn "Autoware workspace exists but src directory is missing"
  fi
  if [[ -f "$AUTOWARE_WS/install/setup.bash" ]]; then
    pass "Autoware install/setup.bash present"
  else
    warn "Autoware workspace exists but install/setup.bash is missing"
  fi
else
  warn "AUTOWARE_WS not found: $AUTOWARE_WS"
fi

CARLA_ROOT="${CARLA_0915_ROOT:-$HOME/CARLA_0.9.15}"
if [[ -d "$CARLA_ROOT" ]]; then
  pass "CARLA_0915_ROOT exists: $CARLA_ROOT"
  if [[ -x "$CARLA_ROOT/CarlaUE4.sh" ]]; then
    pass "CarlaUE4.sh found"
  else
    warn "CARLA runtime root exists but CarlaUE4.sh is missing"
  fi
else
  warn "CARLA_0915_ROOT not found: $CARLA_ROOT"
fi

if [[ -n "${DISPLAY:-}" ]]; then
  pass "DISPLAY is set: $DISPLAY"
else
  warn "DISPLAY is not set; offscreen mode is expected"
fi

if [[ "$VISUAL" -eq 1 ]]; then
  echo
  echo "Checking optional visual validation tools"
  check_cmd "ffmpeg" ffmpeg
  check_optional_cmd "xwd" xwd
  check_optional_cmd "xprop" xprop
  check_optional_cmd "xwininfo" xwininfo
  check_optional_cmd "wmctrl" wmctrl
  check_optional_cmd "xdotool" xdotool
  check_optional_cmd "gnome-screenshot" gnome-screenshot
  check_optional_cmd "scrot" scrot
  check_optional_cmd "ImageMagick import" import
  check_optional_cmd "glxinfo" glxinfo

  if [[ -n "${DISPLAY:-}" ]]; then
    pass "visual DISPLAY target is available from current shell"
  else
    warn "For NoMachine visual runs over SSH, export DISPLAY=:0 and XAUTHORITY=/run/user/$(id -u)/gdm/Xauthority if present."
  fi
fi

if [[ "$SUMO" -eq 1 ]]; then
  echo
  echo "Checking optional SUMO co-simulation tools"
  check_cmd "sumo" sumo
  check_cmd "netconvert" netconvert
  if [[ -n "${SUMO_HOME:-}" && -d "${SUMO_HOME}" ]]; then
    pass "SUMO_HOME exists: ${SUMO_HOME}"
  elif [[ -d /usr/share/sumo ]]; then
    pass "SUMO_HOME candidate exists: /usr/share/sumo"
  else
    fail "SUMO_HOME missing"
  fi
  CARLA_COSIM_SCRIPT="${CARLA_ROOT}/Co-Simulation/Sumo/run_synchronization.py"
  if [[ -f "${CARLA_COSIM_SCRIPT}" ]]; then
    pass "CARLA SUMO co-sim script found: ${CARLA_COSIM_SCRIPT}"
  else
    fail "CARLA SUMO co-sim script missing: ${CARLA_COSIM_SCRIPT}"
  fi
fi

if [[ "$STRICT" -eq 1 && "$FAILURES" -gt 0 ]]; then
  echo "Readiness check failed with ${FAILURES} hard failure(s)"
  exit 1
fi

echo "Readiness check completed with ${FAILURES} hard failure(s)"
