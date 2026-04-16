#!/usr/bin/env bash
set -euo pipefail

RUN_ROOT="${1:-ci_runs}"
DIGEST_OUT="${2:-ci_digest}"

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

export PYTHONPATH=src
"$PYTHON_BIN" -m unittest discover -s tests -v
"$PYTHON_BIN" -m simctl bootstrap --stack stable
"$PYTHON_BIN" -m simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root "$RUN_ROOT"
"$PYTHON_BIN" -m simctl report --run-root "$RUN_ROOT"
"$PYTHON_BIN" -m simctl digest --config ops/project_automation.yaml --tasks-json tests/fixtures/project_tasks.json --scenarios-json tests/fixtures/project_scenarios.json --output-dir "$DIGEST_OUT"

echo "repo-verification completed"
echo "RUN_ROOT=$RUN_ROOT"
echo "DIGEST_OUT=$DIGEST_OUT"
