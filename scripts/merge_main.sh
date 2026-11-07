#!/usr/bin/env bash
# Merge main into a résumé-sync PR branch, so open PRs never conflict over the built files.
# Usage: merge_main.sh <main ref, e.g. origin/main> <built file>...
# The built files (PDF, preview) are taken from main; the build rebuilds them right after.
# Any other conflict means two PRs edited the same lines: abort and fail.
set -euo pipefail
main="$1"; shift

git merge --no-edit "$main" && exit 0

pats=(); for f in "$@"; do pats+=(-e "$f"); done
others=$(git diff --name-only --diff-filter=U | grep -vxF "${pats[@]}" || true)
if [ -n "$others" ]; then
  git merge --abort
  echo "::error::This branch and $main edit the same lines in: $others"
  exit 1
fi
for f in "$@"; do git checkout "$main" -- "$f" 2>/dev/null || git rm -q --ignore-unmatch -- "$f"; done
git add -- "$@" 2>/dev/null || true
git commit --no-edit -q
