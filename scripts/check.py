"""Step 0 of the résumé sync: decide, without reading any content, whether there is anything to do.

Run from the resume repo. Every watched repo is expected to be cloned beside it (../<repo>).
For each repo it lists the files changed since the last-reviewed commit in sync-state.json,
drops the files in `exclude_paths` (the pipeline's own outputs, so its commits never wake it up),
and prints one line per finding:

    changed <repo> <file> ...   new commits touch files that need review
    new <repo>                  a public repo that is neither watched nor ignored
    website-pdf stale           the website serves a different PDF than this repo's main
    repo-list unavailable       the GitHub API couldn't be reached; list repos another way

If nothing is printed except possibly "repo-list unavailable", the last line is "NOTHING TO SYNC".
"""
from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # the resume repo
ROOT = HERE.parent                              # folder holding all clones
USER = "danielzhang122"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout.strip()


def changed_files(repo: Path, since: str, excludes: list[str]) -> list[str] | None:
    """Files changed since `since`, minus excluded ones. None means `since` is unknown (review all)."""
    git(repo, "pull", "-q", "--ff-only")
    if git(repo, "cat-file", "-t", since) != "commit":
        return None
    files = git(repo, "diff", "--name-only", since, "HEAD").splitlines()
    return [f for f in files if not any(fnmatch.fnmatch(f, p) for p in excludes)]


def public_repos() -> list[dict] | None:
    url = f"https://api.github.com/users/{USER}/repos?per_page=100"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.load(r)
    except Exception:
        return None


def check(here: Path = HERE, root: Path = ROOT, list_repos=public_repos) -> list[str]:
    """Return the output lines. `here` is the resume repo, `root` the folder with the other clones."""
    state = json.loads((here / "sync-state.json").read_text(encoding="utf-8"))
    excludes = state.get("exclude_paths", {})
    findings, notes = [], []

    for name, since in state["repos"].items():
        repo = here if name == "resume" else root / name
        if not repo.exists():
            findings.append(f"changed {name} (not cloned)")
            continue
        files = changed_files(repo, since, excludes.get(name, []))
        if files is None:
            findings.append(f"changed {name} (last-reviewed commit missing; review from scratch)")
        elif files:
            findings.append(f"changed {name} " + " ".join(files))

    repos = list_repos()
    if repos is None:
        notes.append("repo-list unavailable")
    else:
        known = set(state["repos"]) | set(state["ignore"])
        findings += [f"new {r['name']}" for r in repos
                     if not r["fork"] and not r["archived"] and r["name"] not in known]

    site_pdf = root / "website" / "Daniel_Zhang_Resume.pdf"
    own_pdf = here / "Daniel_Zhang_Resume.pdf"
    if site_pdf.exists() and own_pdf.exists() and site_pdf.read_bytes() != own_pdf.read_bytes():
        findings.append("website-pdf stale")

    return notes + findings + ([] if findings else ["NOTHING TO SYNC"])


def main() -> int:
    print("\n".join(check()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
