#!/usr/bin/env bash
# Waits for the "Build résumé" GitHub Action run of a pushed commit to finish and reports the result.
# The cloud blocks plain `sleep`, so the sync agent runs this one command instead of sleeping.
#   bash scripts/wait_build.sh <branch> [commit-sha]   (sha defaults to HEAD)
# Exit 0 = build passed (one page, PDF committed back); 1 = build failed (usually over one page);
# 2 = no result within 10 minutes or the GitHub API was unreachable (check with the GitHub MCP
# actions tools instead).
set -uo pipefail
branch=$1
sha=${2:-$(git rev-parse HEAD)}
repo=$(git remote get-url origin | sed -E 's#\.git$##; s#.*/([^/]+/[^/]+)$#\1#')
url="https://api.github.com/repos/$repo/actions/workflows/build.yml/runs?branch=$branch&per_page=20"

for _ in $(seq 1 60); do
  state=$(curl -fsS "$url" 2>/dev/null | SHA="$sha" python3 -c '
import json, os, sys
runs = [r for r in json.load(sys.stdin)["workflow_runs"] if r["head_sha"] == os.environ["SHA"]]
print(" ".join(str(runs[0][k]) for k in ("status", "conclusion", "html_url")) if runs else "none")
' 2>/dev/null) || state=""
  case "$state" in
    "completed success"*) echo "Build passed: ${state##* }"; exit 0 ;;
    completed*) echo "Build FAILED: ${state##* }"; echo "Run 'bash scripts/page_check.sh' to see what overflowed, tighten, commit and push again."; exit 1 ;;
  esac
  sleep 10
done
echo "No build result after 10 minutes for $sha on $branch (last state: ${state:-API unreachable})."
exit 2
