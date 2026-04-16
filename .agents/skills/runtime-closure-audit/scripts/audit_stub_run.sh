#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-automation_outputs/runtime_audit}"
RUN_ROOT="$OUT_DIR/runs"
mkdir -p "$OUT_DIR"

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
"$PYTHON_BIN" -m simctl bootstrap --stack stable
"$PYTHON_BIN" -m simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root "$RUN_ROOT"
"$PYTHON_BIN" -m simctl report --run-root "$RUN_ROOT"
"$PYTHON_BIN" tools/codex/summarize_run_artifacts.py --run-root "$RUN_ROOT" --output "$OUT_DIR/runtime_audit_summary.json"

echo "runtime-closure-audit completed"
echo "OUT_DIR=$OUT_DIR"
