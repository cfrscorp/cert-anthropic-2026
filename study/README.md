# Claude Certification Study App

A **local, offline, single-user**, **multi-exam** study app for Claude certification
exams. It currently covers the **Claude Certified Architect – Foundations (CCAR-F)**
exam (the **Claude Certified Developer – Foundations (CCDV-F)** exam is planned —
see `BACKLOG.md`): a **3-tier practice-question bank** (435 questions —
Standard/Intermediate/Hard, including real multi-response "Select N" items),
**flashcards** (135 cards, with self-graded recall tracking), **concept
explainers**, and a **readiness dashboard** that tracks your progress over time.
Switch exams from the header (each exam keeps its own progress); links name the
exam and section, e.g. `#/ccarf/quiz`, so bookmarks stay on the right exam.
No cloud, no accounts, no backend — everything runs on your machine and your
progress lives in your browser (or in a local history file for the CLI/TUI tools).

The content is plain, schema-validated **JSON**: reusable, versioned content
*components* (`content/`) that each *exam* (`exams/<slug>/exam.json`) pins per
section; the Web UI (`web/`, dependency-free HTML/CSS/JS) and the CLI/TUI tools
(`tools/`) both read it.

## Install uv

Everything here runs through [uv](https://docs.astral.sh/uv/) — see the
[install guide](https://docs.astral.sh/uv/getting-started/installation/) for all options:

- **macOS** — `curl -LsSf https://astral.sh/uv/install.sh | sh`  (or `brew install uv`)
- **Windows** — in PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

## Run It

```bash
# From the repo root — uses uv; no extra downloads (serve.py is stdlib-only):
uv run study/serve.py
```

This starts a local server and opens `http://localhost:8000/web/`. Options:

```bash
uv run study/serve.py --port 8123      # pick a port
uv run study/serve.py --no-browser     # don't auto-open
uv run study/serve.py --help
```

**Prefer a downloaded binary?** The app is just static files, so any static server
works — point it at this `study/` directory and open `/web/`:

```bash
caddy file-server --root . --listen :8000
static-web-server -d . -p 8000
miniserve . -p 8000
```

> Why a server at all? Browsers block `fetch()` of local files opened via `file://`.
> Serving over `http://localhost` fixes that and keeps the JSON as editable files.

### Share on Your LAN (LAN-only)

By default the server binds to `127.0.0.1` (this machine only). To share the app with
other devices **on your local network** while keeping it **off the public internet**,
start it bound to all local interfaces on a fixed port:

```bash
uv run study/serve.py --host 0.0.0.0 --port 8000
```

**Why this stays LAN-only:** home/office routers don't forward inbound connections from
the internet by default, so this only exposes the server to devices on the same network.
Keep it that way with two rules: **(1)** never add a port-forwarding / NAT rule on your
router (and don't use a tunnel like ngrok/Cloudflare Tunnel), and **(2)** scope your OS
firewall to your *private* network (steps below). Only use this on a trusted network
(home/office) — never on public Wi‑Fi (cafés, airports, hotels, conferences).

### Local Access

On the host machine itself, use `http://localhost:8000/web/`. Other devices use
`http://<your-LAN-IP>:8000/web/` (find `<your-LAN-IP>` below — it looks like
`192.168.x.x` or `10.x.x.x`). There is **no authentication** — anyone on the LAN who
opens the URL can view the app (it serves read-only content; each person's progress
stays in their own browser).

### Windows 11

1. **Set the network to Private.** Settings → Network & internet → Wi‑Fi (or Ethernet)
   → click your connected network → set **Network profile type = Private**. (Windows
   only shares on Private networks; Public blocks inbound.)
2. **Find your LAN IP.** Open **Command Prompt** and run `ipconfig`; note the **IPv4
   Address** for your active adapter (e.g. `192.168.1.42`).
3. **Allow the port on the Private profile only.** Open **PowerShell as Administrator**
   and run:
   ```powershell
   New-NetFirewallRule -DisplayName "Claude Cert Study (LAN only)" -Direction Inbound `
     -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private
   ```
   This permits inbound TCP 8000 on Private networks only — never on Public.
4. **Start the server:** `uv run study/serve.py --host 0.0.0.0 --port 8000`.
5. From another device on the same network, open `http://<IPv4-from-step-2>:8000/web/`.
6. **When done**, stop the server (Ctrl+C) and remove the rule:
   ```powershell
   Remove-NetFirewallRule -DisplayName "Claude Cert Study (LAN only)"
   ```

### macOS 26+

1. **Confirm you're on a trusted private network** (home/office Wi‑Fi or Ethernet), not
   a public hotspot.
2. **Find your LAN IP.** System Settings → Network → select your active Wi‑Fi/Ethernet
   → **Details… → TCP/IP** → note the **IP Address** (e.g. `192.168.1.23`). Or in
   Terminal: `ipconfig getifaddr en0` (Wi‑Fi) — try `en1` if that's blank (Ethernet).
3. **Firewall (application-based on macOS).** If the firewall is on
   (System Settings → Network → Firewall), the first time you start the server macOS
   prompts *"Do you want to allow incoming network connections?"* for the Python/`uv`
   binary — choose **Allow**. (You can leave the firewall enabled; under **Firewall
   Options…** the interpreter should be set to *Allow incoming connections*.) macOS's
   firewall has no per-port rules — LAN-only is guaranteed by rules (1) and (2) above,
   not by the firewall.
4. **Start the server:** `uv run study/serve.py --host 0.0.0.0 --port 8000`.
5. From another device on the same network, open `http://<IP-from-step-2>:8000/web/`.
6. **When done**, stop the server (Ctrl+C). Do **not** enable System Settings → General
   → Sharing → *Internet Sharing* (that changes your network exposure).

### Sanity Check & Teardown

- Verify from the host that it's listening on the LAN: another device on the same
  network should load the URL; a device on a *different* network (e.g. cellular, not the
  Wi‑Fi) should **not**.
- Stop sharing at any time with Ctrl+C. The app is fully static/offline — no data leaves
  your network.

## Features

- **Quiz** — scenario multiple-choice (the exam's format), across three difficulty
  tiers (**Standard**, **Intermediate**, **Hard** — pick a set from the dropdown, or
  combine files on the CLI/TUI). Includes real multi-response **"Select N"** items,
  matching the exam's mixed single-/multi-answer format. Each question's answer
  options are reshuffled and relabeled every time it's shown, so repeat practice
  doesn't let you memorize a position instead of the content. Filter by domain / task
  statement, answer, then see the correct choice **and why each distractor is
  wrong**, with a running score and an end-of-set summary.
- **Flashcards** — click-to-flip fact recall (CLI flags, `tool_choice` values, batch
  limits, `stop_reason`, …), each card testing one single concept. Filter by
  domain and task statement, shuffle, and self-grade each card (✓ Got It / ✗ Missed
  It) to drive a "review missed" mode, tracked separately from quiz mastery.
- **Concepts** — one explainer per exam task statement (1.1–5.6): the idea, why it
  matters, the common trap, and a link to the relevant hands-on lab in `../labs/`.
- **Readiness** — a cumulative dashboard: overall readiness % (weighted by the exam's
  domain weights), per-domain and per-task mastery bars, a readiness-over-time
  sparkline, and "revisit lab-NN" suggestions for weak areas.

### Progress Tracking

Progress is cumulative and persists across sessions in your browser's `localStorage`
(no accounts). Because it's browser-local, a different browser/profile or clearing
site data starts fresh — use **Export** / **Import** on the Readiness view to back up
or move your progress, or **Reset** to start over.

## Content Model (`content/` + `exams/`)

Content is split into **components** (a question tier, a flashcard deck, a concept
set, the labs catalog) and **exams** that pin the components each of their sections
uses, so components can be reused and versioned independently of any one exam.

| File | What |
|------|------|
| `app.json` | Engine metadata: `app_version` (shown in the Web UI footer; kept in lockstep with `pyproject.toml` and `serve.py`). |
| `exams/index.json` | The available exams, by slug (the first is the default). |
| `exams/ccarf/exam.json` | The CCAR-F exam: code, name, guide, domains + weights, the 30 task statements and their labs, `config` (per-task question target, pass threshold), and `sections` — the components each section pins by id + version range (e.g. `"ccarf-questions-hard"` at `^1.0`). Section entries' labels drive the Web UI's set pickers. |
| `exams/ccarf/anthropic-ccarf-exam-guide-2026-07.md` | The CCAR-F exam guide — source of truth for its content (`-2026-06` is the prior edition). |
| `content/components.json` | Registry of every component: `{id, kind, version, file, task_scheme}`. `task_scheme` names the exam whose task-statement IDs the component's items use. |
| `content/ccarf-questions-standard.json` (240), `content/ccarf-questions-intermediate.json` (120), `content/ccarf-questions-hard.json` (75, incl. 10 multi-response) | Scenario multiple-choice questions by difficulty tier: stem, 4-5 options (A-E), a `correct` key (a single letter, or a 2+-letter array for a "Select N" item), per-distractor rationale, lab link. All three are schema-identical and interchangeable across every surface. |
| `content/ccarf-flashcards.json` | Front/back fact-recall cards (135), each testing a single concept. |
| `content/ccarf-concepts.json` | One explainer per task statement (30). |
| `content/labs.json` | The labs catalog, generated from `../labs/` by `tools/build_labs.py`. |
| `schema/*.schema.json` | JSON Schemas; every manifest and component is validated against these. |

Item IDs are prefixed with their exam slug and globally unique (`ccarf-q-1.1-001`,
`ccarf-fc-1.1-001`, `ccarf-concept-1.1`), since progress is keyed by them.

### Adding or Editing Content

Edit a component in `content/`; to add one, also register it in
`content/components.json` and pin it in the exam's `sections`. Bump the component's
`version` (major for breaking changes such as re-keyed IDs or changed task tags, and
the exam's pin to match). Then validate:

```bash
cd study && uv run pytest
```

The tests check schema validity; component integrity (valid answer keys, complete
distractor rationales, prefixed and unique IDs, real task statements, resolvable lab
links, the registry staying in sync with the files on disk); exam integrity (weights
summing to 100, the guide existing, every pin resolving to a component of the right
kind and version); and coverage per exam (question count per task statement, per-tier
minimums, one concept per task statement).

## Command-Line & TUI Tools (`tools/`)

Prefer a terminal? `quiz.py` / `quiz_tui.py` and `flashcards.py` / `flashcards_tui.py`
are standalone, dependency-free scripts offering the same content outside the
browser. Like the Web UI, they read the exam manifests: `--exam` picks the exam
(default: the first in `exams/index.json`, i.e. `ccarf`) and `--set` picks its
question/flashcard sets by label or component id (`--set hard`, repeatable, or
`--set all`; default: the exam's first set). Explicit JSON file paths still work
in place of `--set`.

Progress history is kept per exam in `.working/` (gitignored):
`quiz_history_<exam>.json` and `flashcards_history_<exam>.json`. On first run, a
pre-multi-exam `.working/quiz_history.json` / `flashcards_history.json` is migrated
into the CCAR-F file (IDs re-keyed to the `ccarf-` form; the original is left in
place). Each pair shares one "core" module (`quiz_tui.py` and `flashcards_tui.py`
just add a fixed-layout, full-screen rendering mode — same flags, same history
file), and all four share `exam_manifest.py` for exam/set resolution.

```bash
# Quiz: shuffle 20 Hard-tier questions, scoped to one domain
uv run study/tools/quiz.py --set hard --shuffle --num 20 --domain 1

# Combine tiers, or drill everything you've missed before
uv run study/tools/quiz.py --set standard --set intermediate
uv run study/tools/quiz.py --set all --review-missed

# Fixed-layout TUI variant (same flags)
uv run study/tools/quiz_tui.py --set hard --task 4.3

# Flashcards: self-graded recall, filtered to one task statement
uv run study/tools/flashcards.py --task 3.2
uv run study/tools/flashcards_tui.py --review-missed

# Your own question file instead of the exam's sets
uv run study/tools/quiz.py .working/my-questions.json --history .working/my-questions_history.json

# Full flag reference for any of the four
uv run study/tools/quiz.py --help
```
