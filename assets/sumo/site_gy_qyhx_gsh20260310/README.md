# site_gy_qyhx_gsh20260310 SUMO Asset Intake

This directory documents the lightweight Git-tracked contract for the public-road SUMO traffic assets. Generated or large files stay outside Git and are referenced through `assets/manifests/site_gy_qyhx_gsh20260310_sumo_draft.yaml`.

Required external files under `${SIM_ASSET_ROOT}/site_gy_qyhx_gsh20260310/sumo/`:

- `site_gy_qyhx_gsh20260310.net.xml`
- `site_gy_qyhx_gsh20260310.rou.xml`
- `site_gy_qyhx_gsh20260310.sumocfg`

Preferred source is a public-road OpenDRIVE export or native SUMO network. Lanelet2 best-effort conversion is allowed only for intake experiments and must not become the stable acceptance path unless route topology and projection checks pass.
