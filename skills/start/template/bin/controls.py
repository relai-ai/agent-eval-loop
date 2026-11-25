#!/usr/bin/env python3
"""Run an agent-neutral coding task's controls in fresh, offline containers before freezing it.

Usage:
  python3 relai/bin/controls.py relai/tests/<id> [--engine docker|podman] [--only ID[,ID...]] [--plan]

Each control starts a new container from the image of the task's environment/ with no network and the
task's CPUs and memory, changes the workspace, runs tests/test.sh as the verifier does, and compares
/logs/verifier/reward.json with what the control expects:

  start           the untouched start: the primary check at its min_score.
  reference       solution/solve.sh: every code check at its max_score.
  first-command   the agent's first test command, run as [agent].user in the workspace before any change,
                  must finish within its timeout and be runnable (exit 126 or 127 fails it; failing tests
                  are expected, since the bug is there). It is controls.json's first_command (default
                  timeout 300 s), or the suite command, run as root as the verifier runs it, as a stand-in
                  when none is declared.
  shadow-imports  for Python hidden tests: a module named after each top-level module they import, planted
                  at the workspace root and beside each hidden test, exits 0 when imported; the primary
                  check must stay at its min_score on the untouched start.
  <id>            each control in controls/controls.json: solution/solve.sh first when "solve" is true,
                  then its patch from controls/, then the scores in "expect" must hold. A control with
                  "hide": true also runs once per hiding method, which hides the files its patch changes
                  from tools that honor ignore files: <id>/git-exclude (a .git/info/exclude in their
                  folder), <id>/root-exclude (the workspace's .git/info/exclude), <id>/ignore-files
                  (.gitignore, .ignore, .rgignore, .prettierignore and .eslintignore beside them) and
                  <id>/nested-repo (their folder made a git repository whose .gitignore lists them).

controls/controls.json (the coding-evals skill, task-format.md *Validation*):
  {"first_command": {"command": "npm run test:unit", "timeout_sec": 600},
   "controls": [{"id": "regression", "solve": true, "patch": "regression.patch", "expect": {"no-regressions": 0}},
                {"id": "unformatted", "solve": true, "patch": "unformatted.patch", "expect": {"formatted": 0},
                 "hide": true}]}

--plan prints each control and the shell commands it runs, and runs nothing. Otherwise it writes
relai/work/controls/<test key>.json with the task's digest and every control's scores and verdict, which
freeze.py --require-controls reads, and exits 1 when a control fails. It needs a docker- or
podman-compatible container engine, removes its containers, and calls no model.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    HIDING_METHODS, controls_record, declared_evaluators, dir_digest, load_controls, load_json, load_toml,
    relai_root, test_key,
)

FIRST_COMMAND_TIMEOUT = 300
IGNORE_FILES = (".gitignore", ".ignore", ".rgignore", ".prettierignore", ".eslintignore")
SHADOW = "import os\nos._exit(0)\n"


class Engine:
    """A docker- or podman-compatible CLI."""

    def __init__(self, cli: str):
        self.cli = cli

    def call(self, *args: str, timeout: float | None = None) -> tuple[int | None, str]:
        try:
            proc = subprocess.run([self.cli, *args], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, f"timed out after {timeout} s"
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def build(self, context: Path, tag: str) -> None:
        code, out = self.call("build", "-t", tag, "-f", str(context / "Dockerfile"), str(context))
        if code != 0:
            raise RuntimeError(f"building environment/ failed: {out.strip()[-800:]}")

    def start(self, image: str, cpus: float | None, memory_mb: int | None) -> str:
        name = f"relai-controls-{uuid.uuid4().hex[:12]}"
        limits = ([f"--cpus={cpus}"] if cpus else []) + ([f"--memory={memory_mb}m"] if memory_mb else [])
        code, out = self.call("run", "-d", "--name", name, "--network", "none", *limits, "--entrypoint", "sleep",
                              image, "infinity")
        if code != 0:
            raise RuntimeError(f"starting a container failed: {out.strip()[-500:]}")
        return name

    def copy(self, name: str, source: Path, dest: str) -> None:
        code, out = self.call("cp", f"{source}/.", f"{name}:{dest}")
        if code != 0:
            raise RuntimeError(f"copying {source.name}/ into the container failed: {out.strip()[-300:]}")

    def run(self, name: str, script: str, user: str = "root", workdir: str | None = None,
            timeout: float | None = None) -> tuple[int | None, str]:
        args = ["exec", "-u", user] + (["-w", workdir] if workdir else []) + [name, "bash", "-lc", script]
        return self.call(*args, timeout=timeout)

    def remove(self, name: str) -> None:
        self.call("rm", "-f", name)


def find_engine(requested: str | None) -> Engine:
    for cli in [requested] if requested else ["docker", "podman"]:
        if cli and shutil.which(cli) and subprocess.run([cli, "info"], capture_output=True).returncode == 0:
            return Engine(cli)
    raise SystemExit("error: no running docker- or podman-compatible container engine (name one with --engine)")


def changed_files(patch: str) -> list[str]:
    """The paths a unified diff creates or modifies."""
    paths = []
    for line in patch.splitlines():
        if line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            path = line[4:].split("\t")[0].strip()
            paths.append(path[2:] if path.startswith("b/") else path)
    return list(dict.fromkeys(paths))


def hiding_script(method: str, files: list[str]) -> str:
    """Shell commands, run in the workspace, that hide these files with one hiding method."""
    lines = []
    for path in files:
        folder, name = (path.rsplit("/", 1) if "/" in path else (".", path))
        q_folder, q_name, q_path = shlex.quote(folder), shlex.quote(name), shlex.quote(path)
        if method == "git-exclude":
            lines += [f"mkdir -p {q_folder}/.git/info",
                      f"[ -e {q_folder}/.git/HEAD ] || printf 'ref: refs/heads/main\\n' > {q_folder}/.git/HEAD",
                      f"printf '%s\\n' {q_name} >> {q_folder}/.git/info/exclude"]
        elif method == "root-exclude":
            lines += ["mkdir -p .git/info", f"printf '%s\\n' {q_path} >> .git/info/exclude"]
        elif method == "ignore-files":
            lines += [f"printf '%s\\n' {q_name} >> {q_folder}/{ignore}" for ignore in IGNORE_FILES]
        elif method == "nested-repo":
            if folder != ".":
                lines.append(f"[ -e {q_folder}/.git ] || git init -q {q_folder}")
            lines.append(f"printf '%s\\n' {q_name} >> {q_folder}/.gitignore")
        else:
            raise ValueError(f"unknown hiding method {method!r}")
    return "\n".join(lines)


def shadow_plan(task: Path, params: dict) -> list[str]:
    """Workspace paths of modules that shadow what the Python hidden tests import, or [] when there are none."""
    hidden = (params.get("hidden_tests") or {}).get("files") or {}
    names, folders = set(), {"."}
    for source, target in hidden.items():
        if not str(source).endswith(".py"):
            continue
        try:
            tree = ast.parse((task / "tests" / source).read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
        folders.add(str(target).rsplit("/", 1)[0] if "/" in str(target) else ".")
    names.discard("__future__")
    return sorted(f"{folder}/{name}.py" if folder != "." else f"{name}.py" for folder in folders for name in names)


def shadow_script(paths: list[str]) -> str:
    body = shlex.quote(SHADOW)
    return "\n".join(f"[ -e {shlex.quote(p)} ] || printf '%s' {body} > {shlex.quote(p)}" for p in paths)


def plan(task: Path) -> tuple[dict, list[dict]]:
    """The task's settings and every control to run: id, steps (solve, patch, script), expectation and kind."""
    toml = load_toml(task / "task.toml")
    params = load_json(task / "tests" / "params.json")
    config, problems = load_controls(task)
    if problems:
        raise SystemExit("error: " + "; ".join(problems))
    coding = (toml.get("metadata", {}).get("relai", {}) or {}).get("coding") or {}
    evaluators = [ev for ev in declared_evaluators(toml) if ev.get("type") == "code"]
    primary = coding.get("primary")
    low = {ev["id"]: ev.get("min_score", 0.0) for ev in evaluators}
    high = {ev["id"]: ev.get("max_score", 1.0) for ev in evaluators}
    settings = {"workspace": params.get("workspace") or coding.get("workspace") or "/app",
                "agent_user": (toml.get("agent") or {}).get("user") or "root",
                "cpus": (toml.get("environment") or {}).get("cpus"),
                "memory_mb": (toml.get("environment") or {}).get("memory_mb")}
    controls = [{"id": "start", "expect": {primary: low.get(primary, 0.0)}},
                {"id": "reference", "solve": True, "expect": high}]
    first = config.get("first_command") or {}
    command = first.get("command") or (params.get("suite") or {}).get("command")
    if command:
        controls.append({"id": "first-command", "command": command, "stand_in": not first.get("command"),
                         "timeout": float(first.get("timeout_sec") or FIRST_COMMAND_TIMEOUT)})
    shadows = shadow_plan(task, params)
    if shadows:
        controls.append({"id": "shadow-imports", "script": shadow_script(shadows),
                         "expect": {primary: low.get(primary, 0.0)}})
    for control in config.get("controls") or []:
        patch = control.get("patch")
        base = {"id": control["id"], "solve": bool(control.get("solve")), "patch": patch,
                "expect": control["expect"]}
        controls.append(base)
        if control.get("hide"):
            files = changed_files((task / "controls" / patch).read_text(encoding="utf-8", errors="replace"))
            for method in HIDING_METHODS:
                controls.append({**base, "id": f"{control['id']}/{method}", "script": hiding_script(method, files)})
    return settings, controls


def verdict(expect: dict, scores: dict) -> tuple[bool, str]:
    misses = []
    for ev_id, want in expect.items():
        got = scores.get(ev_id)
        if not isinstance(got, (int, float)) or not math.isclose(got, want, abs_tol=1e-9):
            misses.append(f"{ev_id} {got if got is not None else 'no score'} (expected {want})")
    return not misses, "; ".join(misses)


def run_control(engine: Engine, image: str, task: Path, settings: dict, control: dict) -> dict:
    began = time.monotonic()
    name = engine.start(image, settings["cpus"], settings["memory_mb"])
    workspace, user = settings["workspace"], settings["agent_user"]
    try:
        if control["id"] == "first-command":
            who = "root" if control.get("stand_in") else user
            code, output = engine.run(name, control["command"], user=who, workdir=workspace,
                                      timeout=control["timeout"])
            ok = code is not None and code not in (126, 127)
            detail = (f"did not finish within {control['timeout']:g} s" if code is None
                      else f"exit {code}" + (" (could not run)" if code in (126, 127) else ""))
            if control.get("stand_in"):
                detail += "; ran the suite command as a stand-in, since controls.json declares no first_command"
            return {"id": "first-command", "ok": ok, "detail": detail, "output_tail": output.strip()[-600:],
                    "seconds": round(time.monotonic() - began, 1)}
        engine.run(name, "mkdir -p /tests /logs/verifier /logs/agent /tmp/relai-controls")
        engine.copy(name, task / "tests", "/tests")
        steps = []
        if control.get("solve"):
            engine.copy(name, task / "solution", "/solution")
            steps.append(("solve", "bash /solution/solve.sh", "root"))
        if control.get("patch"):
            engine.copy(name, task / "controls", "/tmp/relai-controls")
            steps.append(("patch", f"git apply --whitespace=nowarn /tmp/relai-controls/{shlex.quote(control['patch'])}",
                          user))
        if control.get("script"):
            steps.append(("change", control["script"], user))
        for label, script, who in steps:
            code, output = engine.run(name, script, user=who, workdir=workspace, timeout=1800)
            if code != 0:
                return {"id": control["id"], "ok": False, "detail": f"{label} failed (exit {code}): "
                        f"{output.strip()[-400:]}", "seconds": round(time.monotonic() - began, 1)}
        code, output = engine.run(name, "bash /tests/test.sh", timeout=7200)
        _, reward = engine.run(name, "cat /logs/verifier/reward.json")
        try:
            scores = json.loads(reward)
        except ValueError:
            return {"id": control["id"], "ok": False, "detail": f"no reward.json (test.sh exit {code}): "
                    f"{output.strip()[-400:]}", "seconds": round(time.monotonic() - began, 1)}
        ok, misses = verdict(control["expect"], scores)
        return {"id": control["id"], "ok": ok, "expected": control["expect"], "scores": scores,
                "detail": misses or "as expected", "seconds": round(time.monotonic() - began, 1)}
    except RuntimeError as exc:
        return {"id": control["id"], "ok": False, "detail": str(exc), "seconds": round(time.monotonic() - began, 1)}
    finally:
        engine.remove(name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task", help="an agent-neutral coding task directory")
    parser.add_argument("--engine", help="the container CLI (default: docker, else podman)")
    parser.add_argument("--only", help="comma-separated control ids to run; the record then marks itself partial")
    parser.add_argument("--plan", action="store_true", help="print the controls and their commands; run nothing")
    parser.add_argument("--relai-dir")
    args = parser.parse_args()
    task = Path(args.task).resolve()
    relai_dir = relai_root(args.relai_dir)
    if not (task / "task.toml").is_file() or not (task / "tests" / "params.json").is_file():
        parser.error(f"{task} is not an agent-neutral coding task (needs task.toml and tests/params.json)")
    settings, controls = plan(task)
    if args.only:
        wanted = set(args.only.split(","))
        controls = [c for c in controls if c["id"] in wanted or c["id"].split("/")[0] in wanted]
    if args.plan:
        for control in controls:
            steps = (["solution/solve.sh"] if control.get("solve") else []) + \
                    ([f"git apply controls/{control['patch']}"] if control.get("patch") else [])
            who = "root" if control.get("stand_in") else settings["agent_user"]
            print(f"{control['id']}: " + (f"run `{control['command']}` as {who}, timeout "
                                          f"{control['timeout']:g} s" if "command" in control
                                          else f"{' then '.join(steps) or 'no change'}; expect {control['expect']}"))
            if control.get("script"):
                print("    " + control["script"].replace("\n", "\n    "))
        return 0
    engine = find_engine(args.engine)
    digest = dir_digest(task)
    image = f"relai-controls-{task.name}:{digest[:12]}"
    engine.build(task / "environment", image)
    results = []
    for control in controls:
        result = run_control(engine, image, task, settings, control)
        results.append(result)
        print(f"{'PASS' if result['ok'] else 'FAIL'} {result['id']}: {result['detail']} ({result['seconds']} s)",
              flush=True)
    key = test_key(task, relai_dir)
    record = {"task": key, "digest": digest, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "engine": engine.cli, "partial": bool(args.only), "ok": all(r["ok"] for r in results),
              "controls": results}
    out = controls_record(relai_dir, key)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    failed = [r["id"] for r in results if not r["ok"]]
    print(f"{len(results) - len(failed)} of {len(results)} controls passed; wrote {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
