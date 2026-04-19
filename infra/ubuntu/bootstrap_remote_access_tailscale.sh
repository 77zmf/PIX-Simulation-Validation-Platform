#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash infra/ubuntu/bootstrap_remote_access_tailscale.sh --execute [--tailscale-hostname NAME]
  TAILSCALE_AUTH_KEY=tskey-xxxxx bash infra/ubuntu/bootstrap_remote_access_tailscale.sh --execute

What it does:
  1. installs the current Ubuntu host prerequisites through infra/ubuntu/bootstrap_host.sh
  2. installs and enables OpenSSH server
  3. installs uv if needed, then creates a Python 3.11 repo virtualenv
  4. installs and enables Tailscale
  5. brings the host onto your tailnet
  6. runs infra/ubuntu/preflight_and_next_steps.sh

Notes:
  - default mode is dry-run; add --execute to actually apply changes
  - pass TAILSCALE_AUTH_KEY (or --tailscale-auth-key) for unattended login
  - if no auth key is provided, the script will run 'sudo tailscale up' and print the interactive login URL
EOF
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXECUTE=0
RUN_PREFLIGHT=1
TAILSCALE_AUTH_KEY="${TAILSCALE_AUTH_KEY:-${TS_AUTHKEY:-}}"
TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-}"
TAILSCALE_OPERATOR="${TAILSCALE_OPERATOR:-${USER}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -Execute|--execute)
      EXECUTE=1
      ;;
    --tailscale-auth-key)
      shift
      if [[ $# -eq 0 ]]; then
        echo "[FAIL] --tailscale-auth-key requires a value" >&2
        exit 1
      fi
      TAILSCALE_AUTH_KEY="$1"
      ;;
    --tailscale-hostname)
      shift
      if [[ $# -eq 0 ]]; then
        echo "[FAIL] --tailscale-hostname requires a value" >&2
        exit 1
      fi
      TAILSCALE_HOSTNAME="$1"
      ;;
    --skip-preflight)
      RUN_PREFLIGHT=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[FAIL] Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

run() {
  local cmd="$1"
  echo "$cmd"
  if [[ "$EXECUTE" -eq 1 ]]; then
    bash -lc "$cmd"
  fi
}

echo "Repo root: ${REPO_ROOT}"
echo "EXECUTE=${EXECUTE}"
echo "RUN_PREFLIGHT=${RUN_PREFLIGHT}"
echo "TAILSCALE_HOSTNAME=${TAILSCALE_HOSTNAME:-<default>}"
echo "TAILSCALE_OPERATOR=${TAILSCALE_OPERATOR}"
if [[ -n "$TAILSCALE_AUTH_KEY" ]]; then
  echo "TAILSCALE_AUTH_KEY=<provided>"
else
  echo "TAILSCALE_AUTH_KEY=<interactive login>"
fi
echo

if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  if [[ "${ID:-}" == "ubuntu" ]]; then
    echo "[PASS] Ubuntu detected: ${PRETTY_NAME:-unknown}"
  else
    echo "[WARN] Host OS is not Ubuntu: ${PRETTY_NAME:-unknown}"
  fi
else
  echo "[WARN] Cannot detect OS from /etc/os-release"
fi

echo
echo "== Host prerequisites =="
run "bash '${REPO_ROOT}/infra/ubuntu/bootstrap_host.sh' --execute"
run "sudo apt-get install -y openssh-server"
run "sudo systemctl enable --now ssh"
run "sudo systemctl --no-pager --full status ssh | sed -n '1,12p'"

echo
echo "== Python 3.11 repo environment =="
run "if ! command -v uv >/dev/null 2>&1 && [[ ! -x \"\$HOME/.local/bin/uv\" ]]; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi"
run "export PATH=\"\$HOME/.local/bin:\$PATH\" && uv python install 3.11"
run "export PATH=\"\$HOME/.local/bin:\$PATH\" && uv venv --python 3.11 '${REPO_ROOT}/.venv'"
run "source '${REPO_ROOT}/.venv/bin/activate' && python -m ensurepip --upgrade && python -m pip install --upgrade pip && python -m pip install -e '${REPO_ROOT}'"

echo
echo "== Tailscale remote access =="
run "curl -fsSL https://tailscale.com/install.sh | sh"
run "sudo systemctl enable --now tailscaled"
run "sudo tailscale set --operator '${TAILSCALE_OPERATOR}'"

TAILSCALE_UP_CMD="sudo tailscale up --operator '${TAILSCALE_OPERATOR}'"
if [[ -n "$TAILSCALE_HOSTNAME" ]]; then
  TAILSCALE_UP_CMD+=" --hostname '${TAILSCALE_HOSTNAME}'"
fi
if [[ -n "$TAILSCALE_AUTH_KEY" ]]; then
  TAILSCALE_UP_CMD+=" --auth-key '${TAILSCALE_AUTH_KEY}'"
fi
run "$TAILSCALE_UP_CMD"
run "tailscale status || true"
run "tailscale ip -4 || true"

if [[ "$RUN_PREFLIGHT" -eq 1 ]]; then
  echo
  echo "== Repo preflight =="
  run "bash '${REPO_ROOT}/infra/ubuntu/preflight_and_next_steps.sh'"
fi

echo
echo "== Next steps =="
echo "1. If Tailscale login was interactive, finish the browser/device-code login when prompted."
echo "2. Extract CARLA 0.9.15 to \${CARLA_0915_ROOT:-\$HOME/CARLA_0.9.15} if it is not there yet."
echo "3. Continue with:"
echo "   bash '${REPO_ROOT}/infra/ubuntu/check_host_readiness.sh'"
echo "   source '${REPO_ROOT}/.venv/bin/activate'"
echo "   simctl bootstrap --stack stable"
echo "4. From your Mac, once Tailscale reports an IPv4 address on the Ubuntu host:"
echo "   ssh ${USER}@<tailscale-ip>"
