#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-automation_outputs/runtime_audit}"
RUN_ROOT="$OUT_DIR/runs"
mkdir -p "$OUT_DIR"
rm -rf "$RUN_ROOT"
mkdir -p "$RUN_ROOT"

choose_python() {
  local candidate
  for candidate in "${PYTHON:-}" python3.9 python3 python3.10 python3.11 python3.12 python; do
    [[ -n "$candidate" ]] || continue
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  echo "Python 3.9+ is required for simctl automation." >&2
  return 1
}

PYTHON_BIN="$(choose_python)"

ensure_python_deps() {
  if "$PYTHON_BIN" -c 'import yaml' >/dev/null 2>&1; then
    return 0
  fi
  "$PYTHON_BIN" -m pip install --user "PyYAML>=6.0"
}

ensure_python_deps
export PYTHONPATH=src
"$PYTHON_BIN" -m simctl bootstrap --stack stable
"$PYTHON_BIN" -m simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root "$RUN_ROOT"
LATEST_RUN_RESULT="$("$PYTHON_BIN" - "$RUN_ROOT" <<'PY'
from pathlib import Path
import sys

run_root = Path(sys.argv[1])
matches = sorted(run_root.rglob("run_result.json"), key=lambda path: path.stat().st_mtime)
if not matches:
    raise SystemExit("no run_result.json found after simctl run")
print(matches[-1])
PY
)"
LATEST_RUN_DIR="$(dirname "$LATEST_RUN_RESULT")"
"$PYTHON_BIN" tools/codex/write_stub_metric_probe.py --run-dir "$LATEST_RUN_DIR"
"$PYTHON_BIN" -m simctl finalize --run-dir "$LATEST_RUN_DIR"
"$PYTHON_BIN" -m simctl report --run-root "$RUN_ROOT"
"$PYTHON_BIN" tools/codex/summarize_run_artifacts.py --run-root "$RUN_ROOT" --output "$OUT_DIR/runtime_audit_summary.json"

echo "runtime-closure-audit completed"
echo "OUT_DIR=$OUT_DIR"
