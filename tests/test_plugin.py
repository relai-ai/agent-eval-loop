"""Consistency checks across the plugin's own files. Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import importlib.util
import re
import unittest
from urllib.parse import unquote, urlsplit

from helpers import EXAMPLES, PLUGIN, TEMPLATE

spec = importlib.util.spec_from_file_location("relai_release", PLUGIN / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def guidance():
    return sorted([*PLUGIN.glob("skills/**/*.md"), *PLUGIN.glob("*.md")])


class PluginTest(unittest.TestCase):
    def test_versions_agree(self):
        release.check(PLUGIN)

    def test_referenced_files_exist(self):
        missing = []
        for doc in guidance():
            text = doc.read_text()
            for name in re.findall(r"relai/docs/([\w-]+\.md)", text):
                if not (TEMPLATE / "docs" / name).is_file():
                    missing.append(f"{doc.relative_to(PLUGIN)}: relai/docs/{name}")
            for target in re.findall(r"\]\(([^\s)]+)\)", text):
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                if not (doc.parent / unquote(parsed.path)).exists():
                    missing.append(f"{doc.relative_to(PLUGIN)}: {target}")
        for name in ("judge.py", "triage.py", "native_runner.py", "launcher.py", "harbor_agent.py", "evaluate.py"):
            if not (EXAMPLES / name).is_file():
                missing.append(f"examples/{name}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
