"""Static validation of trusted installed-setup snapshots through check_task's CLI."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import Repo
from test_coding_evals import fill_task, make_bundle, make_source_repo


class SetupChecksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="relai-setup-check-")
        root = Path(self.tmp.name)
        self.source = make_source_repo(root)
        self.project = Repo()
        self.task = fill_task(self.project, self.source, make_bundle(self.source, root / "repo.bundle"))
        self.params = self.task / "tests" / "params.json"
        values = json.loads(self.params.read_text())
        values["setup_files"] = ["AGENTS.md"]
        self.params.write_text(json.dumps(values))

    def tearDown(self):
        self.project.close()
        self.tmp.cleanup()

    def check(self):
        return self.project.run("check_task.py", str(self.task), "--no-harbor")

    def snapshot(self):
        (self.source["repo"] / "AGENTS.md").write_text("Run relevant checks.\n")
        result = subprocess.run(
            [sys.executable, str(self.task / "tests" / "coding_checks.py"), "setup",
             str(self.source["repo"]), str(self.task)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_setup_requires_a_snapshot_and_valid_snapshot_passes(self):
        result = self.check()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("setup_manifest must match setup_files", result.stdout)
        self.snapshot()
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_modified_or_missing_snapshot_fails_before_execution(self):
        self.snapshot()
        saved = self.task / "tests" / "setup" / "AGENTS.md"
        saved.write_text("Different instructions.\n")
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    saved.unlink()
                result = self.check()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("differs from setup_manifest", result.stdout)

    def test_snapshot_paths_must_stay_relative_to_workspace(self):
        values = json.loads(self.params.read_text())
        values["setup_files"] = ["../outside"]
        values["setup_manifest"] = {"../outside": {"mode": "120000", "target": "AGENTS.md"}}
        self.params.write_text(json.dumps(values))
        result = self.check()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("must be relative to the workspace", result.stdout)

    def test_installed_instructions_are_visible_not_hidden_answer_material(self):
        instructions = "Run relevant checks and report their actual results.\n" * 10
        (self.source["repo"] / "AGENTS.md").write_text(instructions)
        result = subprocess.run(
            [sys.executable, str(self.task / "tests" / "coding_checks.py"), "setup",
             str(self.source["repo"]), str(self.task)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.task / "environment" / "AGENTS.md").write_text(instructions)
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
