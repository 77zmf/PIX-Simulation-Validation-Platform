# Planning/Control Scene Gap Matrix

This matrix tracks the current automated bughunt coverage and the next scenarios needed to expose planning/control bugs. It is scoped to the stable line: Autoware Universe + CARLA 0.9.15 + PIX robobus runtime on the company Ubuntu host.

## Covered In Current Bughunt

| Risk Area | Current Scenario | Status |
| --- | --- | --- |
| L1 straight route-follow | `scenarios/l1/regression_follow_lane.yaml` | executable |
| Close cut-in through actor bridge | `scenarios/l2/robobus117th_town01_close_cut_in_actor_bridge.yaml` | executable |
| Merge/yield actor bridge | `scenarios/l2/planning_control_merge_regression.yaml` | executable |
| Multi-actor cut-in plus lead brake | `scenarios/l2/planning_control_multi_actor_cut_in_lead_brake.yaml` | executable |
| Public-road merge surrogate | `scenarios/l2/planning_control_public_road_merge_regression.yaml` | executable |
| Crosswalk VRU yield surrogate | `scenarios/l2/planning_control_crosswalk_vru_yield.yaml` | executable with dummy perception |
| Occluded pedestrian yield | `scenarios/l3/stress_occluded_pedestrian.yaml` | executable with dummy perception |
| Close occluded pedestrian yield | `scenarios/l3/occluded_pedestrian_close_yield.yaml` | executable with dummy perception |
| Double-occluder pedestrian yield | `scenarios/l3/occluded_pedestrian_double_occluder.yaml` | executable with dummy perception |

## Missing Scenarios To Add

| Priority | Gap | Why It Matters | First Acceptance Signal |
| --- | --- | --- | --- |
| P1 | Unprotected left / intersection negotiation | Exposes route selection, gap acceptance, and collision-risk behavior not covered by lane-follow or merge cases. Draft contract exists at `scenarios/l2/planning_control_unprotected_left_intersection_draft.yaml`; execution still needs a real left-turn route and probe. | `collision_count=0`, `min_ttc_sec>=1.8`, `route_completion>=0.90`, no route stuck timeout |
| P1 | Stop line / red light compliance | Rule violations are common planning bugs and are not covered by current gates. Draft contract exists at `scenarios/l2/planning_control_stop_line_red_light_draft.yaml`; execution still needs CARLA traffic-light control and stop-line metric extraction. | `red_light_violations=0`, `stop_line_overshoot_m<=threshold` |
| P2 | Lane change / overtake | Merge/cut-in tests cover reactive yielding, not ego-initiated lane-change planning. | lane-change completes without collision, bounded lateral jerk |
| P2 | Dense SUMO mixed traffic | SUMO smoke proves data plumbing, not planning behavior under traffic pressure. | route progresses with SUMO actors, no collision, safe TTC |
| P2 | Adverse weather / low visibility | Current stable scenarios mostly run clear weather; control stability under degraded visibility remains untested. | no collision, route progresses, bounded jerk |
| P2 | Sensor degradation / delayed perception | Current sensor probes check presence/samples, not delayed or missing perception inputs. | system degrades safely, no unsafe control command |

## Road-Test-Derived Drafts From Local MCAP Evidence

The Mac-local `/Users/cyber/Documents/zmf_test-data` dataset now anchors concrete planning/control replay drafts through `assets/manifests/planning_road_test_failcases_202604.yaml`. The raw MCAP/log/video/map artifacts stay outside Git.

| Priority | Draft Scenario | Source Cases | Simulation Target | Blocker |
| --- | --- | --- | --- | --- |
| P1 | `scenarios/l2/planning_control_roadtest_trajectory_jump_replay_draft.yaml` | 117th `14:52` trajectory jump, 117th `10:04` trajectory issue, 82th turn/new-route P-gear case | route churn, lane-change/static-obstacle path continuity, route update during turn | MCAP replay probe or deterministic public-road CARLA route |
| P1 | `scenarios/l2/planning_control_roadtest_trajectory_dropout_replay_draft.yaml` | 117th `14:56` no trajectory, 117th `11:03` trajectory disappeared, 117th `16:47` route-empty planner crash | trajectory publication dropout, route recovery, route-handler lateral-neighbor loop | replay metrics for trajectory silence, empty route, and planner container death |
| P1 | `scenarios/l2/planning_control_roadtest_out_of_lane_brake_takeover_replay_draft.yaml` | 125th `13:54` out-of-lane/brake-takeover case | out-of-lane slowdown failure, lateral shift, MRM emergency/brake chain | replay metrics for lateral jerk, emergency command, and brake takeover |

Shared draft KPI gate: `evaluation/kpi_gates/planning_control_trajectory_stability_replay.yaml`.

## Add Order

1. Run `stable_l2_planning_control_crosswalk_vru_yield` once on the Ubuntu host and keep it in the bughunt campaign only if it closes with `run_result -> KPI gate -> report/bugpack`.
2. Add `stable_l2_stop_line_red_light` after traffic-light state can be controlled deterministically in CARLA Town01.
3. Add `stable_l2_unprotected_left_intersection` after route and actor spawn points are fixed.
4. Add the road-test replay probe for the three P1 local MCAP-derived drafts above; keep them draft-only until they emit runtime evidence.
5. Add dense SUMO and adverse-weather cases after the above deterministic cases are stable.

## Runtime Rule

Do not promote a draft scenario into `stable_planning_control_bughunt.yaml` until it has:

- deterministic spawn/route config
- validation command that emits runtime evidence
- KPI gate with clear ownership
- rollback note
- one successful company Ubuntu dry-run or explicit blocked reason
