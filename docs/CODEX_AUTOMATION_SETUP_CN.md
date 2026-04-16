# Codex 自动化安装说明

## 你会得到什么

导入这套覆盖包后，仓库会新增：

- Codex 项目配置：`.codex/config.toml`
- 仓库级 Codex 覆盖规则：`AGENTS.override.md`
- 3 个可复用技能：
  - `repo-verification`
  - `project-digest-triage`
  - `runtime-closure-audit`
- 3 个 GitHub Actions：
  - `codex-pr-review.yml`
  - `codex-digest-triage.yml`
  - `codex-runtime-closure-audit.yml`
- 3 个非交互 prompt 模板

## 安装方式

把整个覆盖包解压到仓库根目录即可。

推荐顺序：

1. 合并文件到仓库根目录
2. 提交到一个测试分支
3. 在 GitHub 仓库 Secrets 中新增：
   - `OPENAI_API_KEY`（必需）
   - `GH_PROJECT_TOKEN`（可选；当默认 workflow token 无法读取 GitHub Project v2 时使用）
4. 先手动触发：
   - `codex-digest-triage`
   - `codex-runtime-closure-audit`
5. 再放开 PR review 自动触发

## 本地验证

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
bash .agents/skills/repo-verification/scripts/run_checks.sh
bash .agents/skills/project-digest-triage/scripts/build_digest.sh automation_outputs/project_digest tests/fixtures/project_tasks.json tests/fixtures/project_scenarios.json
bash .agents/skills/runtime-closure-audit/scripts/audit_stub_run.sh automation_outputs/runtime_audit
```

## GitHub Actions 说明

### codex-pr-review
- 触发：PR opened / synchronize / reopened / ready_for_review
- 输出：PR 评论 + `codex-pr-review` artifact

### codex-digest-triage
- 触发：weekday schedule + 手动 dispatch
- 默认建议先用 fixture 验证
- 输出：digest artifact + Codex triage markdown + step summary

### codex-runtime-closure-audit
- 触发：手动 dispatch
- 只跑 stub-safe 路径
- 输出：runtime audit artifact + 闭环差距分析

## 安全边界

- 这套自动化默认不做实时运行主机控制
- 不会替代 Ubuntu runtime host 的正式 bring-up
- 仅对仓库内文件、fixture、stub-safe 路径和 GitHub 项目运营做自动化
- 真实 `--execute` 路径仍应在公司 Ubuntu 22.04 主机上运行
