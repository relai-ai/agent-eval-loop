"""Shared helpers for the RELAI checkers. Standard library only (Python 3.11+)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

HARBOR_PYTHON = "3.12"

# Directories that never belong in a task, a build context or a snapshot.
JUNK_DIRS = {
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", ".nox",
    "node_modules", ".venv", "venv", ".git", ".hg", ".svn",
}

SECRET_PATTERNS = {
    "AWS access key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "Anthropic key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    "OpenAI key": re.compile(r"\bsk-(proj-)?[A-Za-z0-9_-]{32,}"),
    "GitHub token": re.compile(r"\b(ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "Slack token": re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}"),
    "Stripe live key": re.compile(r"\bsk_live_[A-Za-z0-9]{20,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}

PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?P<label>[A-Z ]*PRIVATE KEY)-----.*?-----END (?P=label)-----", re.DOTALL
)

TEXT_SCAN_LIMIT = 2 * 1024 * 1024  # skip larger files when scanning for secrets


@dataclass
class Report:
    """Collects every independent issue so the caller sees them all at once."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)

    def extend(self, other: "Report", prefix: str = "") -> None:
        self.errors += [prefix + m for m in other.errors]
        self.warnings += [prefix + m for m in other.warnings]
        self.notes += [prefix + m for m in other.notes]

    def emit(self, title: str, as_json: bool = False) -> int:
        if as_json:
            print(json.dumps({"title": title, "ok": not self.errors, "errors": self.errors,
                              "warnings": self.warnings, "notes": self.notes}, indent=2))
        else:
            status = "FAIL" if self.errors else "PASS"
            print(f"{status}: {title}")
            for message in self.errors:
                print(f"  error: {message}")
            for message in self.warnings:
                print(f"  warning: {message}")
            for message in self.notes:
                print(f"  note: {message}")
        return 1 if self.errors else 0


ENV_EXAMPLE_NAMES = {".env.example", ".env.sample", ".env.template"}


def relai_root(explicit: str | None = None) -> Path:
    """The relai/ directory: --relai-dir, else the parent of bin/, else ./relai.

    The copy inside the plugin (skills/start/template/bin) is a template, never a project's relai/.
    """
    if explicit:
        return Path(explicit).resolve()
    here = Path(__file__).resolve().parent
    is_template = (here.parent.name == "template" and here.parent.parent.name == "start"
                   and here.parent.parent.parent.name == "skills")
    if here.name == "bin" and (here.parent / "README.md").exists() and not is_template:
        return here.parent
    return (Path.cwd() / "relai").resolve()


def test_key(task_dir: Path, relai_dir: Path) -> str:
    """A test's identity: its path relative to relai/ (tests/<id>, benchmarks/<id>/...), else its name."""
    task_dir = task_dir.resolve()
    if task_dir.is_relative_to(relai_dir):
        return task_dir.relative_to(relai_dir).as_posix()
    return task_dir.name


def resolve_task_dir(raw: str, relai_dir: Path, job_dir: Path | None = None) -> Path | None:
    """Find the task directory a Harbor trial ran. Harbor records -p exactly as typed, so a relative
    path is tried against the directory Harbor ran in (inferred from the job's jobs_dir), the current
    directory, the repository root and relai/. Returns None when no candidate holds a task.toml."""
    if not raw:
        return None
    path = Path(raw).expanduser()
    candidates = [path] if path.is_absolute() else []
    if not path.is_absolute():
        roots = []
        if job_dir is not None:
            config = job_dir / "config.json"
            try:
                jobs_dir = load_json(config).get("jobs_dir") if config.is_file() else None
            except (OSError, json.JSONDecodeError):
                jobs_dir = None
            if jobs_dir and not Path(jobs_dir).is_absolute():
                parts = [p for p in Path(jobs_dir).parts if p != "."]
                base = job_dir.resolve().parent
                if not parts or list(base.parts[-len(parts):]) == parts:
                    roots.append(Path(*base.parts[:len(base.parts) - len(parts)]))
        roots += [Path.cwd(), relai_dir.parent, relai_dir]
        candidates += [root / path for root in roots]
        candidates += [relai_dir / "tests" / path.name]
    for candidate in candidates:
        if (candidate / "task.toml").is_file():
            return candidate.resolve()
    return None


def repo_root(relai_dir: Path) -> Path:
    return relai_dir.parent


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def evals_config(relai_dir: Path) -> dict:
    path = relai_dir / "relai.toml"
    return load_toml(path) if path.exists() else {}


def harbor_version(relai_dir: Path) -> str | None:
    """[harbor].version: the exact Harbor release this suite runs with, recorded at setup."""
    harbor = evals_config(relai_dir).get("harbor")
    version = harbor.get("version") if isinstance(harbor, dict) else None
    return version if isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version) else None


RUNNER_KINDS = ("harbor", "native")


def runner_settings(relai_dir: Path) -> tuple[str, str]:
    """A missing [runner] means Harbor in containers; malformed declarations never fall back."""
    config = evals_config(relai_dir)
    runner = config.get("runner", {})
    if not isinstance(runner, dict):
        raise ValueError("[runner] must be a table")
    kind, isolation = runner.get("kind", "harbor"), runner.get("isolation", "container")
    if kind not in RUNNER_KINDS:
        raise ValueError("[runner].kind must be 'harbor' or 'native'")
    if isolation not in ("container", "host"):
        raise ValueError("[runner].isolation must be 'container' or 'host'")
    if kind == "harbor" and isolation != "container":
        raise ValueError("the Harbor runner requires container isolation")
    return kind, isolation


def pass_mark(config: dict):
    """Runner-independent threshold from [scoring].pass_mark; there is no default."""
    scoring = config.get("scoring", {})
    if not isinstance(scoring, dict):
        raise ValueError("[scoring] must be a table")
    value = scoring.get("pass_mark")
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                              or not 0 <= value <= 1):
        raise ValueError("[scoring].pass_mark must be a number from 0 to 1")
    return value


def secret_values(relai_dir: Path) -> dict[str, str]:
    """Values from relai/.env, used only to detect and redact them. Never print these."""
    path = relai_dir / ".env"
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip().strip("'\"")
        if len(value) >= 8:
            values[name.strip().removeprefix("export ").strip()] = value
    return values


def redaction_values(relai_dir: Path, env_names=()) -> dict[str, str]:
    """Known secrets for redaction, retaining file values when the environment overrides them."""
    values = secret_values(relai_dir)
    for name in set(env_names):
        value = os.environ.get(name)
        if value:
            values[f"{name} (environment)"] = value
    return values


def redact(text: str, values: dict[str, str]) -> str:
    for name, value in sorted(values.items(), key=lambda item: len(item[1]), reverse=True):
        text = text.replace(value, f"[redacted {name}]")
    text = PRIVATE_KEY_BLOCK.sub("[redacted private key]", text)
    for label, pattern in SECRET_PATTERNS.items():
        text = pattern.sub(f"[redacted {label}]", text)
    return text


def expand_globs(root: Path, patterns: list[str]) -> list[Path]:
    """Files matching gitignore-like patterns; a trailing ** or a directory means everything under it.
    (Path.glob('x/**') yields only directories before Python 3.13.)"""
    files: set[Path] = set()
    for pattern in patterns:
        pattern = pattern.strip().lstrip("/")
        if pattern.endswith("**"):
            pattern += "/*"
        for match in root.glob(pattern):
            if match.is_dir():
                files.update(p for p in match.rglob("*") if p.is_file())
            elif match.is_file():
                files.add(match)
    return sorted(files)


def walk_files(root: Path, skip_dirs: set[str] = frozenset()):
    """Yield files under root, not descending into skip_dirs."""
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in skip_dirs)
        for name in sorted(files):
            yield Path(current) / name


def scan_secrets(paths, values: dict[str, str], base: Path, report: Report) -> None:
    for path in paths:
        try:
            if path.is_symlink() or path.stat().st_size > TEXT_SCAN_LIMIT:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(base) if path.is_relative_to(base) else path
        for name, value in values.items():
            if value in text:
                report.error(f"{rel} contains the value of {name} from relai/.env")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                report.error(f"{rel} contains what looks like a {label}")


def dir_digest(root: Path, exclude_names: set[str] = frozenset({"README.md"})) -> str:
    """sha256 over sorted relative paths and file bytes, skipping junk dirs and exclude_names at the top level."""
    digest = hashlib.sha256()
    for path in walk_files(root, JUNK_DIRS):
        rel = path.relative_to(root).as_posix()
        if rel in exclude_names:
            continue
        digest.update(rel.encode() + b"\0")
        digest.update(path.read_bytes() if not path.is_symlink() else os.readlink(path).encode())
        digest.update(b"\0")
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_state(relai_dir: Path) -> dict:
    path = relai_dir / "frozen.json"
    return load_json(path) if path.exists() else {"tests": {}}


def declared_evaluators(task_toml: dict) -> list[dict]:
    return list(task_toml.get("metadata", {}).get("relai", {}).get("evaluators", []) or [])


def normalized(score: float, low: float, high: float) -> float:
    if high == low:
        return 1.0 if score >= high else 0.0
    return min(1.0, max(0.0, (score - low) / (high - low)))


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)
