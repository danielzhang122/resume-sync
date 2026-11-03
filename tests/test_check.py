"""Tests for scripts/check.py, using throwaway git repos. Run: python -m unittest discover tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def commit(repo, files: dict[str, bytes | str], msg="change"):
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.heads = {}
        for name in ("resume", "website", "project"):
            repo = self.root / name
            repo.mkdir()
            git(repo, "init", "-q")
            git(repo, "config", "user.name", "t")
            git(repo, "config", "user.email", "t@t")
            self.heads[name] = commit(repo, {"README.md": f"{name}\n"})
        commit(self.root / "resume", {"Daniel_Zhang_Resume.pdf": b"pdf-v1"})
        commit(self.root / "website", {"Daniel_Zhang_Resume.pdf": b"pdf-v1"})
        self.heads["resume"] = git(self.root / "resume", "rev-parse", "HEAD")
        self.heads["website"] = git(self.root / "website", "rev-parse", "HEAD")
        self.write_state()

    def tearDown(self):
        self.tmp.cleanup()

    def write_state(self):
        state = {
            "repos": self.heads,
            "exclude_paths": {
                "resume": ["resume.tex", "Daniel_Zhang_Resume.pdf", "resume-preview.webp", "sync-state.json"],
                "website": ["Daniel_Zhang_Resume.pdf", "images/resume-preview.webp"],
            },
            "ignore": ["old-repo"],
        }
        (self.root / "resume" / "sync-state.json").write_text(json.dumps(state))

    def run_check(self, repos=()):
        return check.check(self.root / "resume", self.root, lambda: list(repos))

    def test_nothing_changed(self):
        self.assertEqual(self.run_check(), ["NOTHING TO SYNC"])

    def test_project_change_is_reported(self):
        commit(self.root / "project", {"README.md": "now with a new feature\n"})
        self.assertEqual(self.run_check(), ["changed project README.md"])

    def test_own_outputs_do_not_wake_the_pipeline(self):
        # What one full cycle commits: résumé edit + state, the Action's PDF build,
        # and the website PDF PR. None of it should count as a change.
        state = (self.root / "resume" / "sync-state.json").read_text()
        commit(self.root / "resume", {"resume.tex": "edited", "sync-state.json": state + "\n"})
        commit(self.root / "resume", {"Daniel_Zhang_Resume.pdf": b"pdf-v2", "resume-preview.webp": b"img"})
        commit(self.root / "website", {"Daniel_Zhang_Resume.pdf": b"pdf-v2", "images/resume-preview.webp": b"img"})
        self.assertEqual(self.run_check(), ["NOTHING TO SYNC"])

    def test_pipeline_docs_change_is_reported(self):
        # The pipeline is itself a project: its docs and code are content, not output.
        commit(self.root / "resume", {"docs/PIPELINE.md": "architecture"})
        self.assertEqual(self.run_check(), ["changed resume docs/PIPELINE.md"])

    def test_stale_website_pdf(self):
        commit(self.root / "resume", {"Daniel_Zhang_Resume.pdf": b"pdf-v2"})
        self.assertEqual(self.run_check(), ["website-pdf stale"])

    def test_unknown_commit_means_review_from_scratch(self):
        self.heads["project"] = "0" * 40
        self.write_state()
        self.assertIn("review from scratch", self.run_check()[0])

    def test_new_repo_found_and_forks_ignored(self):
        repos = [
            {"name": "project", "fork": False, "archived": False},
            {"name": "brand-new", "fork": False, "archived": False},
            {"name": "someone-elses", "fork": True, "archived": False},
            {"name": "old-repo", "fork": False, "archived": False},
        ]
        self.assertEqual(self.run_check(repos), ["new brand-new"])

    def test_repo_list_unavailable_is_not_a_finding(self):
        out = check.check(self.root / "resume", self.root, lambda: None)
        self.assertEqual(out, ["repo-list unavailable", "NOTHING TO SYNC"])

    def test_config_block_for_another_user(self):
        # An installed copy names its own repo, PDF and (optional) website in sync-state.json.
        state = json.loads((self.root / "resume" / "sync-state.json").read_text())
        state["config"] = {"github_user": "someone", "resume_repo": "resume",
                           "pdf_name": "Jane_Doe_Resume.pdf", "website_repo": ""}
        (self.root / "resume" / "sync-state.json").write_text(json.dumps(state))
        commit(self.root / "resume", {"Jane_Doe_Resume.pdf": b"pdf-v1"})
        state["repos"]["resume"] = git(self.root / "resume", "rev-parse", "HEAD")
        state["exclude_paths"]["resume"].append("Jane_Doe_Resume.pdf")
        (self.root / "resume" / "sync-state.json").write_text(json.dumps(state))
        # No website repo configured: a differing PDF elsewhere is not "stale".
        self.assertEqual(self.run_check(), ["NOTHING TO SYNC"])


if __name__ == "__main__":
    unittest.main()
