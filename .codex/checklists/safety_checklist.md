# Codex Safety Checklist

Use this before any task that touches runtime, vehicle data, assets, scripts, workflows, or repo cleanup.

## Before Work

- [ ] Goal is one task only.
- [ ] Allowed files are explicit.
- [ ] Forbidden files are explicit.
- [ ] Stable / shadow / reconstruction line is clear.
- [ ] Verification is defined.
- [ ] Rollback or containment path is known.
- [ ] No secrets, credentials, tokens, private keys, or passwords are included.
- [ ] No large raw assets are being added to Git.
- [ ] Runtime changes name the Ubuntu host validation that remains required.

## Forbidden By Default

Do not run these unless the user explicitly asks for that exact operation:

```bash
rm -rf
git reset --hard
git clean -fd
git push --force
docker system prune
sudo
chmod -R
chown -R
```

## Evidence Rules

- [ ] `Done` has an evidence pointer.
- [ ] `fixed` has reproducible evidence.
- [ ] `passed` has final KPI or explicit acceptance criteria.
- [ ] Mac dry-run / stub evidence is labeled non-formal.
- [ ] `launch_submitted` is not treated as final acceptance.
- [ ] Notion status is not treated as engineering evidence.

