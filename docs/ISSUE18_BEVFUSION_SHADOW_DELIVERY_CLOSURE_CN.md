# Issue 18 BEVFusion Shadow 交付收口

对应 issue：

- [#18 P1 感知与 Shadow E2E：BEVFusion 接口与指标口径](https://github.com/pixmoving-moveit/zmf_ws/issues/18)
- [#27 Q2 BEVFusion 基线与 Shadow E2E 研究计划](https://github.com/pixmoving-moveit/zmf_ws/issues/27)

这份文档只做一件事：把当前分支 `codex/feature/bevfusion-shadow-contract` 到目前为止的 repo-side 交付收口成一页纸。

## 1. 当前已经完成的交付

### 接口与配置

- 冻结 `BEVFusion` 公开道路感知输入输出契约
- 冻结 `BEVFusion -> UniAD-style shadow / VADv2 shadow` 的最小输入需求、同步约束和输出形式
- 冻结共享指标与 profile-specific 指标口径

对应文件：

- [adapters/profiles/perception_bevfusion_public_road.yaml](../adapters/profiles/perception_bevfusion_public_road.yaml)
- [adapters/profiles/e2e_bevfusion_uniad_shadow.yaml](../adapters/profiles/e2e_bevfusion_uniad_shadow.yaml)
- [adapters/profiles/e2e_bevfusion_vadv2_shadow.yaml](../adapters/profiles/e2e_bevfusion_vadv2_shadow.yaml)
- [tests/test_research_configs.py](../tests/test_research_configs.py)
- [docs/BEVFUSION_SHADOW_INTERFACE_BASELINE_CN.md](./BEVFUSION_SHADOW_INTERFACE_BASELINE_CN.md)

### 研究阅读与路线说明

- 补齐杨志朋负责范围内的阅读纪要
- 明确当前主线仍然是 `BEVFusion -> UniAD-style shadow / VADv2 shadow`
- 明确 `Hydra-MDP / Hydra-NeXt / MomAD` 暂不进入当前季度实现主线

对应文件：

- [docs/YANG_SHADOW_E2E_READING_NOTES_CN.md](./YANG_SHADOW_E2E_READING_NOTES_CN.md)
- [docs/PAPER_READING_MAP_CN.md](./PAPER_READING_MAP_CN.md)

### 报告与回贴工具

- `simctl report` 已支持 `Shadow Comparison`
- 已支持 `Comparison Gaps`
- 已支持 `Gate Verdicts`
- 已支持自动生成 issue-ready 的 [issue_update.md](../artifacts/issue18_validation/shadow_report_v5/issue_update.md)

对应文件：

- [src/simctl/reporting.py](../src/simctl/reporting.py)
- [tests/test_reporting.py](../tests/test_reporting.py)
- [tests/test_cli.py](../tests/test_cli.py)

### Ubuntu 真机执行 handoff

- 已整理公司 Ubuntu 主机上的真实 `--execute` 路径
- 已给出 3 条目标场景、建议槽位、统一 `run_root`、统一 `simctl report` 汇总命令

对应文件：

- [docs/BEVFUSION_SHADOW_UBUNTU_EXECUTE_RUNBOOK_CN.md](./BEVFUSION_SHADOW_UBUNTU_EXECUTE_RUNBOOK_CN.md)

## 2. 当前分支上的关键提交

- `7a71f5d feat(research): freeze bevfusion shadow interface baseline`
- `a6aa843 docs(research): add yang shadow e2e reading notes`
- `dba1fb4 feat(reporting): add shadow comparison summary`
- `885d2cd feat(reporting): track shadow comparison gaps`
- `3df473d feat(reporting): add shadow gate verdict summary`
- `d882a0a docs(research): add shadow ubuntu execute runbook`
- `e346ed7 feat(reporting): add issue-ready shadow summary`

## 3. 本地已验证内容

Windows 开发机上已经验证：

```bash
.venv\Scripts\python -m unittest tests.test_research_configs -v
.venv\Scripts\python -m unittest tests.test_reporting -v
.venv\Scripts\python -m unittest tests.test_cli -v
.venv\Scripts\python -m simctl.cli --repo-root . report --run-root artifacts/issue18_validation --output-dir artifacts/issue18_validation/shadow_report_v5
```

当前已经确认：

- `report.md / report.html / summary.json / issue_update.md` 都能稳定生成
- `Shadow Comparison`、`Gate Verdicts`、`Comparison Gaps` 都能写入报告
- mock 数据下 `UniAD-style shadow` 与 `VADv2 shadow` 已具备同口径比较条件

## 4. 还没有完成的正式验收

当前唯一核心 blocker：

- 还没有在公司 `Ubuntu 22.04` 主机上完成 3 条真实 `--execute` 回填

也就是说，repo-side 已经收口，但正式 runtime 验收还没收口。

## 5. 下一步唯一推荐动作

在公司 Ubuntu 主机上按 runbook 跑这 3 条：

```bash
simctl run --scenario scenarios/l2/perception_bevfusion_public_road_occlusion.yaml --run-root runs/issue18_shadow_execute --slot stable-slot-03 --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_uniad_unprotected_left.yaml --run-root runs/issue18_shadow_execute --slot stable-slot-01 --execute
simctl run --scenario scenarios/e2e/carla0915_bevfusion_vadv2_occluded_pedestrian.yaml --run-root runs/issue18_shadow_execute --slot stable-slot-02 --execute
simctl report --run-root runs/issue18_shadow_execute --output-dir runs/issue18_shadow_execute/report_shadow_issue18
```

跑完后直接回贴：

- `runs/issue18_shadow_execute/report_shadow_issue18/issue_update.md`

## 6. 当前不建议做的事

- 不建议再开 `Hydra-MDP / Hydra-NeXt / MomAD` 的实现分支
- 不建议在真机 `--execute` 没回填前继续扩 shadow 指标范围
- 不建议把当前任务拆去新的研究分支，避免把 `#18` 从“差正式验收”重新拉回“继续研究中”
