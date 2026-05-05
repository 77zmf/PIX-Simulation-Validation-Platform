#!/usr/bin/env bash
# SUMO + Autoware Bug Hunt — 2026-05-05
# Purpose: Run CARLA+SUMO+Autoware joint scenarios and collect evidence for
#          Autoware bugs under SUMO co-simulation pressure.
#
# Usage:
#   cd ~/Documents/zmf_ws
#   bash ops/scripts/sumo_autoware_bug_hunt_20260505.sh
#
# Scenarios:
#   1. L1 SUMO traffic smoke     (baseline — expected passed)
#   2. L2 SUMO dense traffic     (baseline — expected passed)
#   3. L2 SUMO dense route-follow (bughunt — previously failed, attempt_count=0)
#
# Bug detection focus:
#   - Autoware stack crash / node death
#   - ROS topic dropout (especially /perception/object_recognition/objects)
#   - Planning failure (no trajectory, emergency stop, out-of-lane)
#   - Control instability (high jerk, oscillation)
#   - SUMO actor bridge desync (NPCs disappear or freeze)
#   - Ego spawn blocked by SUMO vehicles
#   - vehicle_cmd_gate emergency

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RUN_ROOT="${WS_ROOT}/runs/sumo_bug_hunt_$(date +%Y%m%d_%H%M%S)"
PYTHONPATH="${WS_ROOT}/src:${PYTHONPATH:-}"
export PYTHONPATH

mkdir -p "${RUN_ROOT}"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { log "FATAL: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SLOT_L1="stable-slot-01"
SLOT_L2_DENSE="stable-slot-02"
SLOT_L2_ROUTE="stable-slot-03"

SCENARIOS=(
  "l1_sumo_traffic:scenarios/l1/sumo_town01_traffic_smoke.yaml:${SLOT_L1}:600"
  "l2_sumo_dense:scenarios/l2/sumo_town01_dense_traffic.yaml:${SLOT_L2_DENSE}:600"
  "l2_sumo_route:scenarios/l2/sumo_town01_dense_route_follow.yaml:${SLOT_L2_ROUTE}:900"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  mkdir -p "${run_dir}"

  # Step 1: simctl run --execute
  log "[${name}] Step 1/4: simctl run --execute (timeout ${timeout_sec}s) ..."
  if ! timeout "${timeout_sec}" \
       python3 -m simctl.cli run \
         --scenario "${scenario_fullpath}" \
         --run-root "${run_dir}" \
         --slot "${slot}" \
         --execute \
         >"${run_dir}/bug_hunt_run.log" 2>&1; then
    log "WARN: [${name}] simctl run returned non-zero (see ${run_dir}/bug_hunt_run.log)"
  fi

  # Find actual run dir
  local actual_run_dir
  actual_run_dir="$(find "${run_dir}" -maxdepth 1 -name '*__*' -type d | sort | tail -n 1)"
  if [[ -z "${actual_run_dir}" ]]; then
    log "WARN: [${name}] No run directory found"
    printf '%s\t%s\t%s\t%s\n' "${name}" "N/A" "NO_RUN_DIR" "N/A" >> "${RUN_ROOT}/_results.tsv"
    return 1
  fi

  log "[${name}] Actual run dir: ${actual_run_dir}"

  # Step 2: validate + finalize
  if [[ -f "${actual_run_dir}/run_result.json" ]]; then
    log "[${name}] Step 2/4: simctl validate --execute --finalize ..."
    timeout 120 \
      python3 -m simctl.cli validate \
        --run-dir "${actual_run_dir}" \
        --execute \
        --finalize \
        >"${actual_run_dir}/bug_hunt_validate.log" 2>&1 || true
  fi

  # Step 3: report
  if [[ -f "${actual_run_dir}/run_result.json" ]]; then
    log "[${name}] Step 3/4: simctl report ..."
    timeout 60 \
      python3 -m simctl.cli report \
        --run-dir "${actual_run_dir}" \
        >"${actual_run_dir}/bug_hunt_report.log" 2>&1 || true
  fi

  # Step 4: bug-hunt evidence collection
  log "[${name}] Step 4/4: Collecting bug-hunt evidence ..."
  _collect_bug_evidence "${name}" "${actual_run_dir}"

  # Extract verdict
  local status="unknown"
  if [[ -f "${actual_run_dir}/run_result.json" ]]; then
    status="$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('status','unknown'))" "${actual_run_dir}/run_result.json" 2>/dev/null || echo unknown)"
  fi

  printf '%s\t%s\t%s\n' "${name}" "${actual_run_dir}" "${status}" >> "${RUN_ROOT}/_results.tsv"
  log "[${name}] RESULT: status=${status}"
  return 0
}

_collect_bug_evidence() {
  local name="$1"
  local actual_run_dir="$2"
  local bug_dir="${actual_run_dir}/bug_hunt_evidence"
  mkdir -p "${bug_dir}"

  # 1. ROS topic list snapshot (if ROS 2 available)
  if command -v ros2 &>/dev/null; then
    timeout 10 ros2 topic list >"${bug_dir}/ros2_topic_list.txt" 2>/dev/null || true
    timeout 10 ros2 node list >"${bug_dir}/ros2_node_list.txt" 2>/dev/null || true

    # Check key perception / planning / control topics
    for topic in \
      /perception/object_recognition/objects \
      /planning/scenario_planning/trajectory \
      /control/command/control_cmd \
      /control/command/actuation_cmd \
      /vehicle/status/velocity_status \
      /diagnostics \
      /autoware/state; do
      timeout 5 ros2 topic info "${topic}" >"${bug_dir}/ros2_topic_info_$(echo "${topic}" | tr '/' '_').txt" 2>/dev/null || true
    done

    # Sample diagnostics for errors/warnings
    timeout 5 ros2 topic echo /diagnostics --once --spin-time 2 \
      >"${bug_dir}/ros2_diagnostics_sample.txt" 2>/dev/null || true

    # Sample object recognition
    timeout 5 ros2 topic echo /perception/object_recognition/objects --once --spin-time 2 \
      >"${bug_dir}/ros2_objects_sample.txt" 2>/dev/null || true
  fi

  # 2. SUMO log tail
  local sumo_log
  sumo_log="$(find "${actual_run_dir}/command_logs" -name '*sumo*' -type f | head -n 1)"
  if [[ -n "${sumo_log}" ]]; then
    tail -n 200 "${sumo_log}" >"${bug_dir}/sumo_log_tail.txt" 2>/dev/null || true
  fi

  # 3. Autoware stack log tail (if available)
  local autoware_log
  autoware_log="$(find "${actual_run_dir}/command_logs" -name '*autoware-stack*' -type f | head -n 1)"
  if [[ -n "${autoware_log}" ]]; then
    tail -n 500 "${autoware_log}" >"${bug_dir}/autoware_stack_log_tail.txt" 2>/dev/null || true
  fi

  # 4. CARLA bridge log tail
  local bridge_log
  bridge_log="$(find "${actual_run_dir}/command_logs" -name '*autoware-bridge*' -type f | head -n 1)"
  if [[ -n "${bridge_log}" ]]; then
    tail -n 200 "${bridge_log}" >"${bug_dir}/carla_bridge_log_tail.txt" 2>/dev/null || true
  fi

  # 5. Run result key metrics
  if [[ -f "${actual_run_dir}/run_result.json" ]]; then
    python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print('Status:', d.get('status'))
print('Failure labels:', d.get('failure_labels'))
print('Gate passed:', d.get('gate',{}).get('passed'))
kpis = d.get('kpis', {})
for k in ['route_completion','collision_count','max_speed_kph','lateral_error_m','jerk_mps3',
          'sumo_cosim_alive','sumo_actor_count','autoware_object_stream_seen',
          'ego_control_command_seen','sensor_topic_coverage']:
    print(f'{k}:', kpis.get(k, 'N/A'))
" "${actual_run_dir}/run_result.json" >"${bug_dir}/run_result_summary.txt"
  fi

  # 6. Runtime evidence summary
  if [[ -f "${actual_run_dir}/runtime_evidence_summary.json" ]]; then
    python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print('attempt_count:', d.get('attempt_count'))
print('successful_attempt_count:', d.get('successful_attempt_count'))
print('sensor_probe_count:', d.get('sensor_probe_attempt_count'))
print('dynamic_probe_count:', d.get('dynamic_probe_attempt_count'))
" "${actual_run_dir}/runtime_evidence_summary.json" >"${bug_dir}/runtime_evidence_summary.txt"
  fi

  log "[${name}] Bug-hunt evidence saved to: ${bug_dir}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  log "WS_ROOT:  ${WS_ROOT}"
  log "RUN_ROOT: ${RUN_ROOT}"
  log "PYTHONPATH: ${PYTHONPATH}"

  printf 'scenario\trun_dir\tstatus\n' > "${RUN_ROOT}/_results.tsv"

  if ! python3 -c "import simctl.cli" 2>/dev/null; then
    die "simctl.cli not importable. Check PYTHONPATH=${PYTHONPATH}"
  fi

  log "Starting SUMO+Autoware bug-hunt round with ${#SCENARIOS[@]} scenarios ..."

  for entry in "${SCENARIOS[@]}"; do
    IFS=':' read -r name path slot timeout <<< "${entry}"
    run_scenario "${name}" "${path}" "${slot}" "${timeout}" || true
  done

  # ---------------------------------------------------------------------------
  # Summary + Bug triage
  # ---------------------------------------------------------------------------
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log "BUG HUNT ROUND COMPLETE"
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  cat "${RUN_ROOT}/_results.tsv"

  log ""
  log "Bug-hunt evidence directories:"
  find "${RUN_ROOT}" -type d -name 'bug_hunt_evidence' | while read -r d; do
    log "  ${d}"
  done

  log ""
  log "Next: Inspect each bug_hunt_evidence/ dir for:"
  log "  - ros2_topic_list.txt       → missing critical topics?"
  log "  - ros2_diagnostics_sample.txt → ERROR/WARN from Autoware nodes?"
  log "  - ros2_objects_sample.txt   → empty perception stream?"
  log "  - autoware_stack_log_tail.txt → node crashes, exceptions?"
  log "  - sumo_log_tail.txt         → SUMO sync errors, FatalTraCIError?"
  log "  - runtime_evidence_summary.txt → attempt_count=0 means route probe never started"
  log ""
  log "Artifact root: ${RUN_ROOT}"
}

main "$@"
