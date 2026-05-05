#!/usr/bin/env bash
# Host Regression Round — 2026-05-05
# Purpose: Re-run critical stable-mainline scenarios on the company Ubuntu 22.04 host
#            to validate the robobus spawn fix and converge L1 follow-lane / speed40.
#
# Usage:
#   cd ~/Documents/zmf_ws
#   bash ops/scripts/host_regression_round_20260505.sh
#
# Red lines:
#   - Do NOT run this on Mac/Windows and report as host acceptance.
#   - Do NOT treat launch_submitted as passed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RUN_ROOT="${WS_ROOT}/runs/host_regression_$(date +%Y%m%d_%H%M%S)"
PYTHONPATH="${WS_ROOT}/src:${PYTHONPATH:-}"
export PYTHONPATH

# Slot assignment: avoid collision between long-running scenarios
SLOT_SPAWN="stable-slot-01"
SLOT_FOLLOW="stable-slot-02"
SLOT_SPEED40="stable-slot-03"
SLOT_SUMO="stable-slot-04"

# Scenario manifest: (name, scenario_path, slot, timeout_sec)
# Ordered by dependency / criticality:
#  1. Spawn stability (fast, CARLA-only, validates the fix)
#  2. Follow lane (L1 regression, longest-running)
#  3. Speed40 probe (L1 regression)
#  4. SUMO traffic smoke (reference passed case)
SCENARIOS=(
  "spawn_stability:scenarios/l2/reconstruction_qiyu_loop_robobus_spawn_stability.yaml:${SLOT_SPAWN}:300"
  "follow_lane:scenarios/l1/regression_follow_lane.yaml:${SLOT_FOLLOW}:600"
  "speed40:scenarios/l1/robobus117th_town01_speed40_probe.yaml:${SLOT_SPEED40}:600"
  "sumo_traffic:scenarios/l1/sumo_town01_traffic_smoke.yaml:${SLOT_SUMO}:600"
)

# Whether to run validate + finalize + report after each scenario
AUTO_FINALIZE="${AUTO_FINALIZE:-true}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
  printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

die() {
  log "FATAL: $*" >&2
  exit 1
}

ensure_pythonpath() {
  if [[ -z "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="${WS_ROOT}/src"
  fi
}

run_scenario() {
  local name="$1"
  local scenario_path="$2"
  local slot="$3"
  local timeout_sec="$4"

  local scenario_fullpath="${WS_ROOT}/${scenario_path}"
  local run_dir="${RUN_ROOT}/${name}"

  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log "SCENARIO: ${name}"
  log "  path:   ${scenario_path}"
  log "  slot:   ${slot}"
  log "  run:    ${run_dir}"
  log "  timeout: ${timeout_sec}s"
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  if [[ ! -f "${scenario_fullpath}" ]]; then
    log "SKIP: scenario file not found: ${scenario_fullpath}"
    return 1
  fi

  mkdir -p "${run_dir}"

  # Step 1: simctl run --execute
  log "[${name}] Step 1/3: simctl run --execute ..."
  if ! timeout "${timeout_sec}" \
       python3 -m simctl.cli run \
         --scenario "${scenario_fullpath}" \
         --run-root "${run_dir}" \
         --slot "${slot}" \
         --execute \
         >"${run_dir}/round_run.log" 2>&1; then
    log "WARN: [${name}] simctl run returned non-zero (see ${run_dir}/round_run.log)"
    # Do NOT exit; continue to next scenario so we collect partial evidence
  fi

  # Find the actual run directory created by simctl (timestamped subdir)
  local actual_run_dir
  actual_run_dir="$(find "${run_dir}" -maxdepth 1 -name '*__*' -type d | sort | tail -n 1)"
  if [[ -z "${actual_run_dir}" ]]; then
    log "WARN: [${name}] No run directory found under ${run_dir}"
    return 1
  fi

  log "[${name}] Actual run dir: ${actual_run_dir}"

  # Step 2: validate + finalize + report (if run_result exists)
  if [[ "${AUTO_FINALIZE}" == "true" ]] && [[ -f "${actual_run_dir}/run_result.json" ]]; then
    log "[${name}] Step 2/3: simctl validate --execute --finalize ..."
    timeout 120 \
      python3 -m simctl.cli validate \
        --run-dir "${actual_run_dir}" \
        --execute \
        --finalize \
        >"${actual_run_dir}/round_validate.log" 2>&1 || true

    log "[${name}] Step 3/3: simctl report ..."
    timeout 60 \
      python3 -m simctl.cli report \
        --run-dir "${actual_run_dir}" \
        >"${actual_run_dir}/round_report.log" 2>&1 || true
  else
    log "[${name}] Skipping finalize/report (AUTO_FINALIZE=${AUTO_FINALIZE} or no run_result)"
  fi

  # Extract key verdict
  local status="unknown"
  if [[ -f "${actual_run_dir}/run_result.json" ]]; then
    status="$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('status','unknown'))" "${actual_run_dir}/run_result.json" 2>/dev/null || echo unknown)"
  fi

  log "[${name}] RESULT: status=${status}"
  printf '%s\t%s\t%s\n' "${name}" "${actual_run_dir}" "${status}" >> "${RUN_ROOT}/_results.tsv"
  return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  log "WS_ROOT:  ${WS_ROOT}"
  log "RUN_ROOT: ${RUN_ROOT}"
  log "PYTHONPATH: ${PYTHONPATH}"

  mkdir -p "${RUN_ROOT}"
  printf 'scenario\trun_dir\tstatus\n' > "${RUN_ROOT}/_results.tsv"

  ensure_pythonpath

  # Sanity check: simctl importable
  if ! python3 -c "import simctl.cli" 2>/dev/null; then
    die "simctl.cli not importable. Check PYTHONPATH=${PYTHONPATH}"
  fi

  # Sanity check: slots are free (best-effort; simctl will fail fast if occupied)
  log "Sanity check passed. Starting regression round with ${#SCENARIOS[@]} scenarios ..."

  local failed=0
  for entry in "${SCENARIOS[@]}"; do
    IFS=':' read -r name path slot timeout <<< "${entry}"
    if ! run_scenario "${name}" "${path}" "${slot}" "${timeout}"; then
      ((failed++)) || true
    fi
  done

  # ---------------------------------------------------------------------------
  # Summary
  # ---------------------------------------------------------------------------
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log "REGRESSION ROUND COMPLETE"
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  cat "${RUN_ROOT}/_results.tsv"

  local passed_count
  passed_count="$(grep -c $'\tpassed$' "${RUN_ROOT}/_results.tsv" 2>/dev/null || echo 0)"
  log "Passed: ${passed_count} / ${#SCENARIOS[@]}"

  if [[ ${failed} -gt 0 ]]; then
    log "WARN: ${failed} scenario(s) had execution issues (check logs above)."
  fi

  log "All artifacts under: ${RUN_ROOT}"
  log "Next steps:"
  log "  1. Inspect individual run_result.json files"
  log "  2. If spawn_stability passed → update PMO blocker status"
  log "  3. If follow_lane/speed40 still failed → run failure taxonomy analysis"
  log "  4. simctl digest --run-root ${RUN_ROOT}"
}

main "$@"
