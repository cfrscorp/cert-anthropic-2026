"""Exam + content-component resolution shared by the CLI/TUI study tools.

A library module (imported by quiz.py and flashcards.py, and through them by
the TUI variants) — not a runnable script. It reads the same manifests as the
Web UI: study/exams/index.json (exam slugs, first = default),
study/exams/<slug>/exam.json (the components each section pins),
study/exams/<slug>/map.json (which pool items the exam uses, and the task each
counts toward), and study/content/components.json (component id -> file).

It also owns per-exam history paths and the one-time history migrations: the
single-exam (pre-BL-046) files into per-exam ones, and exam-prefixed item IDs
to neutral pool IDs (BL-050).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
CONTENT = STUDY / "content"
EXAMS_DIR = STUDY / "exams"
POOL_ID_MIGRATION = STUDY / "migrations" / "pool-ids-2026-10.json"
# Personal progress is scratch state, not project content, so it lives in the
# repo's gitignored .working/ directory rather than next to the tracked tools.
WORKING = STUDY.parent / ".working"


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: could not read {path}: {exc}")


def exam_slugs() -> list[str]:
    return _load(EXAMS_DIR / "index.json")["exams"]


def default_exam() -> str:
    return exam_slugs()[0]


def load_exam(slug: str) -> dict:
    if slug not in exam_slugs():
        raise SystemExit(f"error: unknown exam {slug!r} (available: {', '.join(exam_slugs())})")
    return _load(EXAMS_DIR / slug / "exam.json")


def section_sets(exam: dict, section: str) -> list[dict]:
    """The components an exam pins for a section, as {label, id, path}, in order."""
    registry = {c["id"]: c for c in _load(CONTENT / "components.json")["components"]}
    sets = []
    for pin in exam["sections"][section]:
        comp = registry.get(pin["component"])
        if comp is None:
            raise SystemExit(f"error: exam {exam['slug']} pins unknown component {pin['component']!r}")
        sets.append({"label": pin.get("label", comp["id"]), "id": comp["id"], "path": CONTENT / comp["file"]})
    return sets


def select_set_files(exam: dict, section: str, wanted: list[str] | None) -> list[Path]:
    """Resolve --set values (label or component id, case-insensitive; 'all' for
    every pinned set) to files. No --set means the exam's first pinned set."""
    sets = section_sets(exam, section)
    if not wanted:
        return [sets[0]["path"]]
    if any(w.lower() == "all" for w in wanted):
        return [s["path"] for s in sets]
    chosen = []
    for w in wanted:
        match = [s for s in sets if w.lower() in (s["label"].lower(), s["id"].lower())]
        if not match:
            available = ", ".join(f"{s['label'].lower()} ({s['id']})" for s in sets)
            raise SystemExit(f"error: {exam['code']} has no {section} set {w!r} (available: {available}, or 'all')")
        if match[0]["path"] not in chosen:
            chosen.append(match[0]["path"])
    return chosen


def item_tasks(exam: dict, section: str) -> dict[str, tuple[int, str]]:
    """The exam's map for one section: pool item id -> (domain, task). Pool
    items carry no exam tags; items the map doesn't list aren't in the exam."""
    mapping = _load(EXAMS_DIR / exam["slug"] / "map.json")[section]
    domain_of = {ts["id"]: ts["domain"] for ts in exam["task_statements"]}
    return {item_id: (domain_of[task], task) for item_id, task in mapping.items()}


def exam_tags(item: dict, item_tasks: dict | None) -> tuple[int, str] | None:
    """(domain, task) for a loaded item: its own tags if it has them (personal
    question/flashcard files may), else the exam map's; None if the item is a
    pool item this exam doesn't use."""
    if "task_statement" in item:
        return item["domain"], item["task_statement"]
    return (item_tasks or {}).get(item["id"])


def describe_sets(exam: dict, section: str) -> str:
    return ", ".join(s["label"].lower() for s in section_sets(exam, section))


# --------------------------------------------------------------------------
# CLI plumbing shared by quiz.py / flashcards.py (and their TUIs). `kind` names
# the history file ("quiz" / "flashcards"), `section` the exam section
# ("questions" / "flashcards"), `records_key` the history's per-item map.
# Printing goes through the calling tool's own color helpers (c, Color).
# --------------------------------------------------------------------------

def add_exam_arguments(parser, section: str, noun: str) -> None:
    default = default_exam()
    parser.add_argument(
        "--exam", metavar="SLUG", default=default,
        help=f"Exam to study: picks its {noun} sets, banner, and history file "
             f"(default: {default}; available: {', '.join(exam_slugs())}).",
    )
    parser.add_argument(
        "--set", dest="sets", action="append", metavar="NAME",
        help=f"{noun.capitalize()} set from the exam, by label or component id; repeatable, or 'all' "
             f"(default: the exam's first set; {default}: {describe_sets(load_exam(default), section)}). "
             "Can't be combined with explicit files.",
    )


def resolve_exam(parser, args, *, kind: str, section: str, records_key: str, c, Color) -> dict:
    """Apply --exam: per-exam default history (migrating the legacy single-exam
    file on first use, then any pre-pool history to pool IDs), the exam's item
    map (args.item_tasks), and, unless files were given, the --set files."""
    exam = load_exam(args.exam)
    if args.files and args.sets:
        parser.error(f"give {section} files or --set, not both")
    if args.history is None:
        args.history = history_path(kind, exam["slug"])
        if not args.reset_history:
            notice = migrate_legacy_history(kind, records_key, exam["slug"], args.history)
            if notice:
                print(c(f"note: {notice}", Color.DIM), file=sys.stderr)
    if not args.reset_history:
        notice = migrate_pool_ids(args.history, records_key, section)
        if notice:
            print(c(f"note: {notice}", Color.DIM), file=sys.stderr)
    args.item_tasks = item_tasks(exam, section)
    if not args.files and not args.reset_history:
        args.files = select_set_files(exam, section, args.sets)
    return exam


def reset_history(args, exam: dict, *, kind: str, records_key: str, c, Color) -> int:
    """--reset-history. While a legacy single-exam history file exists, the
    reset leaves an empty history behind (rather than deleting the file) so
    the legacy one isn't migrated back in on the next run."""
    keep_empty = legacy_would_reimport(kind, exam["slug"], args.history)
    if not args.history.exists() and not keep_empty:
        print(c(f"No history file at {args.history}; nothing to delete.", Color.YELLOW))
        return 0
    if not args.yes:
        answer = input(f"Delete all {exam['code']} progress history in {args.history}? [y/N] ").strip().lower()
        if answer != "y":
            print("Cancelled.")
            return 0
    if keep_empty:
        args.history.parent.mkdir(parents=True, exist_ok=True)
        args.history.write_text(json.dumps({"version": HISTORY_VERSION, records_key: {}, "sessions": []}, indent=2) + "\n", encoding="utf-8")
        print(c(f"Cleared {args.history} (kept as an empty file so the legacy history isn't re-imported).", Color.GREEN))
    else:
        args.history.unlink()
        print(c(f"Deleted {args.history}.", Color.GREEN))
    return 0


# History files are version 2 once their records use pool IDs (BL-050).
HISTORY_VERSION = 2


def history_path(kind: str, slug: str) -> Path:
    """Default per-exam history file, e.g. .working/quiz_history_ccarf.json."""
    return WORKING / f"{kind}_history_{slug}.json"


# --------------------------------------------------------------------------
# One-time migration from single-exam history (before BL-046)
# --------------------------------------------------------------------------
# Before multi-exam support, CCAR-F history lived in .working/quiz_history.json
# and .working/flashcards_history.json, keyed by unprefixed item IDs
# (q-1.1-001, fc-1.1-001), with sources named after the old data files. The
# first time a tool runs with its default per-exam history path and that file
# doesn't exist yet, the legacy file is copied in with IDs and source names
# re-keyed. It runs once — never over an existing per-exam file — so a personal
# question file whose IDs are still unprefixed keeps its own, separate records.
# The legacy file is left in place.
LEGACY_EXAM = "ccarf"
LEGACY_SOURCES = {
    "questions-standard.json": "ccarf-questions-standard.json",
    "questions-intermediate.json": "ccarf-questions-intermediate.json",
    "questions-hard.json": "ccarf-questions-hard.json",
    "flashcards.json": "ccarf-flashcards.json",
}


def _merge(a: dict | None, b: dict) -> dict:
    if a is None:
        return dict(b)
    newer = b if (b.get("last_seen") or "") > (a.get("last_seen") or "") else a
    return {
        **newer,
        "attempts": a.get("attempts", 0) + b.get("attempts", 0),
        "correct": a.get("correct", 0) + b.get("correct", 0),
    }


def rekey_legacy_history(history: dict, records_key: str, slug: str) -> dict:
    """Return a copy of a legacy history with IDs prefixed by `slug` (records
    saved under both forms are merged) and old data-file names mapped."""
    records: dict[str, dict] = {}
    for item_id, entry in history.get(records_key, {}).items():
        new_id = item_id if item_id.startswith(f"{slug}-") else f"{slug}-{item_id}"
        entry = dict(entry)
        if entry.get("source") in LEGACY_SOURCES:
            entry["source"] = LEGACY_SOURCES[entry["source"]]
        records[new_id] = _merge(records.get(new_id), entry)
    sessions = []
    for s in history.get("sessions", []):
        s = dict(s)
        s["source_files"] = [LEGACY_SOURCES.get(f, f) for f in s.get("source_files", [])]
        sessions.append(s)
    return {**history, records_key: records, "sessions": sessions}


def _legacy_path(kind: str) -> Path:
    return WORKING / f"{kind}_history.json"


def _is_default(kind: str, slug: str, path: Path) -> bool:
    return path.resolve() == history_path(kind, slug).resolve()


def legacy_would_reimport(kind: str, slug: str, path: Path) -> bool:
    """True if deleting `path` would let the legacy single-exam history be
    migrated back into it on the next run (it's the exam's default history
    file and a legacy file exists)."""
    return slug == LEGACY_EXAM and _is_default(kind, slug, path) and _legacy_path(kind).exists()


def migrate_legacy_history(kind: str, records_key: str, slug: str, path: Path) -> str | None:
    """Create `path` from the legacy single-exam history file if appropriate.
    Returns a one-line notice when a migration happened, else None."""
    legacy = _legacy_path(kind)
    if slug != LEGACY_EXAM or not _is_default(kind, slug, path) or path.exists() or not legacy.exists():
        return None
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        shutil.copyfile(legacy, path)  # let the tool's own loader warn about it
        return f"copied {legacy.name} → {path.name} (unreadable; not re-keyed)"
    migrated = rekey_legacy_history(data, records_key, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(migrated, indent=2) + "\n", encoding="utf-8")
    return f"migrated {len(migrated[records_key])} record(s) from {legacy.name} → {path.name} (original left in place)"


# --------------------------------------------------------------------------
# One-time migration to pool IDs (BL-050)
# --------------------------------------------------------------------------
# Content moved into an exam-neutral pool: ccarf-q-1.1-001 became q-0001 and
# ccarf-questions-standard.json became questions-standard.json (the committed
# map is study/migrations/pool-ids-2026-10.json). Any version-1 history file a
# tool opens — the per-exam default or an explicit --history — is re-keyed in
# place once: mapped IDs and file names are renamed (records landing on the
# same new ID are merged), anything unmapped (e.g. a personal question file's
# own IDs) is kept as-is, and the original is backed up beside it as
# <name>.v1.json.

def migrate_pool_ids(path: Path, records_key: str, section: str) -> str | None:
    """Re-key a version-1 history file to pool IDs. Returns a one-line notice
    when it did, else None."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None  # the tool's own loader warns about it
    if not isinstance(data, dict) or data.get("version", 1) >= HISTORY_VERSION:
        return None
    migration = _load(POOL_ID_MIGRATION)
    ids = migration[section]
    files = {f"{old}.json": f"{new}.json" for old, new in migration["components"].items()}
    records: dict[str, dict] = {}
    for item_id, entry in data.get(records_key, {}).items():
        entry = dict(entry)
        if entry.get("source") in files:
            entry["source"] = files[entry["source"]]
        new_id = ids.get(item_id, item_id)
        records[new_id] = _merge(records.get(new_id), entry)
    sessions = []
    for session in data.get("sessions", []):
        session = dict(session)
        session["source_files"] = [files.get(f, f) for f in session.get("source_files", [])]
        sessions.append(session)
    backup = path.with_name(f"{path.stem}.v1{path.suffix}")
    if not backup.exists():
        shutil.copyfile(path, backup)
    renamed = sum(1 for item_id in data.get(records_key, {}) if item_id in ids)
    path.write_text(json.dumps({**data, "version": HISTORY_VERSION, records_key: records, "sessions": sessions}, indent=2) + "\n",
                    encoding="utf-8")
    return f"re-keyed {renamed} record(s) in {path.name} to pool IDs (original kept as {backup.name})"
