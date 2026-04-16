# Subagent 上手与协同 Playbook

对应 issue：

- [#11 子agent上手、阅读顺序与协同约定](https://github.com/77zmf/PIX-Simulation-Validation-Platform/issues/11)

这份 playbook 不再只说“先看什么”，而是把团队上手 subagent 的入口收成 3 个可直接执行的动作：

1. 先列出可用 spec。
2. 再按成员或角色拿到 onboarding 建议。
3. 再渲染目标 subagent 的 `spawn_json`。

## 1. 最小入口

```powershell
python -m simctl subagent-spec --list
python -m simctl subagent-spec --list-onboarding
python -m simctl subagent-spec --onboarding yzp333666
python -m simctl subagent-spec --name public_road_e2e_shadow_explorer --format spawn_json
```

## 2. `--list-onboarding` 是干什么的

`--list-onboarding` 会列出当前仓库已经版本化的 onboarding profile。

当前包含：

- `zhu_minfeng`
- `lsxala`
- `yzp333666`
- `codex_pmo`

每个 profile 都会给出：

- 当前角色说明
- 推荐阅读顺序
- 推荐 subagents
- 配套 skills
- 起手命令
- issue 回贴建议格式

## 3. 对 `@yzp333666` 的最短路径

```powershell
python -m simctl subagent-spec --onboarding yzp333666
python -m simctl subagent-spec --name public_road_e2e_shadow_explorer
python -m simctl subagent-spec --name algorithm_research_explorer --format spawn_json
```

这条路径对应：

- `BEVFusion`
- `UniAD-style / VADv2` shadow
- 感知输出契约
- 指标口径
- 研究对照和 blocker 回贴

## 4. 推荐阅读顺序

不管是谁，建议都先看：

1. `README.md`
2. `AGENTS.md`
3. `docs/TEAM_AGENT_USAGE_CN.md`
4. `docs/TEAM_SKILL_USAGE_CN.md`
5. `docs/SUBAGENT_CATALOG.md`

然后再按 `--onboarding <profile>` 的结果看各自额外阅读项。

## 5. 推荐协同节奏

1. 先确定 issue 范围，不要一次混多个方向。
2. 先跑 `python -m simctl subagent-spec --onboarding <profile>`。
3. 再选 1 个最合适的 subagent，不要同时提很多 explorer。
4. 如果任务需要结构化输出，再选配套 skill。
5. 结果要回填到对应 issue / PR，不要只停在本地终端。

## 6. 回贴 blocker 时推荐最少带什么

建议至少包含：

- 当前现象
- 已验证过什么
- 当前 blocker
- 下一步建议

如果是研究线，可替换成：

- 当前研究结论
- 接口或指标变化
- 当前 blocker
- 下一步实验

## 7. 当前结论

结论很简单：

- subagent 规格已经在 `ops/subagents/` 版本化
- onboarding 路由现在也已经版本化到仓库里
- 团队成员不需要再只靠聊天记录猜“先看什么、先用哪个 agent”
