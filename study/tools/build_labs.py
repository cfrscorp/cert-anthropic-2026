#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "markdown>=3.5",
# ]
# ///
"""Generate study/content/labs.json so the study app can browse the labs offline.

Walks ../labs/lab-*/, renders each lab's README.md and SOLUTION.md from Markdown
to HTML at BUILD TIME (so the browser needs no Markdown parser and the app keeps
its zero-runtime-dependency, fully-offline model), and writes a single
study/content/labs.json the Labs view reads. Re-run whenever the labs change.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import markdown

__version__ = "1.1.0"

STUDY = Path(__file__).resolve().parent.parent
LABS = STUDY.parent / "labs"
OUT = STUDY / "content" / "labs.json"

_MD_EXTENSIONS = ["fenced_code", "tables", "sane_lists"]
_SCRIPT_RE = re.compile(r"<script.*?>.*?</script>", re.S | re.I)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)


def render_md(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    html = markdown.markdown(text, extensions=_MD_EXTENSIONS)
    return _SCRIPT_RE.sub("", html)  # defensive: strip any raw <script>


def title_of(readme: Path, slug: str) -> str:
    if readme.exists():
        m = _H1_RE.search(readme.read_text(encoding="utf-8"))
        if m:
            return m.group(1).strip()
    return slug


def lab_number(slug: str) -> int:
    m = re.match(r"lab-(\d+)-", slug)
    return int(m.group(1)) if m else 999


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="build_labs.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Render the labs' README/SOLUTION to HTML into study/content/labs.json for the Labs view.",
        epilog=(
            "Examples:\n"
            "  # Regenerate study/content/labs.json from the current labs/:\n"
            "  uv run study/tools/build_labs.py\n\n"
            "  # Print the version:\n"
            "  uv run study/tools/build_labs.py --version\n"
        ),
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    lab_dirs = sorted(
        (d for d in LABS.glob("lab-*") if d.is_dir()),
        key=lambda d: lab_number(d.name),
    )
    if not lab_dirs:
        print(f"ERROR: no labs found under {LABS}", file=sys.stderr)
        return 1

    labs = []
    for d in lab_dirs:
        readme, solution = d / "README.md", d / "SOLUTION.md"
        labs.append({
            "slug": d.name,
            "number": lab_number(d.name),
            "title": title_of(readme, d.name),
            "readme_html": render_md(readme),
            "solution_html": render_md(solution),
        })
        print(f"  ✓ {d.name}  ({len(labs[-1]['readme_html'])} B readme, {len(labs[-1]['solution_html'])} B solution)")

    OUT.write_text(json.dumps(labs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(STUDY.parent)} with {len(labs)} labs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
