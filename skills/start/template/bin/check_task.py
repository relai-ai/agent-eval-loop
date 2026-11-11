#!/usr/bin/env python3
"""Check Harbor or native test tasks against the RELAI contract (see relai/README.md).

Usage:
  python3 relai/bin/check_task.py relai/tests/<id> [more task dirs] [--verifier [--fixture DIR]] [--json]

Harbor runs also check relai.toml [harbor]. With --cloud, check portability to the bundled hosted
builder (fixed rule 8): each
FROM or COPY --from in its Dockerfiles names the harness image from [harbor.image], as the only FROM and
the first instruction, or an image its registry serves without credentials (asked anonymously with HEAD
requests, as a cloud builder would pull it), and no FROM reads a build argument. A FROM that pins a literal
platform is warned about: the platform that runs a test decides its architecture. With --json, each report is one JSON document: the [harbor] table first, then each task.

Static checks always run, including Harbor's own task loading (through `uv`; --no-harbor skips
it). --verifier also builds the task's verifier and runs tests/test.sh, as Harbor would, on a
synthetic normal trajectory and a synthetic empty-reply trajectory, requiring a score and feedback
from every declared code evaluator (needs a docker- or podman-compatible container engine). --fixture DIR copies DIR's files into
/logs/agent beside the synthetic trajectory, for evaluators that also read state the harness
exports there (a database dump, a mock journal). Writes nothing in the repository.

An agent-neutral coding task ([metadata.relai].agent_neutral = true, the `coding-evals` skill) gets
leak and verifier checks instead of the harness ones: the workspace image fails to build if the real fix
is in it, its git bundles hold the start commit and its ancestors only, nothing in tests/ or solution/ is
visible to the agent, the verifier shares the agent's container and runs isolated, and the protected
snapshot matches its manifest. --verifier does not apply to it: run the oracle and nop agents instead.
When every task checked is agent-neutral, [harbor] needs only its version (no harness).
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import http.client
import ipaddress
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ENV_EXAMPLE_NAMES, HARBOR_PYTHON, JUNK_DIRS, Report, declared_evaluators, dir_digest,
    evals_config, relai_root, expand_globs, file_sha256, frozen_state, load_toml, normalized, repo_root,
    scan_secrets, secret_values, test_key, walk_files, runner_settings, pass_mark, harbor_version,
)

ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TASK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
COPY_RE = re.compile(r"^\s*(COPY|ADD)\s+(.*)$", re.IGNORECASE | re.MULTILINE)
TRAJECTORY = "/logs/agent/trajectory.json"
HARBOR_LOAD = r"""
import json, sys
from pathlib import Path
from harbor.models.task.task import Task
out = {}
for raw in sys.argv[1:]:
    path = Path(raw)
    try:
        if not Task.is_valid_dir(path):
            out[raw] = "Harbor does not recognize this directory as a task (it would skip it without a message)"
            continue
        Task(path)
        out[raw] = None
    except Exception as exc:
        out[raw] = f"{type(exc).__name__}: {exc}"[:1500]
print(json.dumps(out))
"""


def is_separate(config: dict) -> bool:
    verifier = config.get("verifier", {}) or {}
    return verifier.get("environment_mode") == "separate" or "environment" in verifier


def artifact_sources(config: dict) -> list[str]:
    sources = []
    for entry in config.get("artifacts", []) or []:
        sources.append(entry if isinstance(entry, str) else (entry or {}).get("source", ""))
    return sources


def host_templates(value, path: str, report: Report) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            host_templates(child, f"{path}.{key}" if path else key, report)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            host_templates(child, f"{path}[{index}]", report)
    elif isinstance(value, str) and "${" in value:
        report.error(f"task.toml {path} reads a host variable (${{...}}); Harbor would copy a "
                     "host value into a container. Pass values another way")


def check_evaluators(task: Path, config: dict, report: Report) -> list[dict]:
    meta = config.get("metadata", {}).get("relai")
    if not isinstance(meta, dict):
        report.error("task.toml has no [metadata.relai] table")
        return []
    if meta.get("id") != task.name:
        report.error(f"[metadata.relai].id is {meta.get('id')!r}; it must equal the directory name {task.name!r}")
    evaluators = declared_evaluators(config)
    if not evaluators:
        report.error("declares no [[metadata.relai.evaluators]]; a test must be scored")
    seen = set()
    for index, ev in enumerate(evaluators):
        where = f"evaluator #{index + 1} ({ev.get('id', '?')})"
        ev_id = ev.get("id")
        if not isinstance(ev_id, str) or not ID_RE.match(ev_id):
            report.error(f"{where}: id must be a lowercase slug")
        elif ev_id in seen:
            report.error(f"{where}: duplicate id")
        seen.add(ev_id)
        kind = ev.get("type")
        if kind not in ("code", "judge"):
            report.error(f"{where}: type must be 'code' or 'judge'")
        low, high = ev.get("min_score", 0.0), ev.get("max_score", 1.0)
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (low, high)) or low >= high:
            report.error(f"{where}: min_score and max_score must be finite numbers with min < max")
        method = ev.get("method")
        if method not in ("exact", "semantic"):
            report.error(f"{where}: method must be 'exact' (code can decide it) or 'semantic' (open-ended meaning)")
        elif method == "semantic" and kind != "judge":
            report.error(f"{where}: a semantic criterion needs a judge; keywords and regexes miss valid phrasings")
        if not str(ev.get("criterion", "")).strip():
            report.error(f"{where}: criterion (one sentence on what earns full marks) is missing")
        if kind == "judge":
            rubric = ev.get("rubric")
            if not rubric or not (task / rubric).is_file():
                report.error(f"{where}: rubric {rubric!r} not found; the path is relative to the test directory")
    for ref in meta.get("covers", []) or []:
        if not isinstance(ref, str):
            report.error("[metadata.relai].covers must list wiki page ids")
    if meta.get("split", "development") not in ("development", "held-out", "final"):
        report.error("[metadata.relai].split must be 'development', 'held-out' or 'final'")
    return evaluators


def check_static(task: Path, relai_dir: Path, report: Report, native: bool = False, cloud: bool = False) -> dict:
    toml_path = task / "task.toml"
    if not toml_path.is_file():
        report.error("task.toml not found")
        return {}
    try:
        config = load_toml(toml_path)
    except Exception as exc:  # tomllib raises TOMLDecodeError
        report.error(f"task.toml does not parse: {exc}")
        return {}

    if native:
        report.note("native runner: Harbor-only structure checks skipped")
    else:
        check_harbor_layout(task, config, report)

    check_evaluators(task, config, report)
    neutral = is_agent_neutral(config)
    if neutral:
        check_coding(task, config, relai_dir, report)

    for current, dirs, _files in os.walk(task):
        for name in sorted(d for d in dirs if d in JUNK_DIRS):
            rel = (Path(current) / name).relative_to(task)
            report.error(f"{rel} is a cache or dependency folder; remove it (it breaks or bloats image builds)")
        dirs[:] = [d for d in dirs if d not in JUNK_DIRS]
    for path in walk_files(task, JUNK_DIRS):
        rel = path.relative_to(task)
        name = rel.name
        if name == ".env" or (name.startswith(".env.") and name not in ENV_EXAMPLE_NAMES):
            report.error(f"{rel} is an env file; secret values never go in a task")
        if path.is_symlink():
            report.error(f"{rel} is a symlink; reproducible task checks need regular files")
        if name == ".harborignore":
            report.error(f"{rel}: Harbor leaves the files it matches out of the verifier's upload and the task "
                         "checksum, so graders can run without them; remove it")

    values = secret_values(relai_dir)
    scan_secrets(walk_files(task, JUNK_DIRS), values, task, report)
    harness = relai_dir / "harness"
    if harness.is_dir():
        scan_secrets(walk_files(harness, JUNK_DIRS), values, relai_dir, report)
    if not native:
        if not neutral:  # a coding task's workspace is a pinned repository, not the agent's live source
            check_live_copies(task, relai_dir, report)
        check_task_images(task, config, relai_dir, report, cloud=cloud)

    frozen = frozen_state(relai_dir).get("tests", {}).get(test_key(task, relai_dir))
    if frozen and frozen.get("digest") != dir_digest(task):
        report.warn("changed since it was frozen; a change needs a reason (freeze.py --reason) and a fresh review")
    return config


def is_agent_neutral(config: dict) -> bool:
    return bool((config.get("metadata", {}).get("relai", {}) or {}).get("agent_neutral"))


SHA_RE = re.compile(r"^[0-9a-f]{7,64}$")
LEAK_MIN_BYTES = 20  # smaller files (an empty __init__.py) match by chance


def bundle_contents(bundle: Path, commits: list[str]) -> tuple[list[str], list[str]]:
    """(present, heads): which of these commits a clone of the bundle contains, and the bundle's heads."""
    listed = subprocess.run(["git", "bundle", "list-heads", str(bundle)], capture_output=True, text=True)
    heads = [line.split()[0] for line in listed.stdout.splitlines() if line.strip()]
    with tempfile.TemporaryDirectory(prefix="relai-bundle-check-") as tmp:
        clone = Path(tmp) / "clone"
        ran = subprocess.run(["git", "clone", "-q", "--mirror", str(bundle), str(clone)], capture_output=True, text=True)
        if ran.returncode:
            raise ValueError(f"cannot clone the bundle: {ran.stderr.strip()[-300:]}")
        present = [c for c in commits if subprocess.run(
            ["git", "-C", str(clone), "cat-file", "-e", f"{c}^{{commit}}"], capture_output=True).returncode == 0]
    return present, heads


def check_coding(task: Path, config: dict, relai_dir: Path, report: Report) -> None:
    """An agent-neutral coding task: any coding agent can run it, and nothing it can see gives the answer away."""
    meta = config.get("metadata", {}).get("relai", {}) or {}
    coding = meta.get("coding") if isinstance(meta.get("coding"), dict) else {}
    if not coding:
        report.error("agent_neutral task has no [metadata.relai.coding] table (start_commit, fix_commit, primary, "
                     "workspace)")
    workspace = coding.get("workspace", "/app")
    start, fix = coding.get("start_commit"), coding.get("fix_commit")
    fix = fix if isinstance(fix, str) and SHA_RE.match(fix) else None
    if not (isinstance(start, str) and SHA_RE.match(start)):
        report.error("[metadata.relai.coding].start_commit must be the commit id the workspace starts from")
    if fix is None and coding.get("source") != "written":
        report.error("[metadata.relai.coding].fix_commit must be the commit id of the real fix, which the workspace "
                     "must not contain; only a task written from scratch (source = \"written\") has none")

    evaluators = declared_evaluators(config)
    primary = next((ev for ev in evaluators if ev.get("id") == coding.get("primary")), None)
    if primary is None:
        report.error("[metadata.relai.coding].primary must name the code evaluator that says the task was solved")
    elif primary.get("type") != "code" or primary.get("trajectory"):
        report.error(f"primary evaluator {primary.get('id')!r} must be a code evaluator that reads the workspace, "
                     "not the trajectory, so every agent and the oracle are scored on it")

    if is_separate(config):
        report.error("an agent-neutral task's verifier shares the agent's container (leave environment_mode unset): "
                     "its checks read the workspace the agent left")
    agent = config.get("agent") or {}
    timeout = agent.get("timeout_sec")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        report.error("[agent].timeout_sec is missing: Harbor has no default, so an agent that never stops runs forever")
    if coding.get("public") is True and agent.get("network_mode") in (None, "public"):
        report.note("the fix is public and the agent's network is open, so an agent could fetch it; fine if the "
                    "user chose an open network (record it in the README), otherwise restrict [agent].network_mode")
    if not (task / "solution" / "solve.sh").is_file():
        report.error("solution/solve.sh is missing: the reference fix that shows the task can be solved")

    env_dir = task / "environment"
    dockerfile = env_dir / "Dockerfile"
    if dockerfile.is_file():
        instructions = dockerfile_instructions(dockerfile.read_text(errors="ignore"))
        harness = harness_tag(relai_dir)
        if harness and any(op == "FROM" and harness in args for op, args in instructions):
            report.error("an agent-neutral task must not start FROM the configured harness image: Harbor installs "
                         "the agent under test; use a base without that agent installation (public for the "
                         "bundled hosted recipe, or authorized local/private infrastructure)")
        workdirs = [args[0] for op, args in instructions if op == "WORKDIR" and args]
        effective = (config.get("environment") or {}).get("workdir") or (workdirs[-1] if workdirs else None)
        if effective != workspace:
            report.error(f"the agent must start in the workspace {workspace} (found {effective!r})")
        if fix:
            guard = re.compile(r"!\s*git\b.*\bcat-file\s+-e\s+['\"]?" + re.escape(fix[:7]) + r"[0-9a-f]*")
            if not any(op == "RUN" and guard.search(" ".join(args)) for op, args in instructions):
                report.error(f"environment/Dockerfile needs the leak guard `RUN ! git -C {workspace} cat-file -e {fix}`, "
                             "so the image fails to build if the real fix is in the workspace")

    tests_dir = task / "tests"
    try:
        params = json.loads((tests_dir / "params.json").read_text())
        params = params if isinstance(params, dict) else {}
    except (OSError, ValueError) as exc:
        report.error(f"tests/params.json is missing or not JSON: {exc}")
        params = {}
    given = str(params.get("start_commit") or "")
    if params and (not given or not isinstance(start, str) or not (given.startswith(start) or start.startswith(given))):
        report.error("tests/params.json start_commit must be the task's start commit; the verifier diffs from it, "
                     "never from anything in the workspace")
    if params and not params.get("protected_manifest"):
        report.error("tests/params.json has no protected_manifest: run `python3 tests/coding_checks.py protect` "
                     "(see its docstring)")
    for rel, entry in (params.get("protected_manifest") or {}).items():
        if isinstance(entry, dict) and entry.get("mode") != "120000":
            saved = tests_dir / "protected" / rel
            if not saved.is_file() or file_sha256(saved) != entry.get("sha256"):
                report.error(f"tests/protected/{rel} is missing or differs from the manifest; rerun protect")
                break
    setup_files = params.get("setup_files") or []
    setup_manifest = params.get("setup_manifest") or {}
    if (not isinstance(setup_files, list) or any(not isinstance(p, str) for p in setup_files)
            or not isinstance(setup_manifest, dict) or set(setup_files) != set(setup_manifest)):
        report.error("setup_manifest must match setup_files: capture the installed pre-agent workspace with "
                     "`python3 tests/coding_checks.py setup <workspace> <task>`")
    else:
        for rel, entry in setup_manifest.items():
            relative = Path(rel)
            if not rel or relative.is_absolute() or ".." in relative.parts or relative == Path("."):
                report.error(f"setup_files path {rel!r} must be relative to the workspace")
                continue
            mode = entry.get("mode") if isinstance(entry, dict) else None
            if mode == "120000" and isinstance(entry.get("target"), str):
                continue
            saved = tests_dir / "setup" / relative
            if (mode not in ("100644", "100755") or saved.is_symlink() or not saved.is_file()
                    or file_sha256(saved) != entry.get("sha256")):
                report.error(f"tests/setup/{rel} is missing or differs from setup_manifest; "
                             "recapture the installed pre-agent workspace")
    script = tests_dir / "test.sh"
    body = script.read_text(errors="ignore") if script.is_file() else ""
    if "/logs/verifier" not in body or not re.search(r"python3?\s+-I\s+-S\b", body):
        report.error("tests/test.sh must clear /logs/verifier and run verify.py isolated (python3 -I -S), as the "
                     "plugin's verifier test.sh does: the agent can write there before the verifier runs")

    # Nothing the agent can see may be a copy of what scores it or of the answer.
    hidden_files = {}
    for folder in (tests_dir, task / "solution"):
        for path in walk_files(folder, JUNK_DIRS) if folder.is_dir() else []:
            if (not path.is_relative_to(tests_dir / "protected") and not path.is_relative_to(tests_dir / "setup")
                    and path.name != "coding_checks.py"
                    and path.stat().st_size >= LEAK_MIN_BYTES):
                hidden_files[file_sha256(path)] = path.relative_to(task).as_posix()
    visible = [*(walk_files(env_dir, JUNK_DIRS) if env_dir.is_dir() else []), task / "instruction.md"]
    for path in visible:
        if path.is_file() and path.stat().st_size >= LEAK_MIN_BYTES and (match := hidden_files.get(file_sha256(path))):
            report.error(f"{path.relative_to(task)} is a copy of {match}, which the agent must not see")
    if fix and (task / "instruction.md").is_file() and fix[:7] in (task / "instruction.md").read_text(errors="ignore"):
        report.error("instruction.md mentions the fix commit")
    for bundle in sorted(env_dir.glob("*.bundle")) if env_dir.is_dir() else []:
        if not shutil.which("git"):
            report.note(f"git is not on PATH, so {bundle.name} was not checked for the fix commit")
            continue
        try:
            present, heads = bundle_contents(bundle, [fix] if fix else [])
        except ValueError as exc:
            report.error(f"{bundle.name}: {exc}")
            continue
        if present:
            report.error(f"{bundle.name} contains the fix commit {fix[:10]}: the agent could read the answer from history")
        if isinstance(start, str) and not any(h.startswith(start) for h in heads):  # heads are full ids
            report.error(f"{bundle.name}'s head is {', '.join(h[:10] for h in heads) or 'missing'}, not the start "
                         f"commit {start[:10]}")


def check_harbor_layout(task: Path, config: dict, report: Report) -> None:
    if not (task / "instruction.md").is_file():
        report.error("instruction.md is missing (Harbor requires it, even empty)")
    env = config.get("environment", {}) or {}
    if not (task / "environment").is_dir():
        if not env.get("docker_image"):
            report.error("environment/ is missing and [environment].docker_image is unset (Harbor skips the task)")
    elif not ((task / "environment" / "Dockerfile").is_file()
              or (task / "environment" / "docker-compose.yaml").is_file() or env.get("docker_image")):
        report.error("environment/ has no Dockerfile or docker-compose.yaml and [environment].docker_image is unset")
    if not (task / "tests" / "test.sh").is_file():
        report.error("tests/test.sh is missing")
    info = config.get("task")
    if isinstance(info, dict) and not TASK_NAME_RE.match(str(info.get("name", ""))):
        report.error("[task].name must look like 'org/name' (Harbor skips the task otherwise)")

    if is_separate(config):
        verifier_env = (config.get("verifier", {}) or {}).get("environment", {}) or {}
        if not (task / "tests" / "Dockerfile").is_file() and not verifier_env.get("docker_image"):
            report.error("separate verifier needs tests/Dockerfile or [verifier.environment].docker_image; "
                         "without either, Harbor quietly builds it from environment/")
        dockerfile = task / "tests" / "Dockerfile"
        if dockerfile.is_file() and "/tests" not in dockerfile.read_text(errors="ignore"):
            report.warn("tests/Dockerfile never mentions /tests; Harbor does not upload tests/ to a "
                        "separate verifier, so the image must COPY them to /tests")
        if TRAJECTORY not in artifact_sources(config):
            report.error(f"separate verifier: add {TRAJECTORY!r} to top-level artifacts, or the verifier never sees the trajectory")

    for table in ("environment", "verifier", "solution", "agent"):
        host_templates(config.get(table, {}), table, report)



def check_live_copies(task: Path, relai_dir: Path, report: Report) -> None:
    """Files whose edits change the agent's behavior must not be baked into an image."""
    patterns = (evals_config(relai_dir).get("target", {}) or {}).get("live_paths", []) or []
    if not patterns:
        report.note("relai.toml [target].live_paths is empty, so copies of prompts or configs were not checked")
        return
    root = repo_root(relai_dir)
    live = {file_sha256(p): p.relative_to(root).as_posix()
            for p in expand_globs(root, patterns) if not p.is_relative_to(relai_dir) and p.stat().st_size}
    if not live:
        report.warn(f"live_paths {patterns} match no files")
        return
    live_paths = set(live.values())
    for base in (task / "environment", relai_dir / "harness"):
        if not base.is_dir():
            continue
        for path in walk_files(base, JUNK_DIRS):
            if path.stat().st_size and (match := live.get(file_sha256(path))):
                report.error(f"{path.relative_to(root)} is a copy of live file {match}; trials must read it "
                             "from the current source, or optimizer edits are never measured")
            if path.name.startswith("Dockerfile"):
                for _verb, args in COPY_RE.findall(path.read_text(errors="ignore")):
                    sources = [a for a in args.split() if not a.startswith("--")][:-1]
                    for source in sources:
                        source = source.strip('"[],').lstrip("./") or "."
                        hits = [p for p in live_paths if source == "." or p == source or p.startswith(source + "/")]
                        if hits:
                            report.warn(f"{path.relative_to(root)} copies {source!r}, which includes live file "
                                        f"{hits[0]}; fine if the trial still runs it from the current source, "
                                        "but a baked-in copy hides an optimizer's edits")


def harbor_table(relai_dir: Path) -> dict:
    harbor = evals_config(relai_dir).get("harbor")
    return harbor if isinstance(harbor, dict) else {}


def harness_tag(relai_dir: Path) -> str | None:
    image = harbor_table(relai_dir).get("image")
    tag = image.get("tag") if isinstance(image, dict) else None
    return tag if isinstance(tag, str) and tag else None


def has_judges(tasks: list[Path]) -> bool:
    """Whether any of these tasks declares a judge evaluator (unreadable task.toml files count as none)."""
    for task in tasks:
        try:
            if any(ev.get("type") == "judge" for ev in declared_evaluators(load_toml(task / "task.toml"))):
                return True
        except Exception:  # check_static reports the parse error
            continue
    return False


def all_agent_neutral(tasks: list[Path]) -> bool:
    def neutral(task: Path) -> bool:
        try:
            return is_agent_neutral(load_toml(task / "task.toml"))
        except Exception:
            return False
    return bool(tasks) and all(neutral(t) for t in tasks)


def check_harbor(relai_dir: Path, report: Report, judged: bool = False, cloud: bool = False,
                 neutral_only: bool = False) -> None:
    """relai.toml [harbor]: everything a runner needs to run the suite without knowing the agent.
    judged: whether the tests being checked declare judge evaluators. neutral_only: every test is an
    agent-neutral coding task, whose agent Harbor installs, so no harness settings are needed."""
    config = evals_config(relai_dir)
    if (relai_dir / "relai.toml").is_file():
        scan_secrets([relai_dir / "relai.toml"], secret_values(relai_dir), relai_dir, report)
    harbor = config.get("harbor")
    if harbor is None:
        report.warn("relai.toml has no [harbor] table, so this suite's Harbor integration was not checked "
                    "(see the relai.toml contract in relai/docs/files.md)")
        return
    if not isinstance(harbor, dict):
        report.error("[harbor] must be a table")
        return
    if harbor_version(relai_dir) is None:
        report.error("[harbor].version must be the exact Harbor release this suite runs with (such as \"1.2.3\"); "
                     "record the latest stable release when setting up, and change it only as a measurement change")
    judge = config.get("judge")
    if cloud and judged and isinstance(judge, dict) and judge.get("mode") == "subagent":
        report.warn('[judge].mode is "subagent", but these tests have judge evaluators: a hosted runner has no '
                    'coding agent to judge with, so they stay "judges pending" and never pass there. A hosted '
                    'runner needs mode = "api"')
    if neutral_only:
        try:
            if pass_mark(config) is None:
                report.warn("[scoring].pass_mark is not set yet; there is no default. Choose it with the user "
                            "after the first scored run, before reporting any test as passed or failed")
        except ValueError as exc:
            report.error(str(exc))
        return
    root = repo_root(relai_dir)

    def inside(rel) -> bool:  # a clean clone holds only what is under the repository root
        return isinstance(rel, str) and (root / rel).resolve().is_relative_to(root.resolve())

    paths = harbor.get("pythonpath", [])
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        report.error("[harbor].pythonpath must list directories relative to the repository root")
        paths = []
    for rel in paths:
        if not inside(rel) or not (root / rel).is_dir():
            report.error(f"[harbor].pythonpath {rel!r} is not a directory under the repository root")
    agent = harbor.get("agent")
    if not isinstance(agent, str) or not agent.strip():
        report.error("[harbor].agent must name the agent passed to `harbor run -a` (module:Class for a custom class)")
    elif ":" in agent:
        module = agent.split(":", 1)[0].replace(".", "/")
        if not any((root / rel / f"{module}.py").is_file() or (root / rel / module / "__init__.py").is_file()
                   for rel in paths):
            report.error(f"[harbor].agent {agent!r}: no {module}.py under any [harbor].pythonpath directory, "
                         "so Harbor cannot import it")
    options = harbor.get("agent_env", {})
    runtime = config.get("runtime")
    names = runtime.get("env") if isinstance(runtime, dict) else None
    secrets = {n for n in names if isinstance(n, str)} if isinstance(names, list) else set()
    if not isinstance(options, dict) or not all(isinstance(v, str) for v in options.values()):
        report.error("[harbor].agent_env must map option names to strings (each passed as --ae NAME=value)")
    else:
        for name, value in options.items():
            if name in secrets:
                report.error(f"[harbor].agent_env sets {name}, a secret named in [runtime].env; secret values "
                             "reach Harbor from the runner's environment, never from relai.toml")
            if "${" in value:
                report.error(f"[harbor].agent_env {name} reads a host variable (${{...}}); Harbor would copy a "
                             "host value into the container")
    try:
        if pass_mark(config) is None:
            report.warn("[scoring].pass_mark is not set yet; there is no default. Choose it with the user "
                        "after the first scored run, before reporting any test as passed or failed")
    except ValueError as exc:
        report.error(str(exc))
    image = harbor.get("image")
    if not isinstance(image, dict):
        report.error("[harbor.image] is missing: the tag, dockerfile and context of the harness image tasks start FROM")
        return
    tag, dockerfile, context = image.get("tag"), image.get("dockerfile"), image.get("context")
    if not isinstance(tag, str) or not tag or "$" in tag or any(c.isspace() for c in tag):
        report.error("[harbor.image].tag must be the image name task Dockerfiles use in FROM")
    if not inside(dockerfile) or not (root / dockerfile).is_file():
        report.error(f"[harbor.image].dockerfile {dockerfile!r} is not a file under the repository root")
    else:
        check_dockerfile((root / dockerfile).read_text(errors="ignore"), f"[harbor.image] {dockerfile}", None, report,
                         cloud=cloud)
    if not inside(context) or not (root / context).is_dir():
        report.error(f"[harbor.image].context {context!r} is not a directory under the repository root")
    elif isinstance(dockerfile, str):
        context_dir, recipe = root / context, root / dockerfile
        # The ignore files both Docker (BuildKit) and Modal read.
        ignores = (recipe.with_name(recipe.name + ".dockerignore"), context_dir / ".dockerignore")
        if any(p.is_file() for p in ignores):
            return
        junk = []
        for current, dirs, _files in os.walk(context_dir):
            junk += [(Path(current) / d).relative_to(context_dir).as_posix() for d in sorted(dirs) if d in JUNK_DIRS]
            dirs[:] = [d for d in dirs if d not in JUNK_DIRS]
        if junk:
            report.warn(f"[harbor.image].context holds {', '.join(junk[:3])}; add {recipe.name}.dockerignore beside "
                        "the Dockerfile (Docker and Modal both read it) or narrow the context, or every build "
                        "uploads them")


DOCKER_HUB = {"docker.io", "index.docker.io", "registry-1.docker.io"}
LOCAL_SUFFIXES = (".localhost", ".local", ".internal")
RUNNER_PLATFORMS = {"$BUILDPLATFORM", "${BUILDPLATFORM}", "$TARGETPLATFORM", "${TARGETPLATFORM}"}
PARSER_DIRECTIVE_RE = re.compile(r"^#\s*(syntax|escape|check)\s*=", re.IGNORECASE)
HEREDOC_RE = re.compile(r"<<-?([\"']?)([A-Za-z_][A-Za-z0-9_]*)\1")
MANIFEST_TYPES = ", ".join((
    "application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"))
REGISTRY_TIMEOUT = 10
_unreachable: set[str] = set()


def dockerfile_instructions(text: str) -> list[tuple[str, list[str]]]:
    """(INSTRUCTION, arguments) per Dockerfile instruction: continuation lines joined, comments and
    heredoc bodies (RUN <<EOF ... EOF) skipped."""
    instructions, pending, heredocs = [], "", []
    for line in text.lstrip("﻿").splitlines():
        stripped = line.strip()
        if heredocs:
            if stripped == heredocs[0]:
                heredocs.pop(0)
            continue
        if stripped.startswith("#") or (not stripped and not pending):
            continue
        if stripped.endswith("\\"):
            pending += stripped[:-1] + " "
            continue
        words, pending = (pending + stripped).split(), ""
        if words:
            instructions.append((words[0].upper(), words[1:]))
            if words[0].upper() in ("RUN", "COPY", "ADD"):
                heredocs = [match[1] for match in HEREDOC_RE.findall(" ".join(words[1:]))]
    if pending.split():
        words = pending.split()
        instructions.append((words[0].upper(), words[1:]))
    return instructions


def parser_directives(text: str) -> list[str]:
    """The parser directives (# syntax=, # escape=, # check=) at the top of a Dockerfile."""
    directives = []
    for line in text.lstrip("﻿").splitlines():
        if not PARSER_DIRECTIVE_RE.match(line.strip()):
            break
        directives.append(line.strip())
    return directives


def check_dockerfile(text: str, where: str, harness: str | None, report: Report, cloud: bool = False) -> None:
    """Check architecture hints; cloud mode also checks the bundled builder's substitution rules."""
    instructions = dockerfile_instructions(text)
    froms = [index for index, (op, _args) in enumerate(instructions) if op == "FROM"]
    stages: set[str] = set()
    for index, (op, args) in enumerate(instructions):
        if op == "FROM":
            options = [a for a in args if a.startswith("--")]
            words = [a for a in args if not a.startswith("--")]
            image = words[0] if words else ""
            platform = next((o.split("=", 1)[1] for o in options if o.startswith("--platform=")), None)
            if platform is not None and platform not in RUNNER_PLATFORMS:
                report.warn(f"{where}: FROM {image} pins --platform={platform}; a runner on another architecture "
                            "then emulates it or fails, so let the runner's platform decide")
            if not cloud:
                continue
            if harness and image == harness:
                if froms != [0]:
                    report.error(f"{where}: a Dockerfile that starts FROM the harness image {harness} must have no "
                                 "other FROM and no instruction before it, so a runner can apply the rest of it to "
                                 "the harness it builds from [harbor.image]")
                if directives := parser_directives(text):
                    report.error(f"{where}: starts FROM the harness image but has parser directives "
                                 f"({', '.join(directives)}); a runner applies only the instructions after FROM, so "
                                 "their effect would be lost. Remove them")
            else:
                check_image(image, f"{where}: FROM {image}", stages, harness, report)
            if len(words) >= 3 and words[1].upper() == "AS":
                stages.add(words[2].lower())
        elif cloud and op in ("COPY", "ADD", "RUN"):
            for option in args:
                if not option.startswith("--"):
                    break  # options come before sources and commands
                if option.startswith("--from=") and op != "RUN":
                    source, label = option.split("=", 1)[1], f"{where}: {op} {option}"
                elif option.startswith("--mount="):
                    fields = dict(f.split("=", 1) for f in option.split("=", 1)[1].split(",") if "=" in f)
                    source, label = fields.get("from", ""), f"{where}: RUN --mount from={fields.get('from')}"
                else:
                    continue
                if source and source == harness:
                    report.error(f"{label} reads from the harness image, which a cloud builder has only as the "
                                 "base a runner applies this Dockerfile to; start FROM it instead")
                elif source and not source.isdigit():
                    check_image(source, label, stages, harness, report)


def local_registry(registry: str) -> bool:
    """True for a registry on this machine or its private network, which a cloud builder cannot reach."""
    host = (registry if registry.endswith("]") else registry.rsplit(":", 1)[0]).strip("[]").lower()
    if host == "localhost" or host.endswith(LOCAL_SUFFIXES):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def check_image(image: str, label: str, stages: set[str], harness: str | None, report: Report) -> None:
    if not image:
        report.error(f"{label} names no image")
        return
    if "$" in image:
        report.error(f"{label} reads a build argument; cloud builds get none, so name the image directly")
        return
    if image.lower() in stages or image == "scratch":
        return
    registry = image_reference(image)[0]
    if local_registry(registry):
        report.error(f"{label} comes from a registry on this machine or its network ({registry}), which a cloud "
                     "builder cannot reach")
        return
    found = pullable(image)
    if found is False:
        fix = (f"start FROM the harness image {harness} (built from [harbor.image])" if harness else
               "declare it as the harness image in relai.toml [harbor.image]")
        report.error(f"{label}: no registry serves this image without credentials, so a cloud builder cannot "
                     f"pull it (a tag that exists only where it was built, or a private image). Either {fix}, "
                     "or use an image a registry serves publicly")
    elif found is None:
        report.note(f"{label}: its registry could not be reached, so it was not checked for cloud builds")


def image_reference(image: str) -> tuple[str, str, str]:
    """(registry, repository, tag or digest), resolved the way Docker resolves a FROM name."""
    name, _, digest = image.partition("@")
    first, slash, rest = name.partition("/")
    registry, repository = (first, rest) if slash and ("." in first or ":" in first or first == "localhost") \
        else ("docker.io", name)
    tag = ""
    if ":" in repository.rsplit("/", 1)[-1]:
        repository, tag = repository.rsplit(":", 1)
    if registry in DOCKER_HUB and "/" not in repository:
        repository = "library/" + repository
    return registry, repository, digest or tag or "latest"


@functools.lru_cache(maxsize=None)
def pullable(image: str) -> bool | None:
    """Whether the image's registry serves it to anyone, as a cloud builder with no credentials pulls it.
    None when the registry could not be reached. Sends only HEAD requests, which Docker Hub does not count as pulls."""
    registry, repository, reference = image_reference(image)
    host = "registry-1.docker.io" if registry in DOCKER_HUB else registry
    if host in _unreachable:
        return None
    url = f"https://{host}/v2/{repository}/manifests/{reference}"
    status, challenge = manifest_status(url)
    if status == 401 and challenge.lower().startswith("bearer "):
        token = anonymous_token(challenge, repository)
        if token is None:
            return None
        if not token:
            return False
        status, _ = manifest_status(url, token)
    if status is None:
        _unreachable.add(host)
    return True if status == 200 else False if status in (401, 403, 404) else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Registry lookups follow no redirects, so a registry's answer cannot send them (or a token) elsewhere."""

    def redirect_request(self, *args, **kwargs):
        return None


def registry_open(request, timeout: float):
    return urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout)


def manifest_status(url: str, token: str | None = None) -> tuple[int | None, str]:
    """HTTP status of a manifest HEAD, with its WWW-Authenticate challenge; None when unreachable."""
    headers = {"Accept": MANIFEST_TYPES, **({"Authorization": f"Bearer {token}"} if token else {})}
    try:
        with registry_open(urllib.request.Request(url, headers=headers, method="HEAD"), REGISTRY_TIMEOUT) as response:
            return response.status, ""
    except urllib.error.HTTPError as exc:
        with exc:
            return exc.code, exc.headers.get("WWW-Authenticate", "") or ""
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        return None, ""


def anonymous_token(challenge: str, repository: str) -> str | None:
    """A pull token from the challenge's realm without credentials: '' when refused, None when unreachable."""
    params = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
    realm = params.pop("realm", "")
    if not realm.startswith("https://"):
        return None
    params.setdefault("scope", f"repository:{repository}:pull")
    try:
        with registry_open(f"{realm}?{urllib.parse.urlencode(params)}", REGISTRY_TIMEOUT) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        with exc:
            return "" if exc.code in (401, 403) else None
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        return None
    return (data.get("token") or data.get("access_token") or "") if isinstance(data, dict) else ""


def check_task_images(task: Path, config: dict, relai_dir: Path, report: Report, cloud: bool = False) -> None:
    """Cloud-only checks apply to the bundled builder, not to authorized local image infrastructure."""
    harness = harness_tag(relai_dir)
    for rel in ("environment/Dockerfile", "tests/Dockerfile"):
        if (task / rel).is_file():
            check_dockerfile((task / rel).read_text(errors="ignore"), rel, harness, report, cloud=cloud)
    if not cloud:
        return
    if (task / "environment" / "docker-compose.yaml").is_file():
        report.note("environment/docker-compose.yaml: the images it names were not checked for cloud builds")
    verifier = config.get("verifier", {}) or {}
    for table, section in (("environment", config.get("environment")), ("verifier.environment", verifier.get("environment"))):
        image = section.get("docker_image") if isinstance(section, dict) else None
        if not image or not isinstance(image, str):
            continue
        if image == harness:
            report.error(f"[{table}].docker_image is the harness image; Harbor pulls docker_image from a registry "
                         "and never builds it, so start FROM the harness image in a Dockerfile instead")
        elif pullable(image) is False:
            report.warn(f"[{table}].docker_image {image!r} cannot be pulled without credentials; a cloud run "
                        "needs a registry secret for it")


def harbor_load(tasks: list[Path], version: str | None) -> dict:
    if not version or not shutil.which("uv"):  # check_harbor reports a missing version
        return {}
    command = ["uv", "tool", "run", "--python", HARBOR_PYTHON, "--from", f"harbor=={version}",
               "python", "-c", HARBOR_LOAD, *map(str, tasks)]
    try:
        ran = subprocess.run(command, capture_output=True, text=True, timeout=600)
        return json.loads(ran.stdout.strip().splitlines()[-1]) if ran.returncode == 0 else {
            str(t): f"could not run Harbor's loader: {ran.stderr.strip()[-500:]}" for t in tasks}
    except (subprocess.TimeoutExpired, ValueError, IndexError):
        return {}


def synthetic(empty: bool) -> dict:
    return {
        "schema_version": "ATIF-v1.7",
        "agent": {"name": "relai-synthetic", "version": "0"},
        "steps": [
            {"step_id": 1, "source": "user", "message": "Hello, I need help with my request."},
            {"step_id": 2, "source": "agent",
             "message": "" if empty else "Sure, I can help. Could you tell me more about what you need?"},
        ],
    }


@functools.cache
def container_cli() -> str | None:
    """The first OCI engine CLI on PATH whose engine answers: docker (Docker Desktop, OrbStack, Colima,
    Rancher Desktop and other Docker-compatible engines), then podman."""
    for cli in ("docker", "podman"):
        if shutil.which(cli):
            try:
                if subprocess.run([cli, "info"], capture_output=True, timeout=30).returncode == 0:
                    return cli
            except subprocess.TimeoutExpired:
                continue
    return None


def engine(cli: str, *args: str, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([cli, *args], capture_output=True, text=True, timeout=timeout)


def run_verifier(task: Path, config: dict, report: Report, fixture: Path | None) -> None:
    cli = container_cli()
    if not cli:
        report.error("--verifier needs a running container engine with a docker- or podman-compatible CLI on PATH")
        return
    separate = is_separate(config)
    section = (config.get("verifier", {}) or {}).get("environment", {}) if separate else config.get("environment", {})
    image = (section or {}).get("docker_image")
    context = task / ("tests" if separate else "environment")
    if not image:
        if not (context / "Dockerfile").is_file():
            report.note(f"--verifier skipped: no Dockerfile in {context.name}/ to build the verifier from")
            return
        image = "relai-check:" + hashlib.sha256(str(context.resolve()).encode()).hexdigest()[:12]
        built = engine(cli, "build", "-q", "-t", image, str(context))
        if built.returncode:
            report.error(f"verifier image build failed: {built.stderr.strip()[-1500:]}")
            return
    evaluators = declared_evaluators(config)
    codes = [ev for ev in evaluators if ev.get("type") == "code"]
    if not codes:
        report.note("no code evaluators; judges are scored after the trial, so --verifier only checks that test.sh runs")
    empty_scores: list[float] = []
    for case in ("normal", "empty-reply"):
        # Stage under relai/work/tmp: VM-based engines (Colima, Podman machine and others) may share only
        # the home directory with the VM, so a bind mount from the system temp directory arrives empty.
        stage = relai_root() / "work" / "tmp"
        stage.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="relai-verifier-", dir=stage) as tmp:
            logs = Path(tmp) / "logs"
            (logs / "verifier").mkdir(parents=True)
            if fixture:
                shutil.copytree(fixture, logs / "agent")
            else:
                (logs / "agent").mkdir()
            (logs / "agent" / "trajectory.json").write_text(json.dumps(synthetic(case == "empty-reply")))
            for directory in (logs, logs / "agent", logs / "verifier"):
                directory.chmod(0o777)
            mounts = ["-v", f"{logs}:/logs"]
            if not separate:  # shared mode: Harbor uploads tests/; mount a writable copy
                tests_copy = Path(tmp) / "tests"
                shutil.copytree(task / "tests", tests_copy)
                mounts += ["-v", f"{tests_copy}:/tests"]
            # Like Harbor: make test.sh executable, run it, capture its output.
            script = ("chmod +x /tests/test.sh 2>/dev/null; "
                      "if [ -x /tests/test.sh ]; then /tests/test.sh; else sh /tests/test.sh; fi "
                      "> /logs/verifier/test-stdout.txt 2>&1; echo $? > /logs/verifier/exit-code.txt")
            try:
                ran = engine(cli, "run", "--rm", *mounts, "--entrypoint", "sh", image, "-c", script, timeout=900)
            except subprocess.TimeoutExpired:
                report.error(f"{case}: verifier did not finish within 15 minutes")
                continue
            if ran.returncode:
                report.error(f"{case}: {cli} run failed: {ran.stderr.strip()[-800:]}")
                continue
            rewards, feedback, errors = read_verifier_outputs(logs / "verifier", case, report)
            for ev in codes:
                ev_id, low, high = ev.get("id"), ev.get("min_score", 0.0), ev.get("max_score", 1.0)
                value = rewards.get(ev_id)
                if ev_id in errors and value is None:
                    hint = "" if fixture else (" If it reads state the harness exports to /logs/agent, pass that state "
                                               "with --fixture DIR")
                    report.error(f"{case}: evaluator {ev_id} reported an error on a well-formed trajectory: "
                                 f"{str(errors[ev_id])[-600:]}.{hint}")
                    continue
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                    report.error(f"{case}: reward.json has no numeric score for declared evaluator {ev_id}")
                    continue
                if not low <= value <= high:
                    report.error(f"{case}: evaluator {ev_id} scored {value}, outside [{low}, {high}]")
                if not str(feedback.get(ev_id, "")).strip():
                    report.error(f"{case}: feedback.json has no feedback for evaluator {ev_id}")
                if case == "empty-reply":
                    empty_scores.append(normalized(value, low, high))
            for key in rewards:
                if key not in {ev.get("id") for ev in evaluators}:
                    report.warn(f"{case}: reward.json key {key!r} is not a declared evaluator")
    has_judges = any(ev.get("type") == "judge" for ev in evaluators)
    prohibition = config.get("metadata", {}).get("relai", {}).get("prohibition", False)
    if codes and not has_judges and empty_scores and min(empty_scores) >= 1.0 and not prohibition:
        report.error("every evaluator gives full marks to an empty reply, so this test cannot fail. If it only "
                     "tests a prohibition, set [metadata.relai].prohibition = true")


def read_verifier_outputs(verifier: Path, case: str, report: Report):
    rewards: dict = {}
    if (verifier / "reward.json").is_file():
        try:
            rewards = json.loads((verifier / "reward.json").read_text())
        except json.JSONDecodeError as exc:
            report.error(f"{case}: reward.json is not JSON: {exc}")
        if not isinstance(rewards, dict):
            report.error(f"{case}: reward.json must be an object of evaluator id to number")
            rewards = {}
    elif (verifier / "reward.txt").is_file():
        report.error(f"{case}: verifier wrote reward.txt; write reward.json with one key per declared code evaluator")
    else:
        stdout = (verifier / "test-stdout.txt")
        tail = stdout.read_text(errors="replace")[-800:] if stdout.is_file() else ""
        report.error(f"{case}: verifier wrote no reward file. test.sh output tail:\n{tail}")
    feedback, errors = {}, {}
    for name, target in (("feedback.json", feedback), ("errors.json", errors)):
        path = verifier / name
        if path.is_file():
            try:
                data = json.loads(path.read_text())
                if isinstance(data, dict):
                    target.update(data)
                else:
                    report.error(f"{case}: {name} must be a JSON object keyed by evaluator id")
            except json.JSONDecodeError as exc:
                report.error(f"{case}: {name} is not JSON: {exc}")
    return rewards, feedback, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tasks", nargs="+", help="task directories (for example relai/tests/<id>)")
    parser.add_argument("--verifier", action="store_true", help="also run the verifier on synthetic trajectories (docker or podman)")
    parser.add_argument("--fixture", help="directory whose files are copied into /logs/agent for --verifier")
    parser.add_argument("--no-harbor", action="store_true", help="skip Harbor's own task loading")
    parser.add_argument("--cloud", action="store_true", help="also check portability to the bundled hosted Harbor builder")
    parser.add_argument("--relai-dir", help="the relai/ directory (default: inferred)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    relai_dir = relai_root(args.relai_dir)
    tasks = [Path(raw).resolve() for raw in args.tasks]
    suite = Report()
    try:
        kind, isolation = runner_settings(relai_dir)
        config = evals_config(relai_dir)
        mark = pass_mark(config)
        if mark is None and kind == "native" and (relai_dir / "relai.toml").is_file():
            suite.warn("[scoring].pass_mark is not set yet; there is no default. Choose it with the user "
                       "after the first scored run, before reporting any test as passed or failed")
    except (ValueError, OSError) as exc:
        suite.error(str(exc))
        return suite.emit("relai.toml", args.json)
    native = kind == "native"
    if native and args.cloud:
        suite.note("--cloud checks the bundled Harbor builder only; validate native hosting through its own integration")
    if native and isolation == "host":
        suite.note("host execution requires explicit authorization and reviewed containment; the launcher is not a sandbox")
    scan_secrets([relai_dir / "relai.toml"] if (relai_dir / "relai.toml").is_file() else [],
                 secret_values(relai_dir), relai_dir, suite)
    loaded = {} if args.no_harbor or native or suite.errors else harbor_load(tasks, harbor_version(relai_dir))
    fixture = Path(args.fixture).resolve() if args.fixture else None
    status = 0
    if not native and not suite.errors:
        check_harbor(relai_dir, suite, judged=has_judges(tasks), cloud=args.cloud,
                     neutral_only=all_agent_neutral(tasks))
    status |= suite.emit("relai.toml", args.json)
    for task in tasks:
        report = Report()
        config = check_static(task, relai_dir, report, native, cloud=args.cloud)
        if loaded.get(str(task)):
            report.error(f"Harbor cannot load it: {loaded[str(task)]}")
        elif not args.no_harbor and not native and not loaded:
            report.note("Harbor's own task loading did not run (uv missing or Harbor unavailable)")
        if args.verifier and native:
            report.error("--verifier is Harbor-only; demonstrate native grading on synthetic passing, failing and empty-reply trials")
        elif args.verifier and config and is_agent_neutral(config):
            report.note("--verifier does not apply to an agent-neutral task: run Harbor's oracle and nop agents on it "
                        "(no model cost)")
        elif args.verifier and config and not report.errors:
            run_verifier(task, config, report, fixture)
        elif args.verifier and report.errors:
            report.note("--verifier skipped until the static errors are fixed")
        status |= report.emit(f"task {test_key(task, relai_dir)}", args.json)
    return status


if __name__ == "__main__":
    sys.exit(main())
