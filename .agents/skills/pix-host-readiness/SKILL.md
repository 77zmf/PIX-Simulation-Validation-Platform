---
name: pix-host-readiness
description: Use when checking whether the company Ubuntu 22.04 runtime host is ready for the stable PIX validation line, including Autoware Universe, ROS 2 Humble, CARLA 0.9.15, UE4.26, CUDA/TensorRT, bridge launch, simctl up/run --execute, host preflight, health-check failures, or handoff/rollback readiness.
---

# PIX host readiness

Use this skill for host bring-up and release-readiness decisions. The company Ubuntu 22.04 host is the only formal runtime host for stable closed-loop validation; Mac and Windows machines are for code sync, documentation, and lightweight checks.

## Procedure

1. Identify the machine role first:
   - company Ubuntu host: formal stable runtime host
   - Mac development terminal: code sync, docs, Codex, digest, lightweight `simctl`
   - home Windows host: editing, docs, repo maintenance
2. Read the relevant repo entry points:
   - `infra/ubuntu/check_host_readiness.sh`
   - `infra/ubuntu/preflight_and_next_steps.sh`
   - `infra/ubuntu/bootstrap_host.sh`
   - `stack/profiles/stable.yaml`
   - `stack/stable/start_autoware_host.sh`
   - `stack/stable/start_bridge_host.sh`
   - `stack/stable/stop_stable_stack.sh`
   - latest host session notes under `docs/`
3. For repo-side review, inspect scripts and config without claiming runtime success.
4. On the Ubuntu host, prefer the existing runbook commands:

```bash
bash infra/ubuntu/check_host_readiness.sh
bash infra/ubuntu/preflight_and_next_steps.sh
python -m simctl bootstrap --stack stable
python -m simctl up --stack stable --execute
python -m simctl run --scenario scenarios/l0/smoke_stub.yaml --run-root runs --execute
```

5. Decide readiness from evidence, not intention:
   - dependencies installed and version-pinned
   - CARLA RPC reachable
   - ROS graph has expected topics such as `/clock` and `/tf`
   - bridge and Autoware launch are observable
   - `run_result.json`, KPI gate, report, and replay path can be produced or the missing link is named

## Output

Use this structure:

1. Readiness verdict
2. Evidence found
3. Blocking gaps
4. Exact commands to run next
5. Validation scenario and expected observable
6. Rollback or containment note
7. Owner and next action

## Rules

- Never treat the Mac terminal as a substitute for formal runtime evidence.
- Do not recommend shadow/research work as a blocker for stable-line readiness.
- Prefer tightening existing `infra/ubuntu`, `stack/stable`, and `simctl` paths over adding new scripts.
- State what is stub, dry-run, or real runtime.
