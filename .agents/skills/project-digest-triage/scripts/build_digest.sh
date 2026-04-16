#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-automation_outputs/project_digest}"
TASKS_JSON="${2:-}"
SCENARIOS_JSON="${3:-}"

choose_python() {
  local candidate
  for candidate in "${PYTHON:-}" python3.12 python3.11 python3 python; do
    [[ -n "$candidate" ]] || continue
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  echo "Python 3.11+ is required for simctl automation." >&2
  return 1
}

PYTHON_BIN="$(choose_python)"

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -e .

mkdir -p "$OUT_DIR"

if [[ -n "$TASKS_JSON" && -n "$SCENARIOS_JSON" ]]; then
  "$PYTHON_BIN" -m simctl digest --config ops/project_automation.yaml --tasks-json "$TASKS_JSON" --scenarios-json "$SCENARIOS_JSON" --output-dir "$OUT_DIR"
else
  if [[ -n "${GH_PROJECT_TOKEN:-}" && -z "${GH_TOKEN:-}" ]]; then
    export GH_TOKEN="$GH_PROJECT_TOKEN"
  fi
  if [[ -n "${GITHUB_TOKEN:-}" && -z "${GH_TOKEN:-}" ]]; then
    export GH_TOKEN="$GITHUB_TOKEN"
  fi
  "$PYTHON_BIN" -m simctl digest --config ops/project_automation.yaml --output-dir "$OUT_DIR"
fi

echo "project-digest-triage completed"
echo "OUT_DIR=$OUT_DIR"
