"""Tests for scripts/merge_main.sh, using a throwaway git repo. Run: python -m unittest discover tests"""
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "merge_main.sh"
TEX = "".join(f"line {i}\n" for i in range(1, 21))


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def commit(repo, files, msg="change"):
    for name, content in files.items():
        (repo / name).write_bytes(content.encode())
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)


class MergeMainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.name", "t")
        git(self.repo, "config", "user.email", "t@t")
        commit(self.repo, {"resume.tex": TEX, "r.pdf": "pdf-0", "p.webp": "img-0"})

    def tearDown(self):
        self.tmp.cleanup()

    def branch_and_main(self, branch_line, main_line):
        """A PR branch and main each edit one line of resume.tex and rebuild both built files."""
        git(self.repo, "checkout", "-q", "-b", "resume-sync-x")
        commit(self.repo, {"resume.tex": TEX.replace(f"line {branch_line}\n", "branch\n"), "r.pdf": "pdf-b", "p.webp": "img-b"})
        git(self.repo, "checkout", "-q", "main")
        commit(self.repo, {"resume.tex": TEX.replace(f"line {main_line}\n", "main\n"), "r.pdf": "pdf-m", "p.webp": "img-m"})
        git(self.repo, "checkout", "-q", "resume-sync-x")

    def merge(self):
        return subprocess.run(["bash", str(SCRIPT), "main", "r.pdf", "p.webp"], cwd=self.repo, capture_output=True, text=True)

    def test_separate_lines_merge_and_built_files_come_from_main(self):
        self.branch_and_main(3, 15)
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        tex = (self.repo / "resume.tex").read_text()
        self.assertIn("branch\n", tex)
        self.assertIn("main\n", tex)
        self.assertEqual((self.repo / "r.pdf").read_text(), "pdf-m")
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_same_lines_abort_and_fail(self):
        self.branch_and_main(3, 3)
        r = self.merge()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("resume.tex", r.stdout)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")  # merge aborted, branch untouched
        self.assertIn("branch\n", (self.repo / "resume.tex").read_text())

    def test_already_up_to_date(self):
        git(self.repo, "checkout", "-q", "-b", "resume-sync-x")
        self.assertEqual(self.merge().returncode, 0)


if __name__ == "__main__":
    unittest.main()
