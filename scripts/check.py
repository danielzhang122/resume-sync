"""Step 0 of the résumé sync: decide, without reading any content, whether there is anything to do.

Run from the resume repo. Every watched repo is expected to be cloned beside it (../<repo>).
For each repo it lists the files changed since the last-reviewed commit in sync-state.json,
drops the files in `exclude_paths` (the pipeline's own outputs, so its commits never wake it up),
and prints one line per finding:

    changed <repo> <file> ...   new commits touch files that need review
    new <repo>                  a repo (public or private) that is neither watched nor ignored
    site <section> -/+ <text>   a line of visible text that changed in a section of the website
                                (Experience, Projects, ...), so wording changes can't hide among
                                styling commits
    website-pdf stale           the website serves a different PDF than this repo's main
    repo-list unavailable       the GitHub API couldn't be reached; list repos another way

A repo listed in `links` in sync-state.json gets "-> <résumé entry>" appended, naming the
experience entry (job, team) it belongs to, e.g. a work tool -> "Eclipse Automation".

If nothing is printed except possibly "repo-list unavailable", the last line is "NOTHING TO SYNC".
"""
from __future__ import annotations

import difflib
import fnmatch
import html
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # the resume repo
ROOT = HERE.parent                              # folder holding all clones

# Defaults for the optional "config" block in sync-state.json (set by scripts/install.py).
DEFAULTS = {
    "github_user": "danielzhang122",
    "resume_repo": "resume-sync",
    "pdf_name": "Daniel_Zhang_Resume.pdf",
    "website_repo": "website",  # "" if there is no website repo
    "website_file": "index.html",
    # Website sections whose text is compared line by line (<section data-cmd="..."> or id="...").
    "website_sections": ["whoami", "projects", "experience", "skills", "certs", "misc"],
}
SITE_LINES_PER_SECTION = 30


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout.strip()


def changed_files(repo: Path, since: str, excludes: list[str]) -> list[str] | None:
    """Files changed since `since`, minus excluded ones. None means `since` is unknown (review all)."""
    git(repo, "pull", "-q", "--ff-only")
    if git(repo, "cat-file", "-t", since) != "commit":
        return None
    files = git(repo, "diff", "--name-only", since, "HEAD").splitlines()
    return [f for f in files if not any(fnmatch.fnmatch(f, p) for p in excludes)]


def public_repos(user: str = DEFAULTS["github_user"]) -> list[dict] | None:
    """The user's repos. Private ones are included when the gh CLI can see them (work tools often are
    private but still belong on the résumé)."""
    try:
        out = subprocess.run(
            ["gh", "api", f"search/repositories?q=user:{user}&per_page=100", "--jq", ".items"],
            capture_output=True, text=True, timeout=30, check=True).stdout
        return json.loads(out)
    except Exception:
        pass
    url = f"https://api.github.com/users/{user}/repos?per_page=100"  # public repos only
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.load(r)
    except Exception:
        return None


def page_sections(page: str) -> dict[str, list[str]]:
    """Visible text of each <section data-cmd="x"> (or id="x"), one line per paragraph/row/item."""
    page = re.sub(r"(?is)<(script|style|pre|svg)\b.*?</\1>", " ", page)
    out = {}
    for m in re.finditer(r'(?is)<section\b[^>]*?(?:data-cmd|id)="([^"]+)"[^>]*>(.*?)</section>', page):
        text = re.sub(r"(?i)</?(p|div|li|h\d|br|tr|figcaption)\b[^>]*>", "\n", m.group(2))
        text = html.unescape(re.sub(r"<[^>]+>", "", text))
        out[m.group(1)] = [ln for ln in (" ".join(l.split()) for l in text.splitlines()) if ln]
    return out


def site_changes(repo: Path, since: str, file: str, sections: list[str]) -> list[str]:
    """`site <section> -/+ <line>` for every line of visible text that changed since `since`."""
    old = git(repo, "show", f"{since}:{file}") if git(repo, "cat-file", "-t", since) == "commit" else ""
    new = git(repo, "show", f"HEAD:{file}")
    before, after = page_sections(old), page_sections(new)
    lines = []
    for name in sections:
        diff = [d for d in difflib.unified_diff(before.get(name, []), after.get(name, []), lineterm="", n=0)
                if d[:1] in "-+" and d[:3] not in ("---", "+++")]
        lines += [f"site {name} {d[0]} {d[1:]}" for d in diff[:SITE_LINES_PER_SECTION]]
        if len(diff) > SITE_LINES_PER_SECTION:
            lines.append(f"site {name} ... {len(diff) - SITE_LINES_PER_SECTION} more changed lines")
    return lines


def check(here: Path = HERE, root: Path = ROOT, list_repos=None) -> list[str]:
    """Return the output lines. `here` is the resume repo, `root` the folder with the other clones."""
    state = json.loads((here / "sync-state.json").read_text(encoding="utf-8"))
    cfg = {**DEFAULTS, **state.get("config", {})}
    if list_repos is None:
        list_repos = lambda: public_repos(cfg["github_user"])  # noqa: E731
    excludes = state.get("exclude_paths", {})
    links = state.get("links", {})
    tag = lambda name: f" -> {links[name]}" if name in links else ""  # noqa: E731
    findings, notes = [], []

    for name, since in state["repos"].items():
        repo = here if name == cfg["resume_repo"] else root / name
        if not repo.exists():
            findings.append(f"changed {name} (not cloned){tag(name)}")
            continue
        files = changed_files(repo, since, excludes.get(name, []))
        if files is None:
            findings.append(f"changed {name} (last-reviewed commit missing; review from scratch){tag(name)}")
        elif files:
            findings.append(f"changed {name} " + " ".join(files) + tag(name))
        if name == cfg["website_repo"] and files != [] and (repo / cfg["website_file"]).exists():
            findings += site_changes(repo, since, cfg["website_file"], cfg["website_sections"])

    repos = list_repos()
    if repos is None:
        notes.append("repo-list unavailable")
    else:
        known = set(state["repos"]) | set(state["ignore"])
        findings += [f"new {r['name']}" + (" (private)" if r.get("private") else "") + tag(r["name"])
                     for r in repos if not r["fork"] and not r["archived"] and r["name"] not in known]

    site_pdf = root / cfg["website_repo"] / cfg["pdf_name"]
    own_pdf = here / cfg["pdf_name"]
    if cfg["website_repo"] and site_pdf.exists() and own_pdf.exists() and site_pdf.read_bytes() != own_pdf.read_bytes():
        findings.append("website-pdf stale")

    return notes + findings + ([] if findings else ["NOTHING TO SYNC"])


def main() -> int:
    print("\n".join(check()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
