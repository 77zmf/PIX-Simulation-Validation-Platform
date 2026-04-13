#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CARLA_RUNTIME_ROOT="${CARLA_0915_ROOT:-$HOME/CARLA_0.9.15}"
AUTOWARE_PARENT="${AUTOWARE_PARENT:-$HOME/zmf_ws/projects/autoware_universe}"
AUTOWARE_WS="${AUTOWARE_WS:-$AUTOWARE_PARENT/autoware}"
FIX_SCRIPT_PATH=""

if [[ "${1:-}" == "--write-fix-script" ]]; then
  FIX_SCRIPT_PATH="${2:-}"
  if [[ -z "$FIX_SCRIPT_PATH" ]]; then
    echo "[FAIL] --write-fix-script requires an output path" >&2
    exit 1
  fi
fi

declare -a BLOCKERS=()
declare -a NEXT_STEPS=()
declare -a NOTES=()
declare -a BUSY_PORTS=()

pass() {
  echo "[PASS] $1"
}

warn() {
  echo "[WARN] $1"
}

fail() {
  echo "[FAIL] $1"
}

add_blocker() {
  BLOCKERS+=("$1")
}

add_step() {
  local step="$1"
  for existing in "${NEXT_STEPS[@]}"; do
    if [[ "$existing" == "$step" ]]; then
      return
    fi
  done
  NEXT_STEPS+=("$step")
}

add_note() {
  NOTES+=("$1")
}

check_cmd() {
  local name="$1"
  local cmd="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$name available: $(command -v "$cmd")"
    return 0
  fi
  fail "$name missing"
  return 1
}

check_port() {
  local port="$1"
  if ss -ltn | awk '{print $4}' | grep -E "[:.]${port}$" >/dev/null 2>&1; then
    BUSY_PORTS+=("$port")
  fi
}

echo "== PIX Simulation Validation Platform / Ubuntu Host Preflight =="
echo "Repo root: ${REPO_ROOT}"
echo "Autoware workspace: ${AUTOWARE_WS}"
echo "CARLA runtime root: ${CARLA_RUNTIME_ROOT}"
echo

if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  if [[ "${ID:-}" == "ubuntu" ]]; then
    pass "Ubuntu detected: ${PRETTY_NAME:-unknown}"
  else
    fail "Host OS is not Ubuntu: ${PRETTY_NAME:-unknown}"
    add_blocker "Switch to the company Ubuntu 22.04 host before proceeding."
  fi
else
  fail "Cannot detect OS from /etc/os-release"
  add_blocker "Use the target Ubuntu host; OS metadata is missing."
fi

check_cmd "git" git || add_step "bash '${REPO_ROOT}/infra/ubuntu/bootstrap_host.sh' --execute"
check_cmd "python3" python3 || add_step "bash '${REPO_ROOT}/infra/ubuntu/bootstrap_host.sh' --execute"
check_cmd "pip3" pip3 || add_step "bash '${REPO_ROOT}/infra/ubuntu/bootstrap_host.sh' --execute"
check_cmd "colcon" colcon || add_step "bash '${REPO_ROOT}/infra/ubuntu/bootstrap_host.sh' --execute"
check_cmd "rosdep" rosdep || add_step "bash '${REPO_ROOT}/infra/ubuntu/bootstrap_host.sh' --execute"
check_cmd "vcs" vcs || add_step "bash '${REPO_ROOT}/infra/ubuntu/bootstrap_host.sh' --execute"

if command -v ros2 >/dev/null 2>&1; then
  if ros2 --help >/dev/null 2>&1; then
    pass "ROS 2 CLI responds"
  else
    fail "ROS 2 CLI found but not responding correctly"
    add_step "bash '${REPO_ROOT}/infra/ubuntu/bootstrap_host.sh' --execute"
  fi
else
  fail "ros2 missing"
  add_step "bash '${REPO_ROOT}/infra/ubuntu/bootstrap_host.sh' --execute"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  pass "nvidia-smi available"
  if command -v nvcc >/dev/null 2>&1; then
    pass "nvcc available: $(command -v nvcc)"
  else
    warn "nvcc missing"
    add_step "bash '${REPO_ROOT}/infra/ubuntu/setup_cuda_tensorrt.sh' --execute"
  fi
  LDCONFIG_CACHE="$(ldconfig -p 2>/dev/null || true)"
  if grep -q 'libnvinfer' <<<"$LDCONFIG_CACHE"; then
    pass "TensorRT runtime libraries registered"
  else
    warn "TensorRT runtime libraries missing"
    add_step "bash '${REPO_ROOT}/infra/ubuntu/setup_cuda_tensorrt.sh' --execute"
  fi
else
  warn "nvidia-smi missing; GPU checks unavailable"
  add_note "If this host should use NVIDIA GPU, verify the driver before running CARLA."
fi

if dpkg --audit | grep -q .; then
  fail "dpkg audit reports broken packages"
  add_blocker "Resolve package conflicts first: dpkg --audit"
else
  pass "dpkg audit clean"
fi

if [[ -n "${CONDA_PREFIX:-}" ]]; then
  warn "Conda environment active: ${CONDA_PREFIX}"
  add_note "Deactivate conda before Autoware bring-up if setup-dev-env.sh starts failing."
fi

if [[ -d "$CARLA_RUNTIME_ROOT" ]]; then
  pass "CARLA runtime directory exists"
  if [[ -x "$CARLA_RUNTIME_ROOT/CarlaUE4.sh" ]]; then
    pass "CarlaUE4.sh available"
  else
    warn "CarlaUE4.sh missing under CARLA_0915_ROOT"
    add_step "bash '${REPO_ROOT}/infra/ubuntu/prepare_carla_runtime.sh'"
    add_note "Extract the official CARLA 0.9.15 Linux package into ${CARLA_RUNTIME_ROOT}."
  fi
else
  warn "CARLA runtime directory missing"
  add_step "bash '${REPO_ROOT}/infra/ubuntu/prepare_carla_runtime.sh'"
  add_note "Extract the official CARLA 0.9.15 Linux package into ${CARLA_RUNTIME_ROOT}."
fi

if [[ -d "$AUTOWARE_WS" ]]; then
  pass "AUTOWARE_WS exists"
  if [[ -d "$AUTOWARE_WS/src" ]]; then
    pass "Autoware src directory present"
  else
    warn "Autoware workspace exists but src directory is missing"
    add_step "bash '${REPO_ROOT}/infra/ubuntu/prepare_autoware_workspace.sh' --execute"
  fi
  if [[ -f "$AUTOWARE_WS/install/setup.bash" ]]; then
    pass "Autoware install/setup.bash present"
  else
    warn "Autoware workspace exists but install/setup.bash is missing"
    add_step "cd '${AUTOWARE_WS}' && ./setup-dev-env.sh && rosdep install --from-paths src --ignore-src -r -y && colcon build --symlink-install"
  fi
else
  warn "AUTOWARE_WS missing"
  add_step "bash '${REPO_ROOT}/infra/ubuntu/prepare_autoware_workspace.sh' --execute"
  add_step "cd '${AUTOWARE_WS}' && ./setup-dev-env.sh && rosdep install --from-paths src --ignore-src -r -y && colcon build --symlink-install"
fi

if [[ -d "${REPO_ROOT}/.venv" ]]; then
  pass "Repo virtual environment exists"
else
  warn "Repo virtual environment missing"
  add_step "cd '${REPO_ROOT}' && python3 -m venv .venv && source .venv/bin/activate && python -m pip install -e ."
fi

for port in 2000 2010 2020 2030 8000 8010 8020 8030; do
  check_port "$port"
done

if [[ "${#BUSY_PORTS[@]}" -eq 0 ]]; then
  pass "Stable slot default ports are free"
else
  warn "Some default slot ports are busy: ${BUSY_PORTS[*]}"
  add_note "Inspect busy ports: ss -ltnp | egrep '2000|2010|2020|2030|8000|8010|8020|8030'"
fi

echo
echo "== Next-step summary =="
if [[ "${#BLOCKERS[@]}" -gt 0 ]]; then
  echo "Blockers to clear first:"
  for blocker in "${BLOCKERS[@]}"; do
    echo "  - ${blocker}"
  done
fi

if [[ "${#NEXT_STEPS[@]}" -gt 0 ]]; then
  echo "Suggested commands:"
  step_index=1
  for step in "${NEXT_STEPS[@]}"; do
    echo "  ${step_index}. ${step}"
    step_index=$((step_index + 1))
  done
else
  echo "No missing prerequisites detected."
fi

if [[ "${#NOTES[@]}" -gt 0 ]]; then
  echo "Notes:"
  for note in "${NOTES[@]}"; do
    echo "  - ${note}"
  done
fi

echo
echo "Recommended validation sequence:"
echo "  1. bash '${REPO_ROOT}/infra/ubuntu/check_host_readiness.sh'"
echo "  2. simctl bootstrap --stack stable"
echo "  3. simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --mock-result passed"
echo "  4. simctl batch --scenario-dir scenarios/l1 --run-root runs --parallel 2 --execute"
echo

if [[ -n "$FIX_SCRIPT_PATH" ]]; then
  cat >"$FIX_SCRIPT_PATH" <<EOF
#!/usr/bin/env bash
set -euo pipefail

# Generated by preflight_and_next_steps.sh
EOF
  if [[ "${#BLOCKERS[@]}" -gt 0 ]]; then
    {
      echo
      echo "# Resolve blockers first:"
      for blocker in "${BLOCKERS[@]}"; do
        echo "# - ${blocker}"
      done
    } >>"$FIX_SCRIPT_PATH"
  fi
  if [[ "${#NEXT_STEPS[@]}" -gt 0 ]]; then
    {
      echo
      echo "# Suggested commands"
      for step in "${NEXT_STEPS[@]}"; do
        echo "$step"
      done
    } >>"$FIX_SCRIPT_PATH"
  fi
  chmod +x "$FIX_SCRIPT_PATH"
  echo "Fix script written to: ${FIX_SCRIPT_PATH}"
fi
