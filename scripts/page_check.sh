#!/usr/bin/env bash
# Builds the résumé locally and checks it is one page, so the sync agent can rewrite and retry
# before pushing instead of waiting on CI.
#   bash scripts/page_check.sh [resume.tex]
# Prints "Pages: N". Exit 0 = one page; 1 = too long (prints the text that spilled onto page 2,
# which is how much to cut); 2 = LaTeX error (prints the end of the log); 3 = one page, but some
# paragraph ends within 10 pt of the right margin and may wrap in CI (prints which; shorten them).
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

# CI's LaTeX can break lines slightly differently, so a paragraph whose last line nearly reaches the
# right margin may wrap there and push the page over. Flag those (right-aligned dates are skipped).
pdftotext -bbox-layout "$pdf" "$out/bbox.html"
tight=$(python3 -I - "$out/bbox.html" "${TIGHT_PT:-10}" <<'PY'
import html, re, sys
s = open(sys.argv[1]).read(); margin = float(sys.argv[2])
blocks = []
for b in re.finditer(r"<block[^>]*>(.*?)</block>", s, re.S):
    lines = re.findall(r'<line xMin="[\d.]+" yMin="[\d.]+" xMax="([\d.]+)"[^>]*>(.*?)</line>', b.group(1), re.S)
    if lines:
        blocks.append((float(lines[-1][0]), html.unescape(" ".join(re.findall(r">([^<]+)</word>", lines[-1][1])))))
right = max(x for x, _ in blocks)
for x, text in blocks:
    if right - margin < x < right - 0.5:  # flush with the margin = right-aligned date, not a paragraph end
        print(f"  {right - x:4.1f} pt left: ...{text[-70:]}")
PY
)
if [ -n "$tight" ]; then
  echo "Nearly full last lines (CI may wrap these onto an extra line and overflow the page):"
  echo "$tight"
  echo "Shorten each of these by a word or two, then run this again."
  exit 3
fi
