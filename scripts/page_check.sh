#!/usr/bin/env bash
# Builds the résumé locally and checks it is one page, so the sync agent can rewrite and retry
# before pushing instead of waiting on CI.
#   bash scripts/page_check.sh [resume.tex]
# Prints "Pages: N". Exit 0 = one page; 1 = too long (prints the text that spilled onto page 2,
# which is how much to cut); 2 = LaTeX error (prints the end of the log).
# Installs LaTeX with apt the first time (about a minute) if it is missing.
set -uo pipefail
tex=${1:-resume.tex}

if ! command -v latexmk >/dev/null || ! command -v pdfinfo >/dev/null; then
  echo "Installing LaTeX (first run only, about a minute)..." >&2
  sudo=; [ "$(id -u)" -ne 0 ] && sudo=sudo
  pkgs="texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended latexmk poppler-utils"
  $sudo apt-get install -y -qq $pkgs >/dev/null 2>&1 ||
    { $sudo apt-get update -qq >/dev/null 2>&1 && $sudo apt-get install -y -qq $pkgs >/dev/null 2>&1; } ||
    { echo "Could not install LaTeX; rely on the GitHub build (scripts/wait_build.sh)." >&2; exit 2; }
fi

out=$(mktemp -d)
pdf="$out/$(basename "${tex%.tex}").pdf"
if ! latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir="$out" "$tex" >"$out/build.log" 2>&1; then
  echo "LaTeX error:"; grep -A5 '^!' "$out/build.log" | head -30 || tail -30 "$out/build.log"
  exit 2
fi

pages=$(pdfinfo "$pdf" | awk '/^Pages:/ {print $2}')
echo "Pages: $pages"
if [ "$pages" != "1" ]; then
  echo "Too long. This spilled onto page 2; tighten the text you changed by at least this much:"
  pdftotext -f 2 -layout "$pdf" - | sed '/^[[:space:]]*$/d'
  exit 1
fi
