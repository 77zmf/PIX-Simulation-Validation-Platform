# Quarter Acceptance

The quarter is considered successful when the following are true:

- `simctl bootstrap --stack stable` is usable
- `simctl run` can produce `run_result.json`
- `simctl report` can produce `report.md` and `report.html`
- `simctl replay` can render a replay plan
- `gy_qyhx_gsh20260302` exists as a reusable asset bundle
- at least one public-road scenario enters normal validation
- at least one E2E shadow scenario runs on `CARLA 0.9.15 / UE4.26`
