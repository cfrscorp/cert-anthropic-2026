#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""A colorful, offline terminal flashcard runner for exam flashcard sets.

By default it reviews a flashcard set pinned by an exam (--exam, --set), or
reads explicit JSON files matching study/schema/flashcards.schema.json
(front, back, tags; pool cards get their domain/task from the exam's
map.json, while a personal file may carry its own domain + task_statement), runs an interactive self-graded
review session in the terminal ("Got it" / "Missed it"), and tracks personal
recall results across sessions in a small local JSON history file so you can
see progress over time and re-drill whatever you've missed.

This is the "core" module (data model, loading, history, filtering) for both
the classic scrolling CLI (this script, run directly) and the fixed-layout
TUI (flashcards_tui.py, which imports this module).
"""

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

__version__ = "1.2.0"

# exam_manifest.py lives alongside this script (shared with quiz.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import exam_manifest as em  # noqa: E402

# Deliberately a *separate* history file from quiz.py's — self-graded recall
# isn't exam-question mastery. -> .working/flashcards_history_<exam>.json
HISTORY_KIND = "flashcards"
HISTORY_SCHEMA_VERSION = em.HISTORY_VERSION  # 2: records keyed by pool IDs (BL-050)
EXAM_CODE = ""  # set by resolve_exam(); shown in the banner


# --------------------------------------------------------------------------
# Color (identical palette to quiz.py, kept independent so this script has
# zero import-time dependency on quiz.py — only flashcards_tui.py reuses it)
# --------------------------------------------------------------------------

class Color:
    """Minimal ANSI helper. Disabled automatically when not a TTY or via --no-color."""

    enabled = True

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    ORANGE = "\033[38;5;208m"

    @classmethod
    def wrap(cls, text, *codes):
        if not cls.enabled:
            return text
        return "".join(codes) + text + cls.RESET


def c(text, *codes):
    return Color.wrap(text, *codes)


def rule(char="─", width=72, color=Color.DIM):
    print(c(char * width, color))


def bar(pct, width=24, color=None):
    """A small colored proportion bar for percentages (0-100). Pass `color`
    to override the default green/yellow/red-by-pct coloring."""
    filled = round(width * max(0.0, min(100.0, pct)) / 100)
    color = color or (Color.GREEN if pct >= 80 else Color.YELLOW if pct >= 60 else Color.RED)
    return c("█" * filled, color) + c("░" * (width - filled), Color.DIM)


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

@dataclass
class Flashcard:
    id: str
    domain: int
    task_statement: str
    front: str
    back: str
    source: str
    tags: list = field(default_factory=list)


def load_flashcards(paths, item_tasks=None):
    """Load and merge one or more flashcards.json-schema files, tagging each
    card with the basename of the file it came from. Pool items take their
    domain/task from the exam's map (`item_tasks`, from em.item_tasks); ones the
    map doesn't list aren't part of the exam and are skipped."""
    cards = []
    seen_ids = {}
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SystemExit(f"error: could not read {path}: {exc}")
        if not isinstance(raw, list):
            raise SystemExit(f"error: {path} does not contain a JSON array of flashcards")
        for item in raw:
            try:
                tags = em.exam_tags(item, item_tasks)
                if tags is None:
                    continue
                card = Flashcard(
                    id=item["id"],
                    domain=tags[0],
                    task_statement=tags[1],
                    front=item["front"],
                    back=item["back"],
                    source=path.name,
                    tags=item.get("tags") or [],
                )
            except KeyError as exc:
                raise SystemExit(f"error: {path} has a flashcard missing required field {exc}")
            if card.id in seen_ids:
                print(
                    c(f"warning: duplicate flashcard id {card.id!r} in {path.name} "
                      f"(already loaded from {seen_ids[card.id]}); keeping the first one", Color.YELLOW),
                    file=sys.stderr,
                )
                continue
            seen_ids[card.id] = path.name
            cards.append(card)
    return cards


# --------------------------------------------------------------------------
# History (cumulative, cross-session self-graded recall tracking)
# --------------------------------------------------------------------------

def load_history(path):
    if not path.exists():
        return {"version": HISTORY_SCHEMA_VERSION, "cards": {}, "sessions": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print(c(f"warning: {path} is not valid JSON; starting a fresh history", Color.YELLOW), file=sys.stderr)
        return {"version": HISTORY_SCHEMA_VERSION, "cards": {}, "sessions": []}
    data.setdefault("version", HISTORY_SCHEMA_VERSION)
    data.setdefault("cards", {})
    data.setdefault("sessions", [])
    return data


def save_history(path, history):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")


def record_answer(history, card, got_it):
    entry = history["cards"].setdefault(
        card.id, {"attempts": 0, "correct": 0, "last_result": None, "last_seen": None, "source": card.source}
    )
    entry["attempts"] += 1
    entry["correct"] += 1 if got_it else 0
    entry["last_result"] = "correct" if got_it else "incorrect"
    entry["last_seen"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry["source"] = card.source


def record_session(history, *, source_files, filters, total, correct, duration_seconds):
    history["sessions"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_files": source_files,
        "filters": filters,
        "total": total,
        "correct": correct,
        "score_pct": round(100 * correct / total, 1) if total else 0.0,
        "duration_seconds": round(duration_seconds, 1),
    })


# --------------------------------------------------------------------------
# Filtering & selection
# --------------------------------------------------------------------------

def apply_filters(cards, args, history):
    pool = cards
    if args.domain is not None:
        pool = [c for c in pool if c.domain == args.domain]
    if args.task is not None:
        pool = [c for c in pool if c.task_statement == args.task]
    if args.tag is not None:
        pool = [c for c in pool if args.tag in c.tags]
    if args.review_missed:
        missed_ids = {
            cid for cid, entry in history["cards"].items()
            if entry.get("last_result") == "incorrect"
        }
        pool = [c for c in pool if c.id in missed_ids]
    return pool


def select_cards(pool, args):
    pool = list(pool)
    if args.shuffle:
        rng = random.Random(args.seed) if args.seed is not None else random.Random()
        rng.shuffle(pool)
    if args.num is not None:
        pool = pool[: args.num]
    return pool


# --------------------------------------------------------------------------
# Classic scrolling session (this script's own CLI mode)
# --------------------------------------------------------------------------

def print_banner():
    rule("═")
    print(c("  " + f"{EXAM_CODE} FLASHCARDS".strip(), Color.BOLD, Color.CYAN))
    rule("═")


def print_card_front(index, total, card):
    print()
    header = f"Card {index}/{total}"
    tag = f"Domain {card.domain} · Task {card.task_statement}"
    print(c(header, Color.BOLD, Color.CYAN) + c("   " + tag, Color.DIM))
    rule()
    print(c(card.front, Color.BOLD))
    print()


def prompt_reveal():
    raw = input(c("Press Enter to reveal ", Color.CYAN) + c("(or 'skip', 'quit')", Color.DIM) + c(": ", Color.CYAN)).strip().lower()
    if raw in ("q", "quit", "exit"):
        return "quit"
    if raw in ("s", "skip"):
        return "skip"
    return "reveal"


def prompt_grade():
    while True:
        raw = input(c("Got it? ", Color.CYAN) + c("(y/n, or 'skip', 'quit')", Color.DIM) + c(": ", Color.CYAN)).strip().lower()
        if raw in ("q", "quit", "exit"):
            return "quit"
        if raw in ("s", "skip"):
            return "skip"
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print(c("  Please enter 'y', 'n', 'skip', or 'quit'.", Color.YELLOW))


def show_back(card, got_it):
    print()
    print(c("  Answer: ", Color.BOLD) + card.back)
    print()
    if got_it:
        print(c("  ✓ Marked as got it.", Color.BOLD, Color.GREEN))
    else:
        print(c("  ✗ Marked as missed.", Color.BOLD, Color.RED))


def run_session(cards, history, history_path, source_files, filters):
    print_banner()
    print(c(f"  {len(cards)} card(s) loaded — reveal, then grade yourself. 'skip' / 'quit' anytime.\n", Color.DIM))
    start = datetime.now()
    correct_count = 0
    answered = 0
    for i, card in enumerate(cards, start=1):
        print_card_front(i, len(cards), card)
        choice = prompt_reveal()
        if choice == "quit":
            print(c("\nEnding session early.", Color.YELLOW))
            break
        if choice == "skip":
            print(c("  Skipped.", Color.DIM))
            continue

        print(c("  " + card.back, Color.DIM))
        grade = prompt_grade()
        if grade == "quit":
            print(c("\nEnding session early.", Color.YELLOW))
            break
        if grade == "skip":
            print(c("  Skipped.", Color.DIM))
            continue

        answered += 1
        if grade:
            correct_count += 1
        record_answer(history, card, grade)
        running_pct = 100 * correct_count / answered
        print(c(f"\n  Score so far: {correct_count}/{answered} ({running_pct:.0f}%)", Color.DIM))

    duration = (datetime.now() - start).total_seconds()
    if answered:
        record_session(
            history,
            source_files=source_files,
            filters=filters,
            total=answered,
            correct=correct_count,
            duration_seconds=duration,
        )
        save_history(history_path, history)
    print_summary(correct_count, answered, duration)


def print_summary(correct_count, answered, duration_seconds):
    print()
    rule("═")
    print(c("  SESSION SUMMARY", Color.BOLD, Color.CYAN))
    rule("═")
    if answered == 0:
        print(c("  No cards were graded.", Color.YELLOW))
        return
    pct = 100 * correct_count / answered
    print(f"  Score: {c(f'{correct_count}/{answered}', Color.BOLD)}  {bar(pct)}  {pct:.0f}%")
    tier = (
        "Excellent" if pct >= 90 else
        "Solid" if pct >= 75 else
        "Keep practicing" if pct >= 60 else
        "Needs review"
    )
    tier_color = Color.GREEN if pct >= 75 else Color.YELLOW if pct >= 60 else Color.RED
    print(f"  {c(tier, Color.BOLD, tier_color)}")
    minutes, seconds = divmod(int(duration_seconds), 60)
    print(c(f"  Time: {minutes}m {seconds}s", Color.DIM))
    print()


# --------------------------------------------------------------------------
# Stats / list modes (no session — inspect data)
# --------------------------------------------------------------------------

def print_stats(cards, history):
    by_id = {c.id: c for c in cards}
    print_banner()
    sessions = history["sessions"]
    if not sessions:
        print(c("\n  No recorded sessions yet — run a review first.\n", Color.YELLOW))
        return
    total_attempts = sum(e["attempts"] for e in history["cards"].values())
    total_correct = sum(e["correct"] for e in history["cards"].values())
    overall_pct = 100 * total_correct / total_attempts if total_attempts else 0.0
    print()
    print(f"  Sessions logged: {c(str(len(sessions)), Color.BOLD)}")
    print(f"  Total gradings:  {c(str(total_attempts), Color.BOLD)}")
    print(f"  Overall recall:  {bar(overall_pct)}  {overall_pct:.0f}%  ({total_correct}/{total_attempts})")

    by_domain = {}
    for cid, entry in history["cards"].items():
        card = by_id.get(cid)
        if card is None:
            continue
        d = by_domain.setdefault(card.domain, {"attempts": 0, "correct": 0})
        d["attempts"] += entry["attempts"]
        d["correct"] += entry["correct"]
    if by_domain:
        print()
        print(c("  By domain:", Color.BOLD))
        for domain in sorted(by_domain):
            d = by_domain[domain]
            pct = 100 * d["correct"] / d["attempts"] if d["attempts"] else 0.0
            print(f"    Domain {domain}  {bar(pct)}  {pct:5.1f}%  ({d['correct']}/{d['attempts']})")

    missed = [cid for cid, e in history["cards"].items() if e.get("last_result") == "incorrect"]
    print()
    print(c(f"  Currently missed (available to re-drill with --review-missed): {len(missed)}", Color.DIM))
    print()
    print(c("  Recent sessions:", Color.BOLD))
    for s in sessions[-5:]:
        print(f"    {s['timestamp']}  {s['correct']}/{s['total']} ({s['score_pct']}%)  {', '.join(s['source_files'])}")
    print()


def print_list(cards):
    by_domain = {}
    for card in cards:
        by_domain.setdefault(card.domain, {}).setdefault(card.task_statement, 0)
        by_domain[card.domain][card.task_statement] += 1
    print_banner()
    print()
    all_tags = sorted({t for c in cards for t in c.tags})
    for domain in sorted(by_domain):
        print(c(f"  Domain {domain}", Color.BOLD, Color.CYAN))
        for task in sorted(by_domain[domain], key=lambda t: [int(p) for p in t.split(".")]):
            print(f"    {task}: {by_domain[domain][task]} card(s)")
    print()
    print(c(f"  {len(cards)} card(s) total across {len(by_domain)} domain(s).", Color.DIM))
    if all_tags:
        print(c(f"  Tags seen: {', '.join(all_tags)}", Color.DIM))
    print()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

# CLI helpers shared with flashcards_tui.py (logic lives in exam_manifest.py).
def add_exam_arguments(parser):
    em.add_exam_arguments(parser, "flashcards", "flashcard")


def resolve_exam(parser, args):
    global EXAM_CODE
    exam = em.resolve_exam(parser, args, kind=HISTORY_KIND, section="flashcards", records_key="cards", c=c, Color=Color)
    EXAM_CODE = exam["code"]
    return exam


def reset_history(args, exam):
    return em.reset_history(args, exam, kind=HISTORY_KIND, records_key="cards", c=c, Color=Color)


EPILOG = """\
Examples (run from the repo root):
  # Review the default exam's flashcard deck (CCAR-F), cards in file order
  uv run study/tools/flashcards.py

  # Pick the exam / deck explicitly (by label or component id)
  uv run study/tools/flashcards.py --exam ccarf --set standard

  # Shuffle and cap the session at 20 random cards
  uv run study/tools/flashcards.py --shuffle --num 20

  # Drill one domain or one task statement
  uv run study/tools/flashcards.py --domain 1
  uv run study/tools/flashcards.py --task 4.3

  # Re-drill only the cards you graded "missed" last time
  uv run study/tools/flashcards.py --review-missed

  # Reproducible shuffle order
  uv run study/tools/flashcards.py --shuffle --seed 42

  # View cumulative recall stats, or list domains/tasks/tags, without a session
  uv run study/tools/flashcards.py --stats
  uv run study/tools/flashcards.py --list

  # Review explicit files instead, with a separate history file
  uv run study/tools/flashcards.py .working/my-cards.json --history .working/my_history.json

  # Wipe saved progress for the exam's history file (.working/flashcards_history_<exam>.json)
  uv run study/tools/flashcards.py --reset-history

  # Disable color (e.g. piping output to a file)
  uv run study/tools/flashcards.py --no-color

  # Show the script version
  uv run study/tools/flashcards.py --version
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="flashcards.py",
        description="Interactive, offline terminal flashcard runner for exam flashcard "
                    "sets, with per-exam cross-session self-graded recall tracking.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "files", nargs="*", type=Path,
        help="Flashcard-set JSON files (flashcards.schema.json) to use instead of the exam's sets.",
    )
    add_exam_arguments(parser)
    parser.add_argument("--domain", type=int, metavar="N", help="Only include cards from domain N (see --list).")
    parser.add_argument("--task", metavar="X.Y", help="Only include cards from task statement X.Y (e.g. 4.3).")
    parser.add_argument("--tag", metavar="TAG", help="Only include cards with this tag.")
    parser.add_argument("--num", type=int, metavar="N", help="Limit the session to N cards.")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle card order before selecting.")
    parser.add_argument("--seed", type=int, metavar="N", help="Random seed for --shuffle, for reproducible order.")
    parser.add_argument(
        "--review-missed", action="store_true",
        help="Only include cards whose most recent grading was 'missed'.",
    )
    parser.add_argument(
        "--history", type=Path, default=None, metavar="PATH",
        help="Path to the progress-history JSON file (default: .working/flashcards_history_<exam>.json).",
    )
    parser.add_argument("--stats", action="store_true", help="Show cumulative recall stats and exit (no session).")
    parser.add_argument("--list", action="store_true", help="List domains/tasks/tags in the loaded file(s) and exit.")
    parser.add_argument("--reset-history", action="store_true", help="Delete all saved progress in --history and exit.")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip the confirmation prompt for --reset-history.")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors in output.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    Color.enabled = sys.stdout.isatty() and not args.no_color

    exam = resolve_exam(parser, args)
    if args.reset_history:
        return reset_history(args, exam)

    missing = [p for p in args.files if not p.exists()]
    if missing:
        parser.error(f"file(s) not found: {', '.join(str(p) for p in missing)}")

    cards = load_flashcards(args.files, args.item_tasks)
    if not cards:
        raise SystemExit("error: no flashcards loaded from the given file(s)")

    history = load_history(args.history)
    pool = apply_filters(cards, args, history)

    if args.list:
        print_list(pool)
        return 0

    if args.stats:
        print_stats(pool, history)
        return 0

    if not pool:
        print(c("No flashcards match the given filters.", Color.YELLOW))
        return 1

    selected = select_cards(pool, args)
    if not selected:
        print(c("No cards left after applying --num.", Color.YELLOW))
        return 1

    filters = {
        "domain": args.domain, "task": args.task, "tag": args.tag,
        "review_missed": args.review_missed, "num": args.num, "shuffle": args.shuffle,
    }
    try:
        run_session(selected, history, args.history, [p.name for p in args.files], filters)
    except (KeyboardInterrupt, EOFError):
        print(c("\n\nInterrupted — progress so far was not saved for this session.", Color.YELLOW))
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
