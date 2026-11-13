#!/usr/bin/env python3
"""Check the RELAI wiki in relai/wiki/ and the pages tests cite.

Usage:
  python3 relai/bin/check_wiki.py [relai] [--json]

Pages live in relai/wiki/{requirements,risks,open-questions}/<id>.md; a page's id is its
file name. Checks: ids are lowercase slugs and unique across the three folders, each page
starts with a '# ' title, local links in typed pages and a present wiki/index.md resolve (missing attachments warn), and every id a test or
benchmark lists in [metadata.relai].covers exists. Managed wiki/attachments/**/*.json
files must parse as UTF-8 JSON; this checks format, not evidence accuracy. Read-only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, relai_root, load_toml  # noqa: E402

KINDS = ("requirements", "risks", "open-questions")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
LINK_RE = re.compile(r"\]\((<[^>]+>|[^)\s]+)(?:\s+[^)]*)?\)")
RISK_FIELDS = ("mechanism", "trigger", "observable failure")


def check_links(page: Path, relai_dir: Path, report: Report) -> None:
    rel = page.relative_to(relai_dir)
    for target in LINK_RE.findall(page.read_text(encoding="utf-8", errors="replace")):
        raw = target.strip("<>")
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw) or raw.startswith("//"):
            continue  # external targets are outside this local-file check
        link = urlsplit(raw)
        if not link.path:
            continue
        path = page.parent / unquote(link.path)
        if not path.is_file():
            emit = report.error if path.suffix.lower() == ".md" else report.warn
            emit(f"{rel}: link to {target} does not resolve")


def check_attachments(relai_dir: Path, report: Report) -> None:
    """Parse managed JSON without following attachment symlinks or rewriting evidence."""
    root = relai_dir / "wiki" / "attachments"
    for folder in (root.parent, root):
        if folder.is_symlink():
            report.error(f"{folder.relative_to(relai_dir)}: attachment scan cannot follow a symlink")
            return
    if not root.exists():
        return

    def unreadable(exc: OSError) -> None:
        path = Path(exc.filename) if exc.filename else root
        report.error(f"{path.relative_to(relai_dir)}: cannot read attachments ({exc.strerror})")

    class NonstandardConstantError(ValueError):
        pass

    def reject_constant(value: str) -> None:
        raise NonstandardConstantError

    for folder, dirs, files in os.walk(root, followlinks=False, onerror=unreadable):
        for name in sorted(dirs):
            path = Path(folder) / name
            if path.is_symlink():
                dirs.remove(name)
                report.error(f"{path.relative_to(relai_dir)}: attachment scan cannot follow a symlink")
        for name in sorted(files):
            path = Path(folder) / name
            if path.suffix.lower() != ".json":
                continue
            rel = path.relative_to(relai_dir)
            if path.is_symlink():
                report.error(f"{rel}: attachment scan cannot follow a symlink")
                continue
            try:
                text = path.read_bytes().decode("utf-8")
                json.loads(text, parse_constant=reject_constant)
            except UnicodeDecodeError as exc:
                report.error(f"{rel}: invalid UTF-8 at byte {exc.start}")
            except json.JSONDecodeError as exc:
                report.error(f"{rel}:{exc.lineno}:{exc.colno}: invalid JSON ({exc.msg})")
            except NonstandardConstantError:
                report.error(f"{rel}: invalid JSON (non-standard numeric constant)")
            except ValueError:
                report.error(f"{rel}: cannot parse JSON numeric value")
            except OSError as exc:
                report.error(f"{rel}: cannot read JSON ({exc.strerror})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("relai_dir_arg", nargs="?", metavar="RELAI_DIR", help="the relai/ directory (default: inferred)")
    parser.add_argument("--relai-dir", help="same as RELAI_DIR")
    parser.add_argument("--json", action="store_true", help="machine-readable output on stdout")
    args = parser.parse_args()
    relai_dir = relai_root(args.relai_dir or args.relai_dir_arg)
    wiki = relai_dir / "wiki"
    report = Report()
    pages: dict[str, Path] = {}
    if not wiki.is_dir():
        report.note("relai/wiki/ does not exist yet")
    for kind in KINDS:
        folder = wiki / kind
        if not folder.is_dir():
            continue
        for page in sorted(folder.glob("*.md")):
            page_id = page.stem
            rel = page.relative_to(relai_dir)
            if not ID_RE.match(page_id):
                report.error(f"{rel}: the file name is the page id and must be a lowercase slug")
            if page_id in pages:
                report.error(f"{rel}: id {page_id!r} is also used by {pages[page_id].relative_to(relai_dir)}")
            pages[page_id] = page
            text = page.read_text(encoding="utf-8", errors="replace")
            first = next((line for line in text.splitlines() if line.strip()), "")
            if not first.startswith("# "):
                report.error(f"{rel}: the first line must be a '# ' title")
            if kind == "risks":
                lowered = text.lower()
                missing = [f for f in RISK_FIELDS if f not in lowered]
                if missing:
                    report.warn(f"{rel}: a risk should state its {', '.join(missing)}")
            check_links(page, relai_dir, report)
        for other in sorted(p for p in folder.iterdir() if p.suffix != ".md" and not p.name.startswith(".")):
            report.warn(f"{other.relative_to(relai_dir)}: only .md pages belong in {kind}/")

    index = wiki / "index.md"
    if index.is_file():
        check_links(index, relai_dir, report)
    report.note("Local links checked in typed wiki pages and a present wiki/index.md; "
                "other documents, reference-style links and fragment destinations are not checked")
    check_attachments(relai_dir, report)

    for kind in ("tests", "benchmarks"):
        base = relai_dir / kind
        if not base.is_dir():
            continue
        for toml_path in sorted(base.rglob("task.toml")):  # benchmark rows sit at benchmarks/<id>/rows/<n>/
            try:
                covers = load_toml(toml_path).get("metadata", {}).get("relai", {}).get("covers", []) or []
            except Exception as exc:
                report.error(f"{toml_path.relative_to(relai_dir)} does not parse: {exc}")
                continue
            for ref in covers:
                if ref not in pages:
                    report.error(f"{toml_path.relative_to(relai_dir)} covers {ref!r}, which is not a wiki page")
    report.note(f"{len(pages)} wiki pages")
    return report.emit("wiki", args.json)


if __name__ == "__main__":
    sys.exit(main())
