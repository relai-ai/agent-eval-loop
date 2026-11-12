#!/usr/bin/env python3
"""Coding-agent hooks for RELAI projects. Standard library only.

Usage (the host passes the hook event as JSON on stdin):
  python3 hooks/relai_hook.py guard-frozen [--host claude|codex]   before a file edit
  python3 hooks/relai_hook.py check-edit [--host claude|codex]     after a file edit

guard-frozen flags an edit to a frozen test. Claude Code asks the user first; Codex cannot ask
from a hook (its PreToolUse supports only allow or deny), so there the edit goes ahead and the
agent is warned instead. check-edit runs the project's own checkers on the edited test or wiki
page and passes any problems back to the agent.

guard-frozen needs only the standard library of any Python 3; check-edit runs the checkers, which need
Python 3.11+. On an older `python3`, check-edit says so once per project (it leaves a marker in
relai/work/) instead of failing silently.

Hooks are a convenience for hosts that support them. The guarantees they serve live in the
project's relai/README.md and its checkers, which work without them. Both hooks do nothing
outside a RELAI project, and fail open: an unexpected error never blocks the user's work.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HOSTS = ("claude", "codex")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PATCH_TOOLS = {"apply_patch"}  # Codex: tool_input.command holds the patch text
PATCH_PATH = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+?)\s*$", re.MULTILINE)
JUNK_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", ".nox",
             "node_modules", ".venv", "venv", ".git", ".hg", ".svn"}
CHECK_TIMEOUT_SEC = 45
MAX_REPORT_CHARS = 4000


def edited_paths(event: dict) -> list[Path]:
    """The files an edit tool call touches, as absolute paths."""
    tool, tool_input = event.get("tool_name"), event.get("tool_input") or {}
    if tool in EDIT_TOOLS:
        raw = [tool_input.get("file_path") or tool_input.get("notebook_path")]
    elif tool in PATCH_TOOLS:
        raw = PATCH_PATH.findall(str(tool_input.get("command") or tool_input.get("patch") or ""))
    else:
        return []
    cwd = Path(event.get("cwd") or ".")
    paths = []
    for item in raw:
        if not item:
            continue
        path = Path(item)
        path = (path if path.is_absolute() else cwd / path).resolve()
        if path not in paths:
            paths.append(path)
    return paths


def relai_dir_of(path: Path) -> Path | None:
    """The installed relai/ directory containing path: an ancestor named relai with bin/ or relai.toml."""
    for parent in path.parents:
        if parent.name == "relai" and ((parent / "bin").is_dir() or (parent / "relai.toml").is_file()):
            return parent
    return None


def task_dir_of(path: Path, relai_dir: Path) -> Path | None:
    """The test holding path: the nearest ancestor under relai/tests or relai/benchmarks with a task.toml."""
    rel = path.relative_to(relai_dir)
    if not rel.parts or rel.parts[0] not in ("tests", "benchmarks"):
        return None
    for parent in [path, *path.parents]:
        if parent == relai_dir:
            return None
        if (parent / "task.toml").is_file():
            return parent
    return None


def frozen_entry(path: Path, relai_dir: Path) -> tuple[str, dict] | None:
    """The frozen.json entry covering path, keyed by the test's path relative to relai/."""
    frozen_file = relai_dir / "frozen.json"
    if not frozen_file.is_file():
        return None
    tests = json.loads(frozen_file.read_text(encoding="utf-8")).get("tests") or {}
    rel = path.relative_to(relai_dir)
    for depth in range(len(rel.parts) - 1, 0, -1):
        key = Path(*rel.parts[:depth]).as_posix()
        if key in tests:
            inside = rel.parts[depth:]
            if inside == ("README.md",) or any(part in JUNK_DIRS for part in inside[:-1]):
                return None  # outside the digest: editing it does not change the frozen test
            return key, tests[key]
    return None


def guard_frozen(event: dict, host: str) -> dict | None:
    hits = {}
    for path in edited_paths(event):
        relai_dir = relai_dir_of(path)
        found = relai_dir and frozen_entry(path, relai_dir)
        if found:
            hits.setdefault(found[0], found[1])
    if not hits:
        return None
    if all(entry.get("repair") for entry in hits.values()):
        reasons = "; ".join(f"{key}: {entry['repair'].get('reason', '')}" for key, entry in hits.items())
        context = (f"RELAI: editing a frozen test under an open repair ({reasons}). When done, re-freeze with "
                   "`freeze.py --reason`, record it in relai/decisions.md and get a fresh review.")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": context}}
    tests = "; ".join(f"{key} (frozen {str(entry.get('frozen_at', '')).split('T')[0] or 'earlier'})"
                      for key, entry in hits.items())
    rule = ("Changing a frozen test changes what its scores mean, so results before and after are no "
            "longer comparable. A justified repair needs a reason recorded with `freeze.py --reason`, a line "
            "in relai/decisions.md and a fresh review (relai/README.md, Fixed rules: frozen tests). A low score "
            "alone does not show the test is wrong. Once a repair is agreed, `freeze.py <test> --begin-repair "
            "--reason \"...\"` stops this check asking before each edit until the test is re-frozen.")
    if host == "codex":
        # Codex cannot ask the user from a hook, so the edit goes ahead and the agent is told.
        context = (f"RELAI warning: this edit changes a frozen test: {tests} (relai/frozen.json). {rule} "
                   "If the user has not agreed to this repair, tell them now that the test changed, and "
                   "revert the edit if they do not want it.")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": context}}
    reason = f"RELAI: this edit changes a frozen test: {tests} (relai/frozen.json). {rule}"
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
        "additionalContext": reason,
    }}


def run_checker(relai_dir: Path, script: str, *args: str) -> str | None:
    """Run the project's own copy of a checker; return its report when it finds errors."""
    checker = relai_dir / "bin" / script
    if not checker.is_file():
        return None
    try:
        result = subprocess.run([sys.executable, str(checker), *args], capture_output=True, text=True,
                                cwd=relai_dir.parent, timeout=CHECK_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        command = " ".join(["python3", f"relai/bin/{script}", *args])
        return f"`{command}` did not finish within {CHECK_TIMEOUT_SEC}s, so it was not checked; run it yourself."
    if result.returncode == 0:
        return None
    report = (result.stdout + result.stderr).strip()
    if len(report) > MAX_REPORT_CHARS:
        report = report[:MAX_REPORT_CHARS] + "\n[... truncated; run the command for the full report]"
    command = " ".join(["python3", f"relai/bin/{script}", *args])
    return f"`{command}` reported problems:\n{report}"


def check_edit(event: dict, host: str) -> dict | None:
    checks: dict[tuple, tuple] = {}  # (relai dir, script, args) in first-seen order
    edited = []
    for path in edited_paths(event):
        relai_dir = relai_dir_of(path)
        if not relai_dir:
            continue
        edited.append(path.relative_to(relai_dir.parent).as_posix())
        task = task_dir_of(path, relai_dir)
        if task:
            task_arg = task.relative_to(relai_dir.parent).as_posix()
            checks.setdefault((relai_dir, "check_task.py", task_arg, "--no-harbor"), ())
        # Tests cite wiki ids in [metadata.relai].covers, so a task.toml edit can break the wiki check too.
        if path.relative_to(relai_dir).parts[:1] == ("wiki",) or (task and path.name == "task.toml"):
            checks.setdefault((relai_dir, "check_wiki.py"), ())
    reports = [r for r in (run_checker(*key) for key in checks) if r]
    if not reports:
        return None
    context = (f"RELAI checkers report current problems in the test or wiki you edited ({', '.join(edited)}). "
               "Some may predate this edit or belong to work still in progress; fix them before you finish, "
               "or say why they do not apply:\n\n" + "\n\n".join(reports))
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}


def old_python_notice(event: dict, host: str) -> dict | None:
    """Once per RELAI project: the checkers cannot run on this python3, so say so rather than stay silent."""
    for path in edited_paths(event):
        relai_dir = relai_dir_of(path)
        if not relai_dir:
            continue
        marker = relai_dir / "work" / ".hook-python-notice"
        if marker.exists():
            return None
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{sys.executable} {sys.version.split()[0]}\n", encoding="utf-8")
        found = ".".join(map(str, sys.version_info[:3]))
        message = (f"RELAI: the hook's python3 is {found}, and the checkers need Python 3.11+, so edits under relai/ "
                   "are not checked automatically (frozen tests are still guarded). Put Python 3.11+ first on PATH "
                   "as python3, or run relai/bin's checkers yourself with a newer Python. This notice is shown once "
                   "(delete relai/work/.hook-python-notice to see it again).")
        return {"systemMessage": message,
                "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}
    return None


HOOKS = {"guard-frozen": guard_frozen, "check-edit": check_edit}


def main() -> int:
    args = sys.argv[1:]
    host = "claude"
    if len(args) == 3 and args[1] == "--host" and args[2] in HOSTS:
        host = args[2]
        args = args[:1]
    if len(args) != 1 or args[0] not in HOOKS:
        print(__doc__, file=sys.stderr)
        return 0
    hook = HOOKS[args[0]]
    if hook is check_edit and sys.version_info < (3, 11):
        hook = old_python_notice  # the checkers need Python 3.11+; tell the user once instead of failing
    try:
        output = hook(json.load(sys.stdin), host)
    except Exception:  # fail open: a hook must never block work because of its own error
        return 0
    if output:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
