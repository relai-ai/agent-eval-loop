"""Exercise CI reporting with synthetic tests, without rerunning the real suite."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "ci_runner", Path(__file__).resolve().parents[1] / ".github" / "scripts" / "run_tests.py"
)
ci_runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_runner)


class CiRunnerTest(unittest.TestCase):
    def run_fixture(self, case):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(case)
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            # Job summaries append without destroying earlier step output.
            summary.write_text("Earlier output\n", encoding="utf-8")
            output = io.StringIO()
            status = ci_runner.run_tests(suite, summary, output)
            return status, summary.read_text(encoding="utf-8"), output.getvalue()

    def test_skips_are_visible_with_reasons_and_do_not_fail_otherwise_passing_tests(self):
        class Fixture(unittest.TestCase):
            def test_pass(self):
                pass

            def test_skip(self):
                self.skipTest("needs <engine>\nwith `special` characters")

        status, summary, output = self.run_fixture(Fixture)
        self.assertEqual(status, 0)
        self.assertTrue(summary.startswith("Earlier output\n"))
        self.assertIn("**Passed**", summary)
        self.assertIn("test_skip", summary)
        self.assertIn("needs &lt;engine&gt; with `special` characters", summary)
        self.assertIn("do not establish integration coverage", summary)
        self.assertIn("skipped", output)

    def test_failures_and_import_errors_fail_the_run_and_still_write_a_summary(self):
        class Fixture(unittest.TestCase):
            def test_fail(self):
                self.fail("synthetic failure")

            def test_import_error(self):
                raise ImportError("synthetic import error")

        status, summary, output = self.run_fixture(Fixture)
        self.assertEqual(status, 1)
        self.assertIn("**Failed**", summary)
        self.assertIn("| Failures | 1 |", summary)
        self.assertIn("| Errors | 1 |", summary)
        self.assertIn("synthetic failure", output)
        self.assertIn("synthetic import error", output)

    def test_empty_discovery_fails(self):
        status = ci_runner.run_tests(unittest.TestSuite(), stream=io.StringIO())
        self.assertEqual(status, 1)
