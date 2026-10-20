#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""A fixed-layout, full-screen terminal variant of quiz.py.

Same question sets, filters, and progress-history file as quiz.py (both
read/write study/tools/../.working/quiz_history.json by default, so practice
in either UI counts toward the same tracked history) — this variant just
renders differently: it takes over the whole terminal (an "alternate screen",
the same mechanism `less`/`vim` use), redraws from scratch for every state
change, and keeps the current question pinned at the top of the screen. When
you answer, the Correct/Incorrect verdict and rationale appear directly below
the question — above the input line — rather than scrolling past it.

Pure ANSI escape codes, no curses/third-party TUI library, so it stays
dependency-free and works the same on macOS, Linux, and Windows Terminal /
modern PowerShell.
"""

import argparse
import random
import shutil
import sys
import textwrap
from pathlib import Path

# quiz.py lives alongside this script; reuse its data model, filtering, and
# history logic rather than duplicating it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import quiz as core  # noqa: E402

__version__ = "1.1.0"


# --------------------------------------------------------------------------
# Terminal control (alternate screen, cursor, Windows VT enabling)
# --------------------------------------------------------------------------

def _enable_windows_vt():
    """On legacy Windows consoles, ANSI escape codes are ignored unless the
    ENABLE_VIRTUAL_TERMINAL_PROCESSING mode is turned on. Windows Terminal and
    modern PowerShell already default to it; this is a harmless no-op there
    and a real fix on older conhost.exe windows. Never fatal if it fails."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


def enter_alt_screen():
    sys.stdout.write("\033[?1049h\033[?25l")  # alternate screen + hide cursor
    sys.stdout.flush()


def leave_alt_screen():
    sys.stdout.write("\033[?25h\033[?1049l")  # show cursor + primary screen
    sys.stdout.flush()


def clear_and_home():
    sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()


def term_width(default=88, minimum=48, maximum=100):
    width = shutil.get_terminal_size(fallback=(default, 24)).columns
    return max(minimum, min(maximum, width - 2))


def wrap(text, indent="", width=None):
    width = width or term_width()
    return "\n".join(
        textwrap.fill(line, width=width, initial_indent=indent, subsequent_indent=indent)
        for line in text.splitlines()
    ) if text else ""


def label_line(label, text, width=None):
    """A bold "Label: " prefix followed by wrapped text, with continuation
    lines hanging-indented to line up under the text (not the label)."""
    width = width or term_width()
    indent = " " * len(label)
    body = textwrap.fill(text, width=width, initial_indent="", subsequent_indent=indent)
    return core.c(label, core.Color.BOLD) + body


# --------------------------------------------------------------------------
# Frame rendering — the whole screen is rebuilt and reprinted on every
# state change (before answering, after answering, after skip/feedback).
# --------------------------------------------------------------------------

def accuracy_color(pct):
    """Same 90/75/60 breakpoints as print_summary's Excellent/Solid/Keep
    practicing/Needs review tiers, mapped to four colors instead of three."""
    if pct >= 90:
        return core.Color.GREEN
    if pct >= 75:
        return core.Color.YELLOW
    if pct >= 60:
        return core.Color.ORANGE
    return core.Color.RED


def render_frame(index, total, q, display_options, orig_to_display, display_to_orig, answered_state, running_correct, running_answered):
    """answered_state is None (not yet answered), or a dict with
    {"choice": str, "correct": bool, "skipped": bool} describing the result.
    `choice` is in display-letter terms; display_options/orig_to_display/
    display_to_orig describe this question's current on-screen shuffle."""
    lines = []
    lines.append(core.c("  " + f"{core.EXAM_CODE} PRACTICE QUIZ".strip(), core.Color.BOLD, core.Color.CYAN) + core.c("  ·  fixed-layout mode", core.Color.DIM))
    lines.append(core.c("─" * term_width(), core.Color.DIM))

    header = f"Question {index}/{total}"
    tag = f"Domain {q.domain} · Task {q.task_statement}"
    if q.difficulty is not None:
        tag += f" · difficulty {q.difficulty}/10"
    if isinstance(q.correct, list):
        tag += f" · Select {len(q.correct)}"
    lines.append(core.c(header, core.Color.BOLD, core.Color.CYAN) + core.c("   " + tag, core.Color.DIM))
    lines.append("")
    bar_color = accuracy_color(100 * running_correct / running_answered) if running_answered else core.Color.DIM
    lines.append(core.bar(100 * index / total, width=min(40, term_width()), color=bar_color) + core.c(f"  {index}/{total}", core.Color.DIM))
    lines.append("")

    if q.scenario:
        lines.append(core.c(wrap(q.scenario, width=term_width()), core.Color.CYAN))
        lines.append("")

    lines.append(core.c(wrap(q.stem, width=term_width()), core.Color.BOLD))
    lines.append("")
    for opt in display_options:
        prefix = f"  {opt['key']}. "
        body = textwrap.fill(opt["text"], width=term_width(), initial_indent="", subsequent_indent=" " * len(prefix))
        lines.append(f"  {core.c(opt['key'], core.Color.BOLD, core.Color.CYAN)}. {body}")
    lines.append("")

    if running_answered:
        pct = 100 * running_correct / running_answered
        lines.append(core.c(f"Score so far: {running_correct}/{running_answered} ({pct:.0f}%)", core.Color.DIM))
        lines.append("")

    if answered_state is not None:
        lines.append(core.c("─" * term_width(), core.Color.DIM))
        if answered_state["skipped"]:
            lines.append(core.c("Skipped.", core.Color.DIM))
        else:
            choice = answered_state["choice"]
            is_multi = isinstance(q.correct, list)
            correct_orig = set(q.correct) if is_multi else {q.correct}
            chosen_orig = {display_to_orig[k] for k in choice} if is_multi else {display_to_orig[choice]}
            if answered_state["correct"]:
                lines.append(core.c("✓ Correct!", core.Color.BOLD, core.Color.GREEN))
            else:
                correct_display = sorted(orig_to_display[k] for k in correct_orig)
                answer_label = ", ".join(correct_display) if is_multi else correct_display[0]
                verb = "are" if is_multi else "is"
                lines.append(core.c(f"✗ Incorrect — correct answer{'s' if is_multi else ''} {verb} {answer_label}.", core.Color.BOLD, core.Color.RED))
            lines.append("")
            lines.append(label_line("Why: ", q.rationale.get("correct", "")))
            if not answered_state["correct"]:
                wrong_orig = sorted(chosen_orig - correct_orig, key=lambda k: orig_to_display[k])
                for orig_key in wrong_orig:
                    distractor = q.rationale.get("distractors", {}).get(orig_key)
                    if distractor:
                        lines.append(label_line(f"About {orig_to_display[orig_key]}: ", distractor))
                if is_multi:
                    missed_display = sorted(orig_to_display[k] for k in correct_orig - chosen_orig)
                    if missed_display:
                        lines.append(label_line("Missed: ", f"{', '.join(missed_display)} should also have been selected."))
            if q.lab:
                lines.append(core.c(f"Practice: {q.lab}", core.Color.DIM))
        lines.append("")

    clear_and_home()
    print("\n".join(lines))


# --------------------------------------------------------------------------
# Session loop
# --------------------------------------------------------------------------

def prompt_answer(valid_keys, select_count=None):
    """select_count is None for a normal single-answer item, or an int (2+)
    for a multi-response ('Select N') item — in which case this returns a
    list of letters instead of a single letter."""
    label = "Your answer" if select_count is None else f"Your answer (select {select_count})"
    while True:
        raw = input(core.c(label + " ", core.Color.CYAN) + core.c("(or 'skip', 'quit')", core.Color.DIM) + core.c(": ", core.Color.CYAN)).strip()
        low = raw.lower()
        if low in ("q", "quit", "exit"):
            return "quit"
        if low in ("s", "skip"):
            return "skip"
        if select_count is None:
            up = raw.upper()
            if up in valid_keys:
                return up
            print(core.c(f"  Please enter one of {', '.join(valid_keys)}, or 'skip'/'quit'.", core.Color.YELLOW))
            continue
        letters = []
        for ch in raw.upper():
            if ch.isalpha() and ch not in letters:
                letters.append(ch)
        if len(letters) != select_count or any(ch not in valid_keys for ch in letters):
            example = "".join(valid_keys[:select_count])
            print(core.c(f"  Please enter exactly {select_count} of {', '.join(valid_keys)} (e.g. \"{example}\"), or 'skip'/'quit'.", core.Color.YELLOW))
            continue
        return letters


def wait_continue():
    raw = input(core.c("Press Enter for the next question ", core.Color.DIM) + core.c("(or 'quit')", core.Color.DIM) + core.c(": ", core.Color.DIM)).strip().lower()
    return raw not in ("q", "quit", "exit")


def run_tui_session(questions, history, history_path, source_files, filters, rng):
    from datetime import datetime

    _enable_windows_vt()
    enter_alt_screen()
    start = datetime.now()
    correct_count = 0
    answered = 0
    ended_early = False
    try:
        for i, q in enumerate(questions, start=1):
            display_options, orig_to_display, display_to_orig = core.shuffle_options(q, rng)
            valid_keys = [o["key"] for o in display_options]
            select_count = len(q.correct) if isinstance(q.correct, list) else None

            render_frame(i, len(questions), q, display_options, orig_to_display, display_to_orig, None, correct_count, answered)
            choice = prompt_answer(valid_keys, select_count)

            if choice == "quit":
                ended_early = True
                break

            if choice == "skip":
                render_frame(i, len(questions), q, display_options, orig_to_display, display_to_orig, {"skipped": True, "choice": None, "correct": False}, correct_count, answered)
                if not wait_continue():
                    ended_early = True
                    break
                continue

            answered += 1
            is_multi = isinstance(q.correct, list)
            chosen_orig = {display_to_orig[k] for k in choice} if is_multi else display_to_orig[choice]
            is_correct = chosen_orig == set(q.correct) if is_multi else chosen_orig == q.correct
            if is_correct:
                correct_count += 1
            core.record_answer(history, q, is_correct)

            render_frame(
                i, len(questions), q, display_options, orig_to_display, display_to_orig,
                {"skipped": False, "choice": choice, "correct": is_correct},
                correct_count, answered,
            )
            if not wait_continue():
                ended_early = True
                break
    finally:
        leave_alt_screen()

    duration = (datetime.now() - start).total_seconds()
    if answered:
        core.record_session(
            history,
            source_files=source_files,
            filters=filters,
            total=answered,
            correct=correct_count,
            duration_seconds=duration,
        )
        core.save_history(history_path, history)

    if ended_early:
        print(core.c("Session ended early.\n", core.Color.YELLOW))
    core.print_summary(correct_count, answered, duration)


# --------------------------------------------------------------------------
# CLI — mirrors quiz.py's flags so muscle memory transfers between the two.
# --------------------------------------------------------------------------

EPILOG = """\
Examples (run from the repo root):
  # Fixed-layout quiz on the default exam's first question set (CCAR-F Standard)
  uv run study/tools/quiz_tui.py

  # Pick the exam and set(s); sets are matched by label or component id
  uv run study/tools/quiz_tui.py --exam ccarf --set hard
  uv run study/tools/quiz_tui.py --set all --shuffle --num 20

  # Drill just one domain or task statement
  uv run study/tools/quiz_tui.py --domain 1
  uv run study/tools/quiz_tui.py --set all --task 4.3

  # Re-drill only questions you've gotten wrong before (shared history with quiz.py)
  uv run study/tools/quiz_tui.py --set all --review-missed

  # View cumulative stats or list domains/tasks without quizzing
  uv run study/tools/quiz_tui.py --set all --stats
  uv run study/tools/quiz_tui.py --set hard --list

  # Quiz on explicit files instead, with a separate history file
  uv run study/tools/quiz_tui.py .working/my-questions.json --history .working/my_history.json

  # Disable color (feedback/verdict text still appears above the input line)
  uv run study/tools/quiz_tui.py --no-color

  # Show the script version
  uv run study/tools/quiz_tui.py --version
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="quiz_tui.py",
        description="Fixed-layout, full-screen terminal variant of quiz.py: the current "
                    "question stays pinned at the top, and Correct/Incorrect + rationale "
                    "appear above the input line instead of scrolling past it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "files", nargs="*", type=Path,
        help="Question-set JSON files (questions.schema.json) to use instead of the exam's sets.",
    )
    core.add_exam_arguments(parser)
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
        help="Path to the progress-history JSON file (default: .working/quiz_history_<exam>.json, "
             "shared with quiz.py).",
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

    core.Color.enabled = sys.stdout.isatty() and not args.no_color

    exam = core.resolve_exam(parser, args)
    if args.reset_history:
        return core.reset_history(args, exam)

    missing = [p for p in args.files if not p.exists()]
    if missing:
        parser.error(f"file(s) not found: {', '.join(str(p) for p in missing)}")

    questions = core.load_questions(args.files)
    if not questions:
        raise SystemExit("error: no questions loaded from the given file(s)")

    history = core.load_history(args.history)
    pool = core.apply_filters(questions, args, history)

    if args.list:
        core.print_list(pool)
        return 0

    if args.stats:
        core.print_stats(pool, history)
        return 0

    if not pool:
        print(core.c("No questions match the given filters.", core.Color.YELLOW))
        return 1

    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    selected = core.select_questions(pool, args, rng)
    if not selected:
        print(core.c("No questions left after applying --num.", core.Color.YELLOW))
        return 1

    filters = {
        "domain": args.domain, "task": args.task, "tag": args.tag,
        "review_missed": args.review_missed, "num": args.num, "shuffle": args.shuffle,
    }
    try:
        run_tui_session(selected, history, args.history, [p.name for p in args.files], filters, rng)
    except (KeyboardInterrupt, EOFError):
        # run_tui_session's own try/finally has already restored the terminal by this point.
        print(core.c("\n\nInterrupted — progress so far was not saved for this session.", core.Color.YELLOW))
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# EOF
