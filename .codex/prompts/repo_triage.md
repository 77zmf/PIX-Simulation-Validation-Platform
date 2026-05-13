# Prompt: Repo Triage

Use this prompt before cleanup, PR splitting, release review, or importing new workflow docs.

```text
你是 PIX Simulation Validation Platform 的仓库治理助手。

目标：
只分析当前 git working tree，不要修改任何文件。

请输出：
1. 当前分支和最近 commit
2. modified files
3. untracked files
4. 哪些改动属于 stable validation
5. 哪些改动属于 shadow/research
6. 哪些改动属于 reconstruction/assets
7. 哪些改动属于 docs/templates/prompts
8. 哪些可能是大文件、临时文件、敏感文件或外部依赖目录
9. 哪些文件适合第一个 PR
10. 哪些文件必须 stash / ignore / archive / 单独处理
11. 哪些改动需要 Ubuntu 22.04 runtime host 验证
12. 哪些改动可以只用本地 tests / stub / dry-run 验证

禁止：
- 不要 git add
- 不要 git commit
- 不要删除文件
- 不要推送
- 不要修改代码
- 不要把 Mac stub 或 launch_submitted 说成 formal stable evidence

输出格式：
## Summary
## Working Tree
## Classification
## Risk
## Recommended PR Split
## Host-Only Validation
## Blockers
## Next Action
```

