#!/usr/bin/env python3
"""Build run copies of frozen coding tasks with a team's setup installed, without changing the tasks.

Usage:
  python3 relai/bin/apply_setup.py <setup id> relai/tests/<id> [...]
  python3 relai/bin/apply_setup.py <setup id> relai/tests/<id> [...] --setup-root <another relai/>

Reads `[[coding_evals.setups]]` with that id from relai.toml: `path` holds the files installed into
the workspace, laid out as in a repository root, and `skills` lists the user-level skill
directories the agent gets. Both are relative to relai/, or to --setup-root when the files being
tried live elsewhere, such as a candidate worktree's relai/.

For each task it writes relai/work/setups/<setup id>-<digest>/<test key>/: the frozen task, one
added Dockerfile line that copies the workspace files in, and the installed-state manifest and
snapshots the verifier needs (`setup_files`, `setup_manifest`, `tests/setup/`), written by the
task's own coding_checks.py. Listed skills are copied to .../skills/<name>/; pass each to the
runner (Harbor: `--skill <dir>`). relai-setup.json in that folder records the setup digest and
each task's frozen digest, which summarize.py reports.

A task must be frozen and unchanged, and must not already install a setup. The frozen task is
never written to. Exit status: 0 built, 1 a task was refused, 2 a usage or environment error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (JUNK_DIRS, SETUP_RECORD, dir_digest, evals_config, fail, frozen_state, load_json,
                     relai_root, test_key)

INSTALL_DIR = "relai-setup"


def setup_entries(root: Path) -> list[Path]:
    """Files and symlinks under root, in a stable order; a symlink is an entry, never followed."""
    found = []
    for current, dirs, files in os.walk(root):
        links = [d for d in dirs if (Path(current) / d).is_symlink()]
        dirs[:] = sorted(d for d in dirs if d != ".git" and d not in links)
        found += [Path(current) / name for name in sorted(files + links)]
    return sorted(found)


def tree_digest(digest, label: str, root: Path) -> None:
    for path in setup_entries(root):
        digest.update(f"{label}/{path.relative_to(root).as_posix()}".encode() + b"\0")
        if path.is_symlink():
            digest.update(b"link\0" + os.readlink(path).encode())
        else:
            digest.update((b"exec\0" if path.stat().st_mode & 0o111 else b"file\0") + path.read_bytes())
        digest.update(b"\0")


def declared_setup(config: dict, setup_id: str) -> dict:
    coding = config.get("coding_evals")
    setups = coding.get("setups") if isinstance(coding, dict) else None
    for entry in setups if isinstance(setups, list) else []:
        if isinstance(entry, dict) and entry.get("id") == setup_id:
            return entry
    fail(f"relai.toml has no [[coding_evals.setups]] with id {setup_id!r}")


def resolve_sources(entry: dict, root: Path) -> tuple[Path | None, dict[str, Path]]:
    path, skills = entry.get("path"), entry.get("skills", [])
    if path is not None and not isinstance(path, str):
        fail("[[coding_evals.setups]].path must be a string")
    if not isinstance(skills, list) or any(not isinstance(s, str) or not s for s in skills):
        fail("[[coding_evals.setups]].skills must be a list of skill directories")
    root = root.resolve()
    workspace = (root / path).resolve() if path else None
    if workspace is not None and not workspace.is_dir():
        fail(f"setup path {workspace} is not a directory")
    if workspace is not None and not workspace.is_relative_to(root):
        fail(f"setup path {path} leaves {root}; keep setups inside relai/")
    named: dict[str, Path] = {}
    for raw in skills:
        skill = (root / raw).resolve()
        if not skill.is_relative_to(root):
            fail(f"skill {raw} leaves {root}; copy the skill inside relai/ first")
        if not (skill / "SKILL.md").is_file():
            fail(f"skill {skill} has no SKILL.md")
        if workspace is not None and skill.is_relative_to(workspace):
            fail(f"skill {raw} is inside the setup's path, so it would also be installed into the workspace; "
                 "keep user-level skills outside it")
        if skill.name in named:
            fail(f"two listed skills are named {skill.name}")
        named[skill.name] = skill
    return workspace, named


def last_user(dockerfile: str) -> str | None:
    users = re.findall(r"^[ \t]*USER[ \t]+(\S+)", dockerfile, flags=re.IGNORECASE | re.MULTILINE)
    user = users[-1] if users else None
    return None if user in (None, "root", "0", "root:root", "0:0") else user


def copy_task(task: Path, dest: Path) -> None:
    """Copy the task; large build inputs under environment/ are hard-linked when the filesystem allows."""
    environment = task / "environment"

    def copy(source: str, target: str) -> None:
        path = Path(source)
        if path.is_relative_to(environment) and path.name != "Dockerfile" and not path.is_symlink():
            try:
                os.link(source, target)
                return
            except OSError:
                pass
        shutil.copy2(source, target, follow_symlinks=False)

    shutil.copytree(task, dest, symlinks=True, copy_function=copy, ignore=shutil.ignore_patterns(*JUNK_DIRS))


def install(dest: Path, workspace: Path, files: list[str]) -> str | None:
    """Add the workspace files to the copy's build context and manifest. Returns an error, or None."""
    params_path = dest / "tests" / "params.json"
    params = load_json(params_path)
    dockerfile_path = dest / "environment" / "Dockerfile"
    context = dest / "environment" / INSTALL_DIR
    if not dockerfile_path.is_file():
        return "it has no environment/Dockerfile to install the setup with"
    if context.exists():
        return f"environment/{INSTALL_DIR} already exists in the task"
    for rel in files:
        target = context / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace / rel, target, follow_symlinks=False)
    dockerfile = dockerfile_path.read_text(encoding="utf-8")
    user = last_user(dockerfile)
    chown = f"--chown={user} " if user else ""
    target_dir = str(params.get("workspace") or "/app").rstrip("/") + "/"
    line = f"COPY {chown}{json.dumps([INSTALL_DIR + '/', target_dir])}\n"
    dockerfile_path.write_text(dockerfile + ("" if dockerfile.endswith("\n") else "\n") + line, encoding="utf-8")
    params["setup_files"] = files
    params_path.write_text(json.dumps(params, indent=1) + "\n", encoding="utf-8")
    ran = subprocess.run([sys.executable, "-I", str(dest / "tests" / "coding_checks.py"), "setup",
                          str(workspace), str(dest)], capture_output=True, text=True)
    manifest = load_json(params_path).get("setup_manifest") if ran.returncode == 0 else None
    if not isinstance(manifest, dict) or set(manifest) != set(files):
        detail = (ran.stderr or ran.stdout).strip().splitlines()[-1:] or ["no manifest was written"]
        return ("its tests/coding_checks.py could not record the installed setup "
                f"({detail[0]}); update that verifier copy under the Frozen tests rule")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("setup", help="id of a [[coding_evals.setups]] entry")
    parser.add_argument("tasks", nargs="+", help="frozen coding task directories")
    parser.add_argument("--setup-root", help="read the setup's path and skills relative to this relai/ directory")
    parser.add_argument("--relai-dir")
    args = parser.parse_args()
    relai_dir = relai_root(args.relai_dir)
    entry = declared_setup(evals_config(relai_dir), args.setup)
    workspace, skills = resolve_sources(entry, Path(args.setup_root).resolve() if args.setup_root else relai_dir)
    files = [p.relative_to(workspace).as_posix() for p in setup_entries(workspace)] if workspace else []
    if not files and not skills:
        fail(f"setup {args.setup!r} has no workspace files and no skills to apply")

    digest = hashlib.sha256()
    if workspace:
        tree_digest(digest, "workspace", workspace)
    for name, skill in sorted(skills.items()):
        tree_digest(digest, f"skill/{name}", skill)
    setup_digest = digest.hexdigest()
    run_root = relai_dir / "work" / "setups" / f"{args.setup}-{setup_digest[:12]}"
    record_path = run_root / SETUP_RECORD
    record = load_json(record_path) if record_path.is_file() else {}
    tests = record.get("tests") if isinstance(record.get("tests"), dict) else {}
    frozen = frozen_state(relai_dir).get("tests", {})

    status = 0
    for raw in args.tasks:
        task = Path(raw).resolve()
        key = test_key(task, relai_dir)
        frozen_entry = frozen.get(key)
        problem = None
        if not (task / "task.toml").is_file() or not (task / "tests" / "params.json").is_file():
            problem = "it is not a coding task (task.toml and tests/params.json)"
        elif not frozen_entry:
            problem = "it is not frozen; freeze it first"
        elif dir_digest(task) != frozen_entry.get("digest"):
            problem = "it changed since it was frozen; settle that under the Frozen tests rule first"
        elif load_json(task / "tests" / "params.json").get("setup_files"):
            problem = "it already installs a setup; apply setups to the task without one"
        dest = run_root / key
        if problem is None:
            if dest.exists():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            copy_task(task, dest)
            problem = install(dest, workspace, files) if files else None
            if problem is not None:
                shutil.rmtree(dest)
        if problem is not None:
            print(f"error: {key}: {problem}", file=sys.stderr)
            tests.pop(key, None)
            status = 1
            continue
        tests[key] = {"source_digest": frozen_entry["digest"], "run_digest": dir_digest(dest)}
        print(f"{key}: {dest}")

    if tests:
        for name, skill in skills.items():
            target = run_root / "skills" / name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(skill, target, symlinks=True, ignore=shutil.ignore_patterns(".git"))
            print(f"skill {name}: {target}")
        run_root.mkdir(parents=True, exist_ok=True)
        record_path.write_text(json.dumps({
            "setup": args.setup, "digest": setup_digest, "files": files, "skills": sorted(skills),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tests": tests,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main())
