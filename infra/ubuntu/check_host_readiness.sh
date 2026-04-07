#!/usr/bin/env bash
set -euo pipefail

STRICT=0
if [[ "${1:-}" == "--strict" ]]; then
  STRICT=1
fi

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
  if ldconfig -p | grep -q libnvinfer; then
    pass "TensorRT runtime libraries registered"
  else
    warn "TensorRT runtime libraries missing"
  fi
else
  warn "nvidia-smi missing; GPU checks unavailable"
fi

if sudo dpkg --audit | grep -q .; then
  fail "dpkg audit reports broken packages"
else
  pass "dpkg audit clean"
fi

if [[ -n "${CONDA_PREFIX:-}" ]]; then
  warn "Conda environment active: ${CONDA_PREFIX}"
fi

if command -v ros2 >/dev/null 2>&1; then
  pass "ros2 available: $(command -v ros2)"
  if ros2 --help >/dev/null 2>&1; then
    pass "ROS 2 CLI responds"
  else
    fail "ROS 2 CLI found but not responding correctly"
  fi
else
  fail "ros2 missing"
fi

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

if [[ "$STRICT" -eq 1 && "$FAILURES" -gt 0 ]]; then
  echo "Readiness check failed with ${FAILURES} hard failure(s)"
  exit 1
fi

echo "Readiness check completed with ${FAILURES} hard failure(s)"
