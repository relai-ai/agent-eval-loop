"""Prepare and validate RELAI release metadata and local snapshots; never pushes or publishes."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
TEMPLATE = "skills/start/template/README.md"
VERSION_FILES = (*MANIFESTS, TEMPLATE, "pyproject.toml", "uv.lock")


def version_tuple(value: str) -> tuple[int, ...]:
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise ValueError("version must be X.Y.Z, with no prefix, leading zeros, or suffix")
    return tuple(map(int, value.split(".")))


def versions(root: Path) -> dict[str, str]:
    values = {name: json.loads((root / name).read_text(encoding="utf-8"))["version"] for name in MANIFESTS}
    header = re.match(r"<!-- relai (\S+) -->", (root / TEMPLATE).read_text(encoding="utf-8"))
    if not header:
        raise ValueError("template README is missing its RELAI version marker")
    values[TEMPLATE] = header.group(1)
    values["pyproject.toml"] = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    values["uv.lock"] = next(p["version"] for p in lock["package"]
                               if p["name"] == "agent-eval-loop" and p.get("source") == {"virtual": "."})
    return values


def check(root: Path, expected: str | None = None) -> str:
    values = versions(root)
    current = values["plugin.json"]
    version_tuple(current)
    if set(values.values()) != {current}:
        raise ValueError(f"release versions disagree: {values}")
    if expected is not None and current != expected:
        raise ValueError(f"requested version {expected} does not match {current}")
    return current


def next_version(current: str) -> str:
    major, minor, patch = version_tuple(current)
    return f"{major}.{minor}.{patch + 1}"


def replace_one(pattern: str, replacement: str, text: str) -> str:
    result, count = re.subn(pattern, lambda _: replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"expected one version field matching {pattern!r}; found {count}")
    return result


def replace_toml_version(text: str, table_pattern: str, version: str) -> str:
    matches = list(re.finditer(table_pattern, text, re.MULTILINE | re.DOTALL))
    if len(matches) != 1:
        raise ValueError("cannot identify the project's TOML version table")
    match = matches[0]
    table = replace_one(r'^version = "[^"\n]+"$', f'version = "{version}"', match.group())
    return text[:match.start()] + table + text[match.end():]


def bump(root: Path, target: str, dry_run: bool = False) -> None:
    current = check(root)
    if version_tuple(target) <= version_tuple(current):
        raise ValueError(f"new version must be greater than {current}")
    updates = {}
    for name in MANIFESTS:
        updates[name] = replace_one(r'"version": "' + re.escape(current) + r'"',
                                   f'"version": "{target}"', (root / name).read_text(encoding="utf-8"))
    updates[TEMPLATE] = replace_one(r"^<!-- relai \S+ -->", f"<!-- relai {target} -->",
                                    (root / TEMPLATE).read_text(encoding="utf-8"))
    updates["pyproject.toml"] = replace_toml_version(
        (root / "pyproject.toml").read_text(encoding="utf-8"), r"^\[project\]\n.*?(?=^\[|\Z)", target)
    updates["uv.lock"] = replace_toml_version(
        (root / "uv.lock").read_text(encoding="utf-8"),
        r'^\[\[package\]\]\nname = "agent-eval-loop"\n.*?(?=^\[\[package\]\]|\Z)', target)
    # Validate every replacement before writing any file; dependency entries stay unchanged.
    for name, content in updates.items():
        if not dry_run:
            (root / name).write_text(content, encoding="utf-8")
        print(f"{'Would update' if dry_run else 'Updated'} {name}")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def prepare(root: Path, requested: str | None = None) -> dict[str, str]:
    """Build a local version-bump commit from the selected main revision."""
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("prepare requires a clean tracked checkout")
    source = git(root, "rev-parse", "HEAD")
    current = check(root)
    target = requested or next_version(current)
    if version_tuple(target) <= version_tuple(current):
        raise ValueError(f"release version must be greater than {current}")
    tag = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/tags/v{target}"], cwd=root)
    if tag.returncode == 0:
        raise ValueError(f"tag v{target} already exists")
    if tag.returncode != 1:
        raise ValueError("cannot check existing release tags")
    with redirect_stdout(sys.stderr):
        bump(root, target)
    git(root, "add", "--", *VERSION_FILES)
    tree = git(root, "write-tree")
    parents = ["-p", source]
    sha = git(root, "-c", "commit.gpgsign=false", "commit-tree", tree, *parents,
              "-m", f"Release RELAI {target}\n\nSource-main: {source}")
    git(root, "checkout", "-q", "--detach", sha)
    return {"version": target, "sha": sha, "source_sha": source}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    edit = sub.add_parser("bump", help="update metadata locally without committing")
    edit.add_argument("version")
    edit.add_argument("--dry-run", action="store_true")
    snapshot = sub.add_parser("prepare", help="create a local release snapshot from the clean checkout")
    snapshot.add_argument("version", nargs="?", default="", help="default: patch above the last release")
    verify = sub.add_parser("check", help="check version consistency")
    verify.add_argument("--version")
    args = parser.parse_args()
    try:
        if args.command == "bump":
            bump(ROOT, args.version, args.dry_run)
        elif args.command == "prepare":
            for name, value in prepare(ROOT, args.version).items():
                print(f"{name}={value}")
        else:
            print(f"RELAI {check(ROOT, args.version)}: release checks passed")
    except (ValueError, KeyError, StopIteration, OSError, subprocess.CalledProcessError) as error:
        print(f"Release check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
