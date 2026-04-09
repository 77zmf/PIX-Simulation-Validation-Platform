#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
cd "$ROOT"

echo "== Workspace =="
printf "root: %s
" "$(pwd)"
printf "branch: %s
" "$(git branch --show-current 2>/dev/null || true)"
printf "head: %s
" "$(git rev-parse HEAD 2>/dev/null || true)"
printf "tag: %s
" "$(git describe --tags --always 2>/dev/null || true)"
echo

echo "== git status =="
git status --short || true
echo

if [ -d src ]; then
  echo "== repos under src =="
  find src -maxdepth 4 -name .git -type d | while read -r gitdir; do
    repo="$(dirname "$gitdir")"
    echo "--- $repo ---"
    printf "branch: %s
" "$(git -C "$repo" branch --show-current 2>/dev/null || true)"
    printf "head: %s
" "$(git -C "$repo" rev-parse HEAD 2>/dev/null || true)"
    git -C "$repo" status --short || true
    echo
  done
fi
