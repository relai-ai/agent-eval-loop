"""Consistency checks across the plugin's own files. Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import json
import re
import unittest
from urllib.parse import unquote, urlsplit

from helpers import EXAMPLES, PLUGIN, TEMPLATE

MANIFESTS = ["plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"]


def guidance():
    return sorted([*PLUGIN.glob("skills/**/*.md"), PLUGIN / "README.md", PLUGIN / "DESIGN.md"])


class PluginTest(unittest.TestCase):
    def test_versions_agree(self):
        versions = {name: json.loads((PLUGIN / name).read_text())["version"] for name in MANIFESTS}
        market = json.loads((PLUGIN / ".claude-plugin/marketplace.json").read_text())
        versions["marketplace"] = market["plugins"][0]["version"]
        header = re.match(r"<!-- relai (\S+) -->", (TEMPLATE / "README.md").read_text())
        versions["template README"] = header and header.group(1)
        self.assertEqual(len(set(versions.values())), 1, versions)

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
