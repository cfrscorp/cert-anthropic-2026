# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# CCAF exam-prep repository

Study materials for the **Claude Certified Architect – Foundations (CCAF)** exam.

## Layout

- `anthropic-ccaf-exam-guide-2026-07.md` — the exam guide (5 domains, 30 task statements 1.1–5.6, 6 scenarios S1–S6). **Source of truth for all content.** (`-2026-06.md` is the superseded prior edition.)
- `labs/` — 25 hands-on labs + a shared offline test harness (`labs/_shared/`). See `labs/README.md`.
- `study/` — a local, offline, single-user study app (practice quiz, flashcards, concept explainers, browsable labs, readiness dashboard) plus CLI/TUI tools. See `study/README.md`.
- `BACKLOG.md` — the running task backlog (see below).
- `.working/` — gitignored scratch (reference PDFs, CLI/TUI quiz history). Not content.

## Commands

Everything runs through `uv`; `labs/` and `study/` are **separate uv projects** — run pytest from inside each.

```bash
# Study content + app integrity
cd study && uv run pytest
cd study && uv run pytest tests/test_study_data.py::test_every_distractor_has_a_rationale

# Labs (default target = starter/, i.e. learner work — unfinished starters fail by design)
cd labs && LAB_TARGET=solution uv run pytest                      # reference solutions, must be all green
cd labs && LAB_TARGET=solution uv run pytest lab-03-agentic-loop  # one lab
ANTHROPIC_API_KEY=... uv run pytest -m llm                        # opt-in semantic checks

# Run the app / tools
uv run study/serve.py [--port 8123] [--no-browser]               # opens /web/
uv run study/tools/build_labs.py                                  # regenerate study/data/labs.json
uv run study/tools/quiz.py study/data/questions-hard.json --shuffle --num 20
```

## Architecture

### Study app (`study/`)
- **Data → UI:** `study/data/*.json` is validated against `study/data/schema/*.schema.json` and is the only thing the Web UI (`web/app.js`, vanilla JS, no build step) and the CLI/TUI tools read. `serve.py` exists only because browsers block `fetch()` over `file://`.
- **`sets.json` is a manifest** of question/flashcard sets driving the Web UI dropdowns. Adding/removing a `questions-*.json` or flashcard file requires updating it (a test enforces manifest ↔ disk sync).
- **Question tiers** (`questions-standard/intermediate/hard.json`) are schema-identical. `correct` is a single letter, or a 2+-letter array for "Select N" multi-response items. Every distractor needs a rationale. Answer options are shuffled **at display time** in all three interfaces (web, CLI, TUI) — authored keys stay as written in the data; don't reorder options to "balance" them.
- **`labs.json` is generated**, not hand-edited: `build_labs.py` renders each lab's `README.md`/`SOLUTION.md` to HTML at build time (so the browser needs no Markdown parser). Re-run it whenever lab Markdown changes; tests check it covers every `labs/lab-*` dir.
- **CLI/TUI pairs:** `quiz_tui.py` imports `quiz.py` as `core` (likewise `flashcards_tui.py` → `flashcards.py`). Logic lives in the core module; TUI files only add rendering. History is written to `.working/`.
- **Version lockstep:** `meta.json` `config.app_version` is the single source of truth and must equal `study/pyproject.toml` `version` and `serve.py` `__version__` (tested). Bump all three together.
- Coverage targets come from `meta.json` `config` (e.g. `questions_per_task_target`, applied to the Standard tier); each tier needs ≥ 50 questions.

### Labs (`labs/`)
- Each `lab-NN-slug/` has `starter/` and `solution/` exposing **the same module names and public API**; one `tests/test_labNN.py` runs against either, selected by `LAB_TARGET`.
- Tests import the module under test via `labkit.lab_module(__file__, "name")` — never a plain import. `labkit` evicts same-named sibling modules cached from other labs (multiple labs reuse bare module names like `agent_loop`); bypassing it causes cross-lab `sys.modules` collisions.
- `labs/conftest.py` puts `_shared/` on `sys.path`, auto-skips `llm` tests without a key; `pyproject.toml` excludes `-m llm` by default.
- Claude is mocked with `_shared/mock_anthropic.MockAnthropic` (scripted `responses=[...]` or a `router`, plus batch support; `client.calls` records requests). Learner code must take a `client` parameter (dependency injection), never construct `anthropic.Anthropic()` internally.
- Don't edit `_shared/` from within a lab. Full contract: `labs/_shared/README.md`.

## BACKLOG.md — consult and keep it current

`BACKLOG.md` tracks outstanding and completed work. Read it before starting feature work, and update it as items change.

- **IDs** are global and unique: `BL-NNN` (e.g. `BL-001`).
- Two top-level sections: **Open** and **Completed**. Open is split into **Fixes → Changes → Additions**.
- Default resolution order is per-section, top-down (Fixes first, then Changes, then Additions) — a guideline, not a rule; items may be done out of order.
- When an item is resolved (done, descoped, or tabled), move it from Open to **Completed** with a note on how it was resolved.

## Working conventions

- **Study content is schema-validated JSON** under `study/data/` — the single source of truth the web app reads. Any content/schema change must keep `cd study && uv run pytest` green (schema + integrity + per-task coverage).
- **The study web app (`study/web/`) has zero runtime dependencies** and must stay fully offline (no external requests). Fonts are self-hosted via `study/tools/fetch_fonts.py`. Preserve this when adding features.
- **Labs tests** are deterministic and offline: `cd labs && uv run pytest` (reference solutions: `LAB_TARGET=solution uv run pytest`). See `labs/_shared/README.md`.
- **Runnable Python scripts** follow the user's conventions: PEP 723 inline metadata (`uv run`-able), `argparse` `-h/--help` with an Examples epilog, module-level `__version__` + `--version`. Config-only lab artifacts are exempt.
- **Ground exam content in the guide**, mirroring its sample-question style (correct answer + why each distractor is wrong).
- **Content counts are hardcoded in docs** (`README.md` "By the Numbers" + tier counts, `study/README.md`, test-pass counts). When adding/removing questions, flashcards, concepts, or code samples, update those numbers.
- `study/videos/` holds curated third-party video links per domain — Markdown only, not app data, not schema-validated.
