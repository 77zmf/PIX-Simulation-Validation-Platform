# Autoware Release Checklist

## Identity
- [ ] Confirm repo root
- [ ] Confirm current branch
- [ ] Record HEAD commit
- [ ] Record nearest tag
- [ ] Confirm whether HEAD is detached

## Dirty state
- [ ] Check modified files
- [ ] Check staged files
- [ ] Check untracked files
- [ ] Confirm whether local source/config changes are intentional

## Baseline comparison
- [ ] Identify baseline tag / anchor / known-good commit
- [ ] Compare ahead/behind counts
- [ ] Review commit list since baseline
- [ ] Review diff summary since baseline

## Multi-repo consistency
- [ ] Check all repos under `src/`
- [ ] Record each repo branch
- [ ] Record each repo HEAD
- [ ] Flag detached HEAD repos
- [ ] Flag dirty repos
- [ ] Compare actual local repos with `.repos` manifest if present

## Build and runtime risk
- [ ] Check obvious merge conflicts
- [ ] Check missing repos / submodules
- [ ] Check generated artifacts mixed into source changes
- [ ] Check critical map/config/runtime files
- [ ] Confirm build/test evidence if available

## Delivery readiness
- [ ] Confirm release tag naming
- [ ] Confirm rollback target
- [ ] Confirm handoff metadata for workstation / OTA side
- [ ] Confirm issue traceability (branch/tag/commit/date)
