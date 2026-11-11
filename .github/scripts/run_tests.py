"""Run the existing unittest suite and summarize skips in GitHub Actions."""

from __future__ import annotations

import html
import os
from pathlib import Path
import sys
import unittest


def run_tests(suite: unittest.TestSuite, summary_path: Path | None = None, stream=None) -> int:
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    successful = result.wasSuccessful() and result.testsRun > 0
    lines = [
        "## Tests and manifest checks",
        "",
        f"**{'Passed' if successful else 'Failed'}** on Python {sys.version.split()[0]}.",
        "",
        "| Result | Count |",
        "| --- | ---: |",
        f"| Tests run (including skips) | {result.testsRun} |",
        f"| Failures | {len(result.failures)} |",
        f"| Errors | {len(result.errors)} |",
        f"| Skipped | {len(result.skipped)} |",
        f"| Expected failures | {len(result.expectedFailures)} |",
        f"| Unexpected successes | {len(result.unexpectedSuccesses)} |",
        "",
        "### Skipped tests",
        "",
    ]
    if result.skipped:
        lines.append("Skipped tests did not execute and do not establish integration coverage.")
        lines.append("")
        for test, reason in result.skipped:
            test_id = html.escape(test.id())
            reason_text = html.escape(" ".join(reason.splitlines()))
            lines.append(f"- <code>{test_id}</code>: <code>{reason_text}</code>")
    else:
        lines.append("None.")
    if result.testsRun == 0:
        lines.extend(["", "No tests were discovered; failing rather than reporting success."])
    if summary_path is not None:
        with summary_path.open("a", encoding="utf-8") as summary:
            summary.write("\n".join(lines) + "\n")
    return 0 if successful else 1


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    sys.exit(run_tests(suite, Path(summary_file) if summary_file else None))
