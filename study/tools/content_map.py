#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Content dependency report for the shared pool.

Every exam's study/exams/<slug>/map.json lists the pool items it uses (and the
task each counts toward); its exam.json pins the components it draws them
from. This tool reads those manifests and reports the reverse view: which
exams use each component and item, and what's orphaned — pool items no exam
maps, and components no exam pins. Nothing is written; the report is computed
on demand, so it can't drift from the manifests.

Exams are every study/exams/<slug>/ directory with an exam.json, including
ones not yet listed in exams/index.json (marked "unlisted": in development,
not shown in the app), since they're consumers too.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

__version__ = "1.0.0"

STUDY = Path(__file__).resolve().parents[1]
CONTENT = STUDY / "content"
EXAMS_DIR = STUDY / "exams"
MAPPED_KINDS = ("questions", "flashcards", "concepts")

EPILOG = """\
Examples:
  # Summary: per component, its size, which exams pin it, and how many of its items each maps
  uv run study/tools/content_map.py

  # List orphans: pool items no exam maps, and components no exam pins
  uv run study/tools/content_map.py --orphans

  # Where is one item used (component, exams, task in each)?
  uv run study/tools/content_map.py --item q-0001

  # Only consider one exam as a consumer (e.g. what would be orphaned without the others)
  uv run study/tools/content_map.py --exam ccarf --orphans

  # Machine-readable output (any of the above)
  uv run study/tools/content_map.py --json

  # Show the script version
  uv run study/tools/content_map.py --version
"""


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: could not read {path}: {exc}")


def load_state(only_exam: str | None = None) -> dict:
    """Components (with their item ids) and exams (with pins and maps)."""
    listed = _load(EXAMS_DIR / "index.json")["exams"]
    components = {}
    for comp in _load(CONTENT / "components.json")["components"]:
        entries = _load(CONTENT / comp["file"])
        # Labs aren't mapped (exams link them per task in exam.json), so only
        # the mapped kinds contribute item ids.
        ids = [item["id"] for item in entries] if comp["kind"] in MAPPED_KINDS else []
        components[comp["id"]] = {**comp, "items": ids, "count": len(entries)}
    exams = {}
    for exam_file in sorted(EXAMS_DIR.glob("*/exam.json")):
        exam = _load(exam_file)
        map_file = exam_file.with_name("map.json")
        exams[exam["slug"]] = {
            "code": exam["code"],
            "listed": exam["slug"] in listed,
            "pins": {pin["component"]: pin["version"] for pins in exam["sections"].values() for pin in pins},
            "map": _load(map_file) if map_file.is_file() else {kind: {} for kind in MAPPED_KINDS},
        }
    if only_exam is not None:
        if only_exam not in exams:
            raise SystemExit(f"error: unknown exam {only_exam!r} (exams: {', '.join(exams)})")
        exams = {only_exam: exams[only_exam]}
    return {"components": components, "exams": exams}


def build_report(state: dict) -> dict:
    components, exams = state["components"], state["exams"]
    report = {"exams": {slug: {"code": e["code"], "listed": e["listed"]} for slug, e in exams.items()},
              "components": {}, "orphan_components": [], "orphan_items": {}, "dangling": []}
    for cid, comp in components.items():
        pinned_by = {slug: e["pins"][cid] for slug, e in exams.items() if cid in e["pins"]}
        mapped = {}
        if comp["kind"] in MAPPED_KINDS:
            ids = set(comp["items"])
            for slug, e in exams.items():
                mapped[slug] = sum(1 for item_id in e["map"][comp["kind"]] if item_id in ids)
            used = {item_id for e in exams.values() for item_id in e["map"][comp["kind"]]}
            orphans = [item_id for item_id in comp["items"] if item_id not in used]
            if orphans:
                report["orphan_items"][cid] = orphans
        report["components"][cid] = {"kind": comp["kind"], "version": comp["version"], "items": comp.get("count", len(comp["items"])),
                                     "pinned_by": pinned_by, "mapped": mapped}
        if not pinned_by:
            report["orphan_components"].append(cid)
    # Map entries naming items that don't exist (the test suite fails on these).
    all_ids = {item_id for comp in components.values() for item_id in comp["items"]}
    for slug, e in exams.items():
        for kind in MAPPED_KINDS:
            report["dangling"] += [f"{slug}:{item_id}" for item_id in e["map"][kind] if item_id not in all_ids]
    return report


def item_usage(state: dict, item_id: str) -> dict:
    owner = next((cid for cid, comp in state["components"].items() if item_id in comp["items"]), None)
    if owner is None:
        raise SystemExit(f"error: no pool item {item_id!r}")
    kind = state["components"][owner]["kind"]
    used_by = {slug: e["map"][kind][item_id] for slug, e in state["exams"].items() if item_id in e["map"][kind]}
    return {"item": item_id, "component": owner, "kind": kind, "used_by": used_by}


def _exam_label(report: dict, slug: str) -> str:
    e = report["exams"][slug]
    return e["code"] + ("" if e["listed"] else " (unlisted)")


def print_summary(report: dict) -> None:
    print("Exams: " + ", ".join(_exam_label(report, slug) for slug in report["exams"]))
    print()
    width = max(len(cid) for cid in report["components"])
    for cid, comp in report["components"].items():
        pins = ", ".join(f"{_exam_label(report, slug)} {spec}" for slug, spec in comp["pinned_by"].items()) or "not pinned"
        noun = "item(s)" if comp["kind"] in MAPPED_KINDS else "entries"
        print(f"  {cid:<{width}}  {comp['kind']:<10} v{comp['version']:<7} {comp['items']:>4} {noun:<7}  pinned by: {pins}")
        for slug, n in comp["mapped"].items():
            if n:
                print(f"  {'':<{width}}  {'':<10} {'':<8} {'':>4}          {_exam_label(report, slug)} maps {n}")
    n_orphans = sum(len(v) for v in report["orphan_items"].values())
    print()
    print(f"Orphans: {n_orphans} item(s), {len(report['orphan_components'])} component(s)"
          + (" — see --orphans" if n_orphans or report["orphan_components"] else ""))
    if report["dangling"]:
        print(f"Dangling map entries (no such item): {', '.join(report['dangling'])}")


def print_orphans(report: dict) -> None:
    if not report["orphan_components"] and not report["orphan_items"]:
        print("No orphans: every component is pinned and every pool item is mapped by at least one exam.")
        return
    for cid in report["orphan_components"]:
        print(f"Component not pinned by any exam: {cid}")
    for cid, ids in report["orphan_items"].items():
        print(f"{cid}: {len(ids)} item(s) no exam maps")
        for i in range(0, len(ids), 8):
            print("  " + "  ".join(ids[i:i + 8]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content_map.py",
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--orphans", action="store_true", help="List orphaned items and components instead of the summary.")
    parser.add_argument("--item", metavar="ID", help="Show where one pool item is used (its component, and each exam's task for it).")
    parser.add_argument("--exam", metavar="SLUG", help="Only count this exam as a consumer (default: every exam directory).")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    state = load_state(args.exam)
    if args.item:
        usage = item_usage(state, args.item)
        if args.json:
            print(json.dumps(usage, indent=2))
        else:
            where = ", ".join(f"{state['exams'][s]['code']} → task {t}" for s, t in usage["used_by"].items()) or "no exam (orphan)"
            print(f"{usage['item']} ({usage['component']}): {where}")
        return 0
    report = build_report(state)
    if args.json:
        print(json.dumps(report if not args.orphans else
                         {"orphan_components": report["orphan_components"], "orphan_items": report["orphan_items"]}, indent=2))
    elif args.orphans:
        print_orphans(report)
    else:
        print_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
