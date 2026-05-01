# Continuous Ego Bughunt Loop

This runbook keeps the stable PIX ego vehicle testing loop repeatable and auditable. It extends the existing `simctl` chain instead of adding a separate runner.

## Objective

Run planning/control scenarios in repeated rounds:

`campaign-loop -> per-round run/validate/finalize/down -> report -> bugpack -> next round`

Each round writes its own artifacts, and the loop root keeps `loop_state.json` updated after every round.

## Safe Default

On the current company Ubuntu host, use one real CARLA+Autoware slot by default:

```bash
cd /home/pixmoving/PIX-Simulation-Validation-Platform
PYTHONPATH=src python3 -m simctl.cli campaign-loop \
  --config ops/test_campaigns/stable_planning_control_bughunt.yaml \
  --run-root runs/continuous_stable_planning_control_bughunt_$(date -u +%Y%m%dT%H%M%SZ) \
  --execute \
  --max-rounds 0 \
  --parallel 1 \
  --require-validation
```

Use `--max-rounds 0` only when the loop is intentionally long-running. For a bounded check, use `--max-rounds 1` or `--max-rounds 2`.

## Parallel Mode

The command supports multiple slots:

```bash
PYTHONPATH=src python3 -m simctl.cli campaign-loop \
  --config ops/test_campaigns/stable_planning_control_bughunt.yaml \
  --execute \
  --max-rounds 0 \
  --parallel 2 \
  --require-validation
```

Do not enable `--parallel 2` on the current host unless readiness shows enough memory and disk headroom. A full CARLA+Autoware slot can use several GiB of RAM, and prior host freezes make single-slot execution the safer default.

## Monitoring

```bash
tail -f <loop_root>/loop_stdout.log
cat <loop_root>/loop_state.json
find <loop_root> -name loop_round_result.json -print
find <loop_root> -path '*/bugpack/index.md' -print
```

The important evidence files are:

- `<loop_root>/loop_state.json`
- `<loop_root>/round_*/loop_round_result.json`
- `<loop_root>/round_*/report/report.md`
- `<loop_root>/round_*/bugpack/index.md`
- `<loop_root>/round_*/*/run_result.json`

## Stop And Cleanup

Stop the controller process, then clean the active run dir:

```bash
pkill -f "simctl.cli campaign-loop" || true
PYTHONPATH=src python3 -m simctl.cli down \
  --stack stable \
  --run-dir <active_round_run_dir>/<active_scenario_run_dir> \
  --execute
```

Confirm cleanup:

```bash
ps -eo pid,ppid,stat,comm,args | grep -E "[C]arlaUE4|[r]os2 launch|[a]utoware_carla|[s]umo|[s]imctl.cli" || true
ss -ltnp 2>/dev/null | grep -E ":(2000|8000|9000)\b" || true
cat artifacts/slot_locks/stable/stable-slot-01.json 2>/dev/null || echo slot_free
```

