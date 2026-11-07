"""Tests for scripts/website_pdf.sh, using throwaway git repos (no network). Run: python -m unittest discover tests"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "website_pdf.sh"
PAGE = "<p>PDF, one page, updated Jan 2020. <a>Download</a></p>\n<p>other text</p>\n"


def git(repo, *args, env=None):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
                          env={**os.environ, **(env or {})}).stdout.strip()


def commit(repo, files, date="2026-11-07T12:00:00"):
    for name, content in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_bytes(content.encode())
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "c", env={"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})


class WebsitePdfTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.res, self.origin, self.site = root / "res", root / "origin.git", root / "site"
        for repo in (self.res, self.site):
            repo.mkdir()
            git(repo, "init", "-q", "-b", "main")
            git(repo, "config", "user.name", "t")
            git(repo, "config", "user.email", "t@t")
        commit(self.res, {"resume.tex": "x", "r.pdf": "pdf-new", "resume-preview.webp": "img-new"})
        commit(self.site, {"r.pdf": "pdf-old", "images/resume-preview.webp": "img-old", "index.html": PAGE, "other.txt": "keep"})
        git(self.site, "init", "-q", "--bare", str(self.origin))
        git(self.site, "remote", "add", "origin", str(self.origin))
        git(self.site, "push", "-q", "origin", "main")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *extra):
        env = {**os.environ, "GIT_NAME": "danielzhang122", "GIT_EMAIL": "d@users.noreply.github.com"}
        env.pop("GITHUB_OUTPUT", None)
        return subprocess.run(["bash", str(SCRIPT), str(self.res), str(self.site), "r.pdf", "resume.tex", *extra],
                              capture_output=True, text=True, env=env)

    def remote_file(self, branch, path):
        return git(self.origin, "show", f"{branch}:{path}")

    def test_new_branch_with_pdf_preview_and_month(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        branch = r.stdout.strip().split("branch=")[-1]
        self.assertTrue(branch.startswith("resume-pdf-"))
        self.assertEqual(self.remote_file(branch, "r.pdf"), "pdf-new")
        self.assertEqual(self.remote_file(branch, "images/resume-preview.webp"), "img-new")
        self.assertIn("updated Nov 2026.", self.remote_file(branch, "index.html"))
        self.assertEqual(git(self.origin, "log", "-1", "--format=%an <%ae>%n%b", branch), "danielzhang122 <d@users.noreply.github.com>")
        changed = git(self.origin, "diff", "--name-only", "main", branch).split()
        self.assertEqual(sorted(changed), ["images/resume-preview.webp", "index.html", "r.pdf"])

    def test_same_pdf_pushes_nothing(self):
        commit(self.res, {"r.pdf": "pdf-old"})
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("branch=", r.stdout)
        self.assertEqual(git(self.origin, "branch", "--list").split(), ["main"])

    def test_existing_branch_name_is_never_reused(self):
        first = self.run_script().stdout.strip().split("branch=")[-1]
        git(self.site, "checkout", "-q", "main")
        second = self.run_script().stdout.strip().split("branch=")[-1]
        self.assertEqual(second, first + "-2")

    def test_open_pr_branch_gets_a_commit_on_top(self):
        first = self.run_script().stdout.strip().split("branch=")[-1]
        git(self.site, "checkout", "-q", "main")
        commit(self.res, {"r.pdf": "pdf-newer"})
        r = self.run_script(first)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"branch={first}", r.stdout)
        self.assertEqual(self.remote_file(first, "r.pdf"), "pdf-newer")
        self.assertEqual(git(self.origin, "rev-list", "--count", f"main..{first}"), "2")


if __name__ == "__main__":
    unittest.main()
