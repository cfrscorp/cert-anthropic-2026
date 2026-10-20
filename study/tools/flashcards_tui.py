#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""A fixed-layout, full-screen terminal variant of flashcards.py.

Same flashcard sets, filters, and progress-history file as flashcards.py
(both read/write study/tools/../.working/flashcards_history.json by default,
so practice in either UI counts toward the same tracked history) — this
variant just renders differently: it takes over the whole terminal (an
"alternate screen", the same mechanism `less`/`vim` use), redraws from
scratch for every state change, and keeps the current card pinned at the top
of the screen. Revealing the answer and grading yourself both appear
directly below the card — above the input line — rather than scrolling
past it.

Pure ANSI escape codes, no curses/third-party TUI library, so it stays
dependency-free and works the same on macOS, Linux, and Windows Terminal /
modern PowerShell. Mirrors quiz_tui.py's architecture exactly, adapted for
front/back self-grading instead of multiple-choice grading.
"""

import argparse
import shutil
import sys
import textwrap
from pathlib import Path

# flashcards.py lives alongside this script; reuse its data model, filtering,
# history logic, and ANSI color helpers rather than duplicating them.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flashcards as core  # noqa: E402

__version__ = "1.2.0"


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


# --------------------------------------------------------------------------
# Frame rendering — the whole screen is rebuilt and reprinted on every
# state change (front only, after reveal, after grading, after skip).
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


def render_frame(index, total, card, state, running_correct, running_seen):
    """state is None (front only), or a dict with
    {"skipped": bool, "revealed": bool, "graded": bool|None}."""
    lines = []
    lines.append(core.c("  " + f"{core.EXAM_CODE} FLASHCARDS".strip(), core.Color.BOLD, core.Color.CYAN) + core.c("  ·  fixed-layout mode", core.Color.DIM))
    lines.append(core.c("─" * term_width(), core.Color.DIM))

    header = f"Card {index}/{total}"
    tag = f"Domain {card.domain} · Task {card.task_statement}"
    lines.append(core.c(header, core.Color.BOLD, core.Color.CYAN) + core.c("   " + tag, core.Color.DIM))
    lines.append("")
    bar_color = accuracy_color(100 * running_correct / running_seen) if running_seen else core.Color.DIM
    lines.append(core.bar(100 * index / total, width=min(40, term_width()), color=bar_color) + core.c(f"  {index}/{total}", core.Color.DIM))
    lines.append("")

    lines.append(core.c(wrap(card.front, width=term_width()), core.Color.BOLD))
    lines.append("")

    if running_seen:
        pct = 100 * running_correct / running_seen
        lines.append(core.c(f"Score so far: {running_correct}/{running_seen} ({pct:.0f}%)", core.Color.DIM))
        lines.append("")

    if state is not None:
        lines.append(core.c("─" * term_width(), core.Color.DIM))
        if state["skipped"]:
            lines.append(core.c("Skipped.", core.Color.DIM))
        elif state["revealed"]:
            lines.append(core.c("Answer: ", core.Color.BOLD) + wrap(card.back, width=term_width()))
            if state["graded"] is True:
                lines.append("")
                lines.append(core.c("✓ Marked as got it.", core.Color.BOLD, core.Color.GREEN))
            elif state["graded"] is False:
                lines.append("")
                lines.append(core.c("✗ Marked as missed.", core.Color.BOLD, core.Color.RED))
        lines.append("")

    clear_and_home()
    print("\n".join(lines))


# --------------------------------------------------------------------------
# Session loop
# --------------------------------------------------------------------------

def prompt_reveal():
    raw = input(core.c("Press Enter to reveal ", core.Color.CYAN) + core.c("(or 'skip', 'quit')", core.Color.DIM) + core.c(": ", core.Color.CYAN)).strip().lower()
    if raw in ("q", "quit", "exit"):
        return "quit"
    if raw in ("s", "skip"):
        return "skip"
    return "reveal"


def prompt_grade():
    while True:
        raw = input(core.c("Got it? ", core.Color.CYAN) + core.c("(y/n, or 'quit')", core.Color.DIM) + core.c(": ", core.Color.CYAN)).strip().lower()
        if raw in ("q", "quit", "exit"):
            return "quit"
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print(core.c("  Please enter 'y', 'n', or 'quit'.", core.Color.YELLOW))


def wait_continue():
    raw = input(core.c("Press Enter for the next card ", core.Color.DIM) + core.c("(or 'quit')", core.Color.DIM) + core.c(": ", core.Color.DIM)).strip().lower()
    return raw not in ("q", "quit", "exit")


def run_tui_session(cards, history, history_path, source_files, filters):
    from datetime import datetime

    _enable_windows_vt()
    enter_alt_screen()
    start = datetime.now()
    correct_count = 0
    answered = 0
    ended_early = False
    try:
        for i, card in enumerate(cards, start=1):
            render_frame(i, len(cards), card, None, correct_count, answered)
            choice = prompt_reveal()

            if choice == "quit":
                ended_early = True
                break

            if choice == "skip":
                render_frame(i, len(cards), card, {"skipped": True, "revealed": False, "graded": None}, correct_count, answered)
                if not wait_continue():
                    ended_early = True
                    break
                continue

            render_frame(i, len(cards), card, {"skipped": False, "revealed": True, "graded": None}, correct_count, answered)
            grade = prompt_grade()
            if grade == "quit":
                ended_early = True
                break

            answered += 1
            if grade:
                correct_count += 1
            core.record_answer(history, card, grade)

            render_frame(i, len(cards), card, {"skipped": False, "revealed": True, "graded": grade}, correct_count, answered)
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
# CLI — mirrors flashcards.py's flags so muscle memory transfers between them.
# --------------------------------------------------------------------------

EPILOG = """\
Examples (run from the repo root):
  # Fixed-layout review of the default exam's flashcard deck (CCAR-F)
  uv run study/tools/flashcards_tui.py

  # Pick the exam / deck explicitly (by label or component id)
  uv run study/tools/flashcards_tui.py --exam ccarf --set standard

  # Shuffle and cap the session at 20 random cards
  uv run study/tools/flashcards_tui.py --shuffle --num 20

  # Drill one domain or one task statement
  uv run study/tools/flashcards_tui.py --domain 1
  uv run study/tools/flashcards_tui.py --task 4.3

  # Re-drill only cards you graded "missed" (shared history with flashcards.py)
  uv run study/tools/flashcards_tui.py --review-missed

  # View cumulative stats or list domains/tasks without a session
  uv run study/tools/flashcards_tui.py --stats
  uv run study/tools/flashcards_tui.py --list

  # Review explicit files instead, with a separate history file
  uv run study/tools/flashcards_tui.py .working/my-cards.json --history .working/my_history.json

  # Disable color
  uv run study/tools/flashcards_tui.py --no-color

  # Show the script version
  uv run study/tools/flashcards_tui.py --version
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="flashcards_tui.py",
        description="Fixed-layout, full-screen terminal variant of flashcards.py: the current "
                    "card stays pinned at the top, and the answer + self-grade appear above the "
                    "input line instead of scrolling past it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "files", nargs="*", type=Path,
        help="Flashcard-set JSON files (flashcards.schema.json) to use instead of the exam's sets.",
    )
    core.add_exam_arguments(parser)
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
        help="Path to the progress-history JSON file (default: .working/flashcards_history_<exam>.json, "
             "shared with flashcards.py).",
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

    core.Color.enabled = sys.stdout.isatty() and not args.no_color

    exam = core.resolve_exam(parser, args)
    if args.reset_history:
        return core.reset_history(args, exam)

    missing = [p for p in args.files if not p.exists()]
    if missing:
        parser.error(f"file(s) not found: {', '.join(str(p) for p in missing)}")

    cards = core.load_flashcards(args.files, args.item_tasks)
    if not cards:
        raise SystemExit("error: no flashcards loaded from the given file(s)")

    history = core.load_history(args.history)
    pool = core.apply_filters(cards, args, history)

    if args.list:
        core.print_list(pool)
        return 0

    if args.stats:
        core.print_stats(pool, history)
        return 0

    if not pool:
        print(core.c("No flashcards match the given filters.", core.Color.YELLOW))
        return 1

    selected = core.select_cards(pool, args)
    if not selected:
        print(core.c("No cards left after applying --num.", core.Color.YELLOW))
        return 1

    filters = {
        "domain": args.domain, "task": args.task, "tag": args.tag,
        "review_missed": args.review_missed, "num": args.num, "shuffle": args.shuffle,
    }
    try:
        run_tui_session(selected, history, args.history, [p.name for p in args.files], filters)
    except (KeyboardInterrupt, EOFError):
        # run_tui_session's own try/finally has already restored the terminal by this point.
        print(core.c("\n\nInterrupted — progress so far was not saved for this session.", core.Color.YELLOW))
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
