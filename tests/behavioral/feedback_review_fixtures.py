"""Prepare one isolated feedback-review pilot; runs no agent or app."""

import argparse
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("analysis", "handoff", "app-review"))
    parser.add_argument("destination", type=Path, help="new directory outside the plugin checkout")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    destination = args.destination.resolve()
    if destination == repo or repo in destination.parents:
        parser.error("use a destination outside the plugin checkout")
    destination.mkdir(parents=True, exist_ok=False)
    fixtures = json.loads(Path(__file__).with_name("feedback-review-fixtures.json").read_text())
    case = fixtures[args.case]
    shutil.copytree(repo / "skills", destination / "plugin" / "skills")
    project = destination / "project"
    for relative, content in case["files"].items():
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    if args.case != "analysis":
        shutil.copy(repo / "skills/start/template/README.md", project / "relai/README.md")
    # Keep the continuation outside the project until the evaluator supplies it.
    for relative, content in case.get("reply_files", {}).items():
        path = destination / "continuation" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    print(f"Workspace: {project}\nSkills: {destination / 'plugin/skills'}\nTask: {case['task']}")
    if "reply" in case:
        print(f"After the first handoff, supply this reply: {case['reply']}")


if __name__ == "__main__":
    main()
