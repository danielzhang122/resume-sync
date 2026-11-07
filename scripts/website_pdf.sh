#!/usr/bin/env bash
# Copy main's résumé PDF and preview into a website clone and push them on a PR branch.
# Usage: website_pdf.sh <résumé repo> <website clone> <pdf name> <tex file> [open PR branch]
# Needs GIT_NAME and GIT_EMAIL. Pushes nothing if the website already has the same PDF.
# On a push, prints "branch=<name>" (and appends it to $GITHUB_OUTPUT when set).
set -euo pipefail
res=$(cd "$1" && pwd); site="$2"; pdf="$3"; tex="$4"; branch="${5:-}"
cd "$site"

if cmp -s "$res/$pdf" "$pdf"; then echo "Website PDF already matches main."; exit 0; fi

if [ -n "$branch" ]; then
  git fetch -q origin "$branch"
  git checkout -q -B "$branch" "origin/$branch"
  if cmp -s "$res/$pdf" "$pdf"; then echo "Open PR branch $branch already has main's PDF."; exit 0; fi
else
  base="resume-pdf-$(date -u +%F)"; branch="$base"; n=2
  # never reuse a branch that exists on the remote (it may belong to a merged or closed PR)
  while git ls-remote --exit-code --heads origin "$branch" >/dev/null; do branch="$base-$n"; n=$((n + 1)); done
  git checkout -q -b "$branch"
fi

cp "$res/$pdf" "$pdf"
mkdir -p images && cp "$res/resume-preview.webp" images/resume-preview.webp
files=("$pdf" images/resume-preview.webp)
month=$(LC_ALL=C git -C "$res" log -1 --format=%cd --date=format:'%b %Y' -- "$tex")
if [ -f index.html ] && [ -n "$month" ]; then
  sed -i -E "s/(PDF, one page, updated )[A-Z][a-z]{2} [0-9]{4}\./\1$month./" index.html
  files+=(index.html)
fi

git add -- "${files[@]}"
git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" commit -q -m "Update résumé PDF"
git push -q origin "HEAD:refs/heads/$branch"
echo "branch=$branch"
[ -n "${GITHUB_OUTPUT:-}" ] && echo "branch=$branch" >> "$GITHUB_OUTPUT"
exit 0
