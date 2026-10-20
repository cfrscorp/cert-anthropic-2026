#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""A colorful, offline terminal quiz runner for exam-style practice question sets.

By default it quizzes on a question set pinned by an exam (--exam, --set), or
reads explicit JSON files matching study/schema/questions.schema.json
(scenario, stem, four options, correct key, rationale, difficulty, tags; pool
items get their domain/task from the exam's map.json, while a personal file may
carry its own domain + task_statement), runs an interactive multiple-choice session in the
terminal, and tracks personal correct/incorrect results across sessions in a
small local JSON history file so you can see progress over time and re-drill
whatever you've missed.
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

# exam_manifest.py lives alongside this script (shared with flashcards.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import exam_manifest as em  # noqa: E402

HISTORY_KIND = "quiz"  # -> .working/quiz_history_<exam>.json (em.history_path)
HISTORY_SCHEMA_VERSION = em.HISTORY_VERSION  # 2: records keyed by pool IDs (BL-050)
EXAM_CODE = ""  # set by resolve_exam(); shown in the banner


# --------------------------------------------------------------------------
# Color
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

    # True orange isn't in the standard 16-color set; this is the 256-color
    # (xterm-256color) equivalent, near-universally supported in 2026.
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
    to override the default green/yellow/red-by-pct coloring — e.g. to color
    the bar by a different percentage than the one it's filled to."""
    filled = round(width * max(0.0, min(100.0, pct)) / 100)
    color = color or (Color.GREEN if pct >= 80 else Color.YELLOW if pct >= 60 else Color.RED)
    return c("█" * filled, color) + c("░" * (width - filled), Color.DIM)


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

@dataclass
class Question:
    id: str
    domain: int
    task_statement: str
    stem: str
    options: list
    correct: str
    rationale: dict
    source: str
    scenario: Optional[str] = None
    lab: Optional[str] = None
    difficulty: Optional[int] = None
    tags: list = field(default_factory=list)


def load_questions(paths, item_tasks=None):
    """Load and merge one or more questions.json-schema files, tagging each
    question with the basename of the file it came from. Pool items take their
    domain/task from the exam's map (`item_tasks`, from em.item_tasks); ones the
    map doesn't list aren't part of the exam and are skipped."""
    questions = []
    seen_ids = {}
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SystemExit(f"error: could not read {path}: {exc}")
        if not isinstance(raw, list):
            raise SystemExit(f"error: {path} does not contain a JSON array of questions")
        for item in raw:
            try:
                tags = em.exam_tags(item, item_tasks)
                if tags is None:
                    continue
                q = Question(
                    id=item["id"],
                    domain=tags[0],
                    task_statement=tags[1],
                    stem=item["stem"],
                    options=item["options"],
                    correct=item["correct"],
                    rationale=item["rationale"],
                    source=path.name,
                    scenario=item.get("scenario"),
                    lab=item.get("lab"),
                    difficulty=item.get("difficulty"),
                    tags=item.get("tags") or [],
                )
            except KeyError as exc:
                raise SystemExit(f"error: {path} has a question missing required field {exc}")
            if q.id in seen_ids:
                print(
                    c(f"warning: duplicate question id {q.id!r} in {path.name} "
                      f"(already loaded from {seen_ids[q.id]}); keeping the first one", Color.YELLOW),
                    file=sys.stderr,
                )
                continue
            seen_ids[q.id] = path.name
            questions.append(q)
    return questions


# --------------------------------------------------------------------------
# History (cumulative, cross-session progress tracking)
# --------------------------------------------------------------------------

def load_history(path):
    if not path.exists():
        return {"version": HISTORY_SCHEMA_VERSION, "questions": {}, "sessions": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print(c(f"warning: {path} is not valid JSON; starting a fresh history", Color.YELLOW), file=sys.stderr)
        return {"version": HISTORY_SCHEMA_VERSION, "questions": {}, "sessions": []}
    data.setdefault("version", HISTORY_SCHEMA_VERSION)
    data.setdefault("questions", {})
    data.setdefault("sessions", [])
    return data


def save_history(path, history):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")


def record_answer(history, question, correct):
    entry = history["questions"].setdefault(
        question.id, {"attempts": 0, "correct": 0, "last_result": None, "last_seen": None, "source": question.source}
    )
    entry["attempts"] += 1
    entry["correct"] += 1 if correct else 0
    entry["last_result"] = "correct" if correct else "incorrect"
    entry["last_seen"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry["source"] = question.source


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

def apply_filters(questions, args, history):
    pool = questions
    if args.domain is not None:
        pool = [q for q in pool if q.domain == args.domain]
    if args.task is not None:
        pool = [q for q in pool if q.task_statement == args.task]
    if args.tag is not None:
        pool = [q for q in pool if args.tag in q.tags]
    if args.review_missed:
        missed_ids = {
            qid for qid, entry in history["questions"].items()
            if entry.get("last_result") == "incorrect"
        }
        pool = [q for q in pool if q.id in missed_ids]
    return pool


def select_questions(pool, args, rng):
    pool = list(pool)
    if args.shuffle:
        rng.shuffle(pool)
    if args.num is not None:
        pool = pool[: args.num]
    return pool


def shuffle_options(q, rng):
    """Return a per-presentation shuffle of a question's options: real exam
    items don't always put the correct answer in the same position, so this
    randomizes on-screen order and reassigns sequential display letters
    (A, B, C, ...), independent of the underlying `q.correct` / `q.rationale`
    keys (which stay exactly as authored). Returns (display_options,
    orig_to_display, display_to_orig); the two dicts translate between the
    letters shown to the user this time and the letters the data model uses,
    so grading and rationale lookups stay correct regardless of shuffle."""
    perm = list(q.options)
    rng.shuffle(perm)
    letters = [o["key"] for o in q.options][: len(perm)]  # reuse A, B, C... in order
    display_options = [{"key": letters[i], "text": perm[i]["text"]} for i in range(len(perm))]
    orig_to_display = {perm[i]["key"]: letters[i] for i in range(len(perm))}
    display_to_orig = {letters[i]: perm[i]["key"] for i in range(len(perm))}
    return display_options, orig_to_display, display_to_orig


# --------------------------------------------------------------------------
# Interactive quiz session
# --------------------------------------------------------------------------

def print_banner():
    rule("═")
    print(c("  " + f"{EXAM_CODE} PRACTICE QUIZ".strip(), Color.BOLD, Color.CYAN))
    rule("═")


def print_question(index, total, q, display_options):
    print()
    header = f"Question {index}/{total}"
    tag = f"Domain {q.domain} · Task {q.task_statement}"
    if q.difficulty is not None:
        tag += f" · difficulty {q.difficulty}/10"
    if isinstance(q.correct, list):
        tag += f" · Select {len(q.correct)}"
    print(c(header, Color.BOLD, Color.CYAN) + c("   " + tag, Color.DIM))
    rule()
    if q.scenario:
        print(c(q.scenario, Color.BLUE))
        print()
    print(c(q.stem, Color.BOLD))
    print()
    for opt in display_options:
        print(f"  {c(opt['key'], Color.BOLD, Color.CYAN)}. {opt['text']}")
    print()


def prompt_answer(valid_keys, select_count=None):
    """select_count is None for a normal single-answer item, or an int (2+)
    for a multi-response ('Select N') item — in which case this returns a
    list of letters instead of a single letter."""
    label = "Your answer" if select_count is None else f"Your answer (select {select_count})"
    while True:
        raw = input(c(label + " ", Color.CYAN) + c("(or 'skip', 'quit')", Color.DIM) + c(": ", Color.CYAN)).strip()
        low = raw.lower()
        if low in ("q", "quit", "exit"):
            return "quit"
        if low in ("s", "skip"):
            return "skip"
        if select_count is None:
            up = raw.upper()
            if up in valid_keys:
                return up
            print(c(f"  Please enter one of {', '.join(valid_keys)}, or 'skip'/'quit'.", Color.YELLOW))
            continue
        # Accept letters in any of "AC", "A,C", "A C" and de-dupe while preserving order.
        letters = []
        for ch in raw.upper():
            if ch.isalpha() and ch not in letters:
                letters.append(ch)
        if len(letters) != select_count or any(ch not in valid_keys for ch in letters):
            example = "".join(valid_keys[:select_count])
            print(c(f"  Please enter exactly {select_count} of {', '.join(valid_keys)} (e.g. \"{example}\"), or 'skip'/'quit'.", Color.YELLOW))
            continue
        return letters


def show_feedback(q, chosen, orig_to_display, display_to_orig):
    """`chosen` is in display-letter terms (what the user typed, matching what
    was on screen); comparisons against q.correct/q.rationale translate
    through display_to_orig, and anything shown back to the user is
    translated through orig_to_display so it stays consistent with the
    letters they just saw, regardless of how this question's options were
    shuffled for presentation."""
    is_multi = isinstance(q.correct, list)
    correct_orig = set(q.correct) if is_multi else {q.correct}
    chosen_orig = {display_to_orig[k] for k in chosen} if is_multi else {display_to_orig[chosen]}
    correct = chosen_orig == correct_orig
    if correct:
        print(c("  ✓ Correct!", Color.BOLD, Color.GREEN))
    else:
        correct_display = sorted(orig_to_display[k] for k in correct_orig)
        answer_label = ", ".join(correct_display) if is_multi else correct_display[0]
        verb = "are" if is_multi else "is"
        print(c(f"  ✗ Incorrect — correct answer{'s' if is_multi else ''} {verb} {answer_label}.", Color.BOLD, Color.RED))
    print()
    print(c("  Why: ", Color.BOLD) + q.rationale.get("correct", ""))
    if not correct:
        wrong_orig = sorted(chosen_orig - correct_orig, key=lambda k: orig_to_display[k])
        for orig_key in wrong_orig:
            distractor = q.rationale.get("distractors", {}).get(orig_key)
            if distractor:
                print(c(f"  About {orig_to_display[orig_key]}: ", Color.BOLD) + distractor)
        if is_multi:
            missed_display = sorted(orig_to_display[k] for k in correct_orig - chosen_orig)
            if missed_display:
                print(c("  Missed: ", Color.BOLD) + f"{', '.join(missed_display)} should also have been selected.")
    if q.lab:
        print(c(f"  Practice: {q.lab}", Color.DIM))
    return correct


def run_session(questions, history, history_path, source_files, filters, rng):
    print_banner()
    print(c(f"  {len(questions)} question(s) loaded — answer A-D, or 'skip' / 'quit' anytime.\n", Color.DIM))
    start = datetime.now()
    correct_count = 0
    answered = 0
    for i, q in enumerate(questions, start=1):
        display_options, orig_to_display, display_to_orig = shuffle_options(q, rng)
        print_question(i, len(questions), q, display_options)
        valid_keys = [o["key"] for o in display_options]
        select_count = len(q.correct) if isinstance(q.correct, list) else None
        choice = prompt_answer(valid_keys, select_count)
        if choice == "quit":
            print(c("\nEnding session early.", Color.YELLOW))
            break
        if choice == "skip":
            print(c("  Skipped.", Color.DIM))
            continue
        answered += 1
        is_correct = show_feedback(q, choice, orig_to_display, display_to_orig)
        if is_correct:
            correct_count += 1
        record_answer(history, q, is_correct)
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
        print(c("  No questions were answered.", Color.YELLOW))
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
# Stats / list modes (no quiz — inspect data)
# --------------------------------------------------------------------------

def print_stats(questions, history):
    by_id = {q.id: q for q in questions}
    print_banner()
    sessions = history["sessions"]
    if not sessions:
        print(c("\n  No recorded sessions yet — run a quiz first.\n", Color.YELLOW))
        return
    total_attempts = sum(e["attempts"] for e in history["questions"].values())
    total_correct = sum(e["correct"] for e in history["questions"].values())
    overall_pct = 100 * total_correct / total_attempts if total_attempts else 0.0
    print()
    print(f"  Sessions logged: {c(str(len(sessions)), Color.BOLD)}")
    print(f"  Total answers:   {c(str(total_attempts), Color.BOLD)}")
    print(f"  Overall accuracy: {bar(overall_pct)}  {overall_pct:.0f}%  ({total_correct}/{total_attempts})")

    by_domain = {}
    for qid, entry in history["questions"].items():
        q = by_id.get(qid)
        if q is None:
            continue
        d = by_domain.setdefault(q.domain, {"attempts": 0, "correct": 0})
        d["attempts"] += entry["attempts"]
        d["correct"] += entry["correct"]
    if by_domain:
        print()
        print(c("  By domain:", Color.BOLD))
        for domain in sorted(by_domain):
            d = by_domain[domain]
            pct = 100 * d["correct"] / d["attempts"] if d["attempts"] else 0.0
            print(f"    Domain {domain}  {bar(pct)}  {pct:5.1f}%  ({d['correct']}/{d['attempts']})")

    missed = [qid for qid, e in history["questions"].items() if e.get("last_result") == "incorrect"]
    print()
    print(c(f"  Currently missed (available to re-drill with --review-missed): {len(missed)}", Color.DIM))
    print()
    print(c("  Recent sessions:", Color.BOLD))
    for s in sessions[-5:]:
        print(f"    {s['timestamp']}  {s['correct']}/{s['total']} ({s['score_pct']}%)  {', '.join(s['source_files'])}")
    print()


def print_list(questions):
    by_domain = {}
    for q in questions:
        by_domain.setdefault(q.domain, {}).setdefault(q.task_statement, 0)
        by_domain[q.domain][q.task_statement] += 1
    print_banner()
    print()
    all_tags = sorted({t for q in questions for t in q.tags})
    for domain in sorted(by_domain):
        print(c(f"  Domain {domain}", Color.BOLD, Color.CYAN))
        for task in sorted(by_domain[domain], key=lambda t: [int(p) for p in t.split(".")]):
            print(f"    {task}: {by_domain[domain][task]} question(s)")
    print()
    print(c(f"  {len(questions)} question(s) total across {len(by_domain)} domain(s).", Color.DIM))
    if all_tags:
        print(c(f"  Tags seen: {', '.join(all_tags)}", Color.DIM))
    print()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

# CLI helpers shared with quiz_tui.py (logic lives in exam_manifest.py).
def add_exam_arguments(parser):
    em.add_exam_arguments(parser, "questions", "question")


def resolve_exam(parser, args):
    global EXAM_CODE
    exam = em.resolve_exam(parser, args, kind=HISTORY_KIND, section="questions", records_key="questions", c=c, Color=Color)
    EXAM_CODE = exam["code"]
    return exam


def reset_history(args, exam):
    return em.reset_history(args, exam, kind=HISTORY_KIND, records_key="questions", c=c, Color=Color)


EPILOG = """\
Examples (run from the repo root):
  # Quiz on the default exam's first question set (CCAR-F Standard)
  uv run study/tools/quiz.py

  # Pick the exam and set(s) explicitly; sets are matched by label or component id
  uv run study/tools/quiz.py --exam ccarf --set hard
  uv run study/tools/quiz.py --set standard --set intermediate
  uv run study/tools/quiz.py --set all --shuffle --num 30

  # Shuffle and cap the session at 20 random questions
  uv run study/tools/quiz.py --shuffle --num 20

  # Drill just one domain (Agentic Architecture & Orchestration)
  uv run study/tools/quiz.py --domain 1

  # Drill one task statement, or filter by tag
  uv run study/tools/quiz.py --set all --task 4.3
  uv run study/tools/quiz.py --tag hooks

  # Quiz on explicit files instead, e.g. a component plus your own question set
  uv run study/tools/quiz.py study/content/questions-standard.json .working/my-questions.json --shuffle

  # Re-drill only the questions you've gotten wrong before
  uv run study/tools/quiz.py --set all --review-missed

  # Reproducible shuffle order (useful for comparing runs)
  uv run study/tools/quiz.py --shuffle --seed 42

  # View cumulative stats, or see what's in a set (domains/tasks/tags), without quizzing
  uv run study/tools/quiz.py --set all --stats
  uv run study/tools/quiz.py --set hard --list

  # Use a separate history file, e.g. to keep a personal bank's progress apart
  uv run study/tools/quiz.py .working/my-questions.json --history .working/my-questions_history.json

  # Wipe saved progress for the exam's history file (.working/quiz_history_<exam>.json)
  uv run study/tools/quiz.py --reset-history

  # Disable color (e.g. piping output to a file)
  uv run study/tools/quiz.py --no-color

  # Show the script version
  uv run study/tools/quiz.py --version
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="quiz.py",
        description="Interactive, offline terminal quiz runner for exam-style practice "
                    "question sets, with per-exam cross-session progress tracking.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "files", nargs="*", type=Path,
        help="Question-set JSON files (questions.schema.json) to use instead of the exam's sets.",
    )
    add_exam_arguments(parser)
    parser.add_argument("--domain", type=int, metavar="N", help="Only include questions from domain N (see --list).")
    parser.add_argument("--task", metavar="X.Y", help="Only include questions from task statement X.Y (e.g. 4.3).")
    parser.add_argument("--tag", metavar="TAG", help="Only include questions with this tag.")
    parser.add_argument("--num", type=int, metavar="N", help="Limit the session to N questions.")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle question order before selecting.")
    parser.add_argument(
        "--seed", type=int, metavar="N",
        help="Random seed for reproducible randomness (--shuffle's question order, and each "
             "question's on-screen answer order, which is always shuffled).",
    )
    parser.add_argument(
        "--review-missed", action="store_true",
        help="Only include questions whose most recent recorded attempt was incorrect.",
    )
    parser.add_argument(
        "--history", type=Path, default=None, metavar="PATH",
        help="Path to the progress-history JSON file (default: .working/quiz_history_<exam>.json).",
    )
    parser.add_argument("--stats", action="store_true", help="Show cumulative stats and exit (no quiz).")
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

    questions = load_questions(args.files, args.item_tasks)
    if not questions:
        raise SystemExit("error: no questions loaded from the given file(s)")

    history = load_history(args.history)
    pool = apply_filters(questions, args, history)

    if args.list:
        print_list(pool)
        return 0

    if args.stats:
        print_stats(pool, history)
        return 0

    if not pool:
        print(c("No questions match the given filters.", Color.YELLOW))
        return 1

    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    selected = select_questions(pool, args, rng)
    if not selected:
        print(c("No questions left after applying --num.", Color.YELLOW))
        return 1

    filters = {
        "domain": args.domain, "task": args.task, "tag": args.tag,
        "review_missed": args.review_missed, "num": args.num, "shuffle": args.shuffle,
    }
    try:
        run_session(selected, history, args.history, [p.name for p in args.files], filters, rng)
    except (KeyboardInterrupt, EOFError):
        print(c("\n\nInterrupted — progress so far was not saved for this session.", Color.YELLOW))
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
