"""Install the résumé sync pipeline into someone else's résumé repo.

Copies the pipeline's code, tests and workflows from this repo, fills in the per-person template
(template/SYNC.md) and writes a fresh sync-state.json. It never touches the person's résumé content
except to add one reproducible-PDF line after \\documentclass if it is missing.

    python3 scripts/install.py --target ../jane-resume --name "Jane Doe" --github-user janedoe \\
        [--tex resume.tex] [--pdf-name Jane_Doe_Resume.pdf] \\
        [--site-url https://janedoe.dev --website-repo janedoe.github.io] [--force]

See INSTALL.md for the full procedure (scheduling the weekly agent is a separate step).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
COPY = [
    "scripts/check.py",
    "tests/test_check.py",
    ".github/workflows/build.yml",
    ".github/workflows/test.yml",
]
GITIGNORE = ["*.aux", "*.log", "*.out", "*.fls", "*.fdb_latexmk", "*.synctex.gz", "preview.png", "__pycache__/"]
REPRO = r"\ifdefined\pdftrailerid \pdfinfoomitdate=1 \pdftrailerid{} \fi"


def fill_sync(a: argparse.Namespace) -> str:
    first = a.name.split()[0]
    site = bool(a.website_repo or a.site_url)
    site_name = a.site_url or f"the `{a.website_repo}` repo"
    if a.website_repo and a.website_git_name and a.website_git_email:
        identity = (f"In the `{a.website_repo}` repo commit as {first}: run "
                    f'`git config user.name "{a.website_git_name}"` and '
                    f'`git config user.email "{a.website_git_email}"` there first.')
    elif a.website_repo:
        identity = f"In the `{a.website_repo}` repo, commit with the identity {first} uses there."
    else:
        identity = ""
    values = {
        "NAME": a.name,
        "FIRST_NAME": first,
        "GITHUB_USER": a.github_user,
        "TEX_FILE": a.tex,
        "PDF_NAME": a.pdf_name,
        "WEBSITE_REPO": a.website_repo or "",
        "SITE_CLAUSE": f" and portfolio site ({site_name})" if site else "",
        "OR_SITE": " or on the site" if site else "",
        "OR_SITE_2": " or the site" if site else "",
        "OR_SITE_3": " or the site" if site else "",
        "AND_SITE": ", the site" if site else "",
        "WEBSITE_IDENTITY": identity,
        "STALE_LINE": ", `website-pdf stale`" if a.website_repo else "",
    }
    text = (SRC / "template" / "SYNC.md").read_text(encoding="utf-8")
    if a.website_repo:
        text = text.replace("<!-- website -->\n", "").replace("<!-- /website -->\n", "")
    else:
        text = re.sub(r"<!-- website -->\n.*?<!-- /website -->\n\n?", "", text, flags=re.S)
        text = text.replace("### 7. Finish", "### 6. Finish").replace("step 7 notification", "step 6 notification")
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    leftover = re.findall(r"\{\{\w+\}\}", text)
    if leftover:
        sys.exit(f"template placeholders left unfilled: {leftover}")
    return text


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", required=True, type=Path, help="local clone of the person's résumé repo")
    p.add_argument("--name", required=True, help='full name, e.g. "Jane Doe"')
    p.add_argument("--github-user", required=True)
    p.add_argument("--resume-repo", help="GitHub name of the résumé repo (default: target folder name)")
    p.add_argument("--tex", default="resume.tex", help="LaTeX source, relative to the repo root")
    p.add_argument("--pdf-name", help="committed PDF name (default: First_Last_Resume.pdf)")
    p.add_argument("--site-url", default="", help="portfolio URL, if any")
    p.add_argument("--website-repo", default="", help="repo that serves the PDF on the site, if any")
    p.add_argument("--website-git-name", default="")
    p.add_argument("--website-git-email", default="")
    p.add_argument("--force", action="store_true", help="overwrite existing pipeline files")
    a = p.parse_args()

    target = a.target.resolve()
    a.resume_repo = a.resume_repo or target.name
    a.pdf_name = a.pdf_name or "_".join(a.name.split()) + "_Resume.pdf"
    tex = target / a.tex
    if not (target / ".git").exists():
        sys.exit(f"{target} is not a git clone")
    if not tex.exists():
        sys.exit(f"{tex} not found: the pipeline needs a LaTeX résumé (see INSTALL.md, step 2)")
    if "/" in a.tex:
        sys.exit("--tex must be at the repo root (the build workflow compiles from there)")
    if a.pdf_name == Path(a.tex).with_suffix(".pdf").name:
        sys.exit("--pdf-name must differ from the LaTeX file's own output name")

    outputs = ["SYNC.md", "sync-state.json", *COPY]
    clash = [f for f in outputs if (target / f).exists()]
    if clash and not a.force:
        sys.exit("already present (rerun with --force to overwrite): " + ", ".join(clash))

    for rel in COPY:
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC / rel, target / rel)

    build = target / ".github/workflows/build.yml"
    b = build.read_text(encoding="utf-8")
    b = re.sub(r"(?m)^  TEX_FILE: .*$", f"  TEX_FILE: {a.tex}", b)
    b = re.sub(r"(?m)^  PDF_NAME: .*$", f"  PDF_NAME: {a.pdf_name}", b)
    build.write_text(b, encoding="utf-8")

    (target / "SYNC.md").write_text(fill_sync(a), encoding="utf-8")

    head = subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    excludes = {a.resume_repo: [a.tex, a.pdf_name, "resume-preview.webp", "sync-state.json"]}
    if a.website_repo:
        excludes[a.website_repo] = [a.pdf_name]
    state = {
        "last_run": None,
        "config": {"github_user": a.github_user, "resume_repo": a.resume_repo,
                   "pdf_name": a.pdf_name, "website_repo": a.website_repo},
        # Only the résumé repo is watched at first, so the first run sees every other repo as new.
        "repos": {a.resume_repo: head},
        "exclude_paths": excludes,
        "ignore": [],
    }
    (target / "sync-state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    gi = target / ".gitignore"
    have = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    stem_pdf = Path(a.tex).with_suffix(".pdf").name
    add = [x for x in [*GITIGNORE, stem_pdf] if x not in have]
    if add:
        gi.write_text("\n".join([*have, "# résumé sync", *add]) + "\n", encoding="utf-8")

    t = tex.read_text(encoding="utf-8")
    if r"\pdftrailerid" not in t:
        t = re.sub(r"(\\documentclass[^\n]*\n)", lambda m: m.group(1) + REPRO + "\n", t, count=1)
        tex.write_text(t, encoding="utf-8")

    print(f"Installed into {target}:")
    for f in outputs:
        print("  ", f)
    print("Next: run the tests there, commit, push, then schedule the weekly agent (INSTALL.md, steps 4-5).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
