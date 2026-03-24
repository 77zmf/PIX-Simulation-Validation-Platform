#!/usr/bin/env bash
set -euo pipefail

EXECUTE=0
if [[ "${1:-}" == "-Execute" || "${1:-}" == "--execute" ]]; then
  EXECUTE=1
fi

AUTOWARE_PARENT="${AUTOWARE_PARENT:-$HOME/zmf_ws/projects/autoware_universe}"
AUTOWARE_WS="${AUTOWARE_WS:-$AUTOWARE_PARENT/autoware}"

echo "Autoware parent: ${AUTOWARE_PARENT}"
echo "Autoware workspace: ${AUTOWARE_WS}"
echo "EXECUTE=${EXECUTE}"

if sudo dpkg --audit | grep -q .; then
  echo "[WARN] dpkg audit is not clean. setup-dev-env.sh may fail until host package conflicts are resolved."
fi

COMMANDS=(
  "mkdir -p '${AUTOWARE_PARENT}'"
  "cd '${AUTOWARE_PARENT}' && if [[ ! -d '${AUTOWARE_WS}' ]]; then git clone https://github.com/autowarefoundation/autoware.git; fi"
  "cd '${AUTOWARE_WS}' && mkdir -p src"
  "cd '${AUTOWARE_WS}' && vcs import src < repositories/autoware.repos"
)

for cmd in "${COMMANDS[@]}"; do
  echo "$cmd"
  if [[ "$EXECUTE" -eq 1 ]]; then
    bash -lc "$cmd"
  fi
done

echo
echo "Known issue from the previous server baseline:"
echo "- setup-dev-env.sh may fail if host dpkg/DKMS state is dirty (for example agnocast-related conflicts)"
echo
echo "Recommended next commands once package state is clean:"
echo "cd '${AUTOWARE_WS}'"
echo "./setup-dev-env.sh"
echo "rosdep install --from-paths src --ignore-src -r -y"
echo "colcon build --symlink-install"
