# D3 · Claude Code Configuration & Workflows — Video Resources

Videos that explain or demonstrate the [Concept Explainers](../content/concepts.json) for
Domain 3. See [`README.md`](README.md) for scope and how these were sourced.

### 3.1 CLAUDE.md Hierarchy, Scoping, and Modular Organization

- **[Claude Code best practices | Code w/ Claude](https://www.youtube.com/watch?v=gv0WHhKelSE)** — Anthropic. Official Anthropic talk (Cal Rueb) explaining how CLAUDE.md provides persistent project context and how to structure it — the primary authoritative source on the mechanism.
- **[Anatomy of the .claude/ Folder — The Secret to 10x Claude Code](https://www.youtube.com/watch?v=rX6DLHlaOhU)** — Daniel Noworyta. Hands-on walkthrough showing project vs. global `.claude` folders, how multiple CLAUDE.md files stack/take precedence, `@import` for external files, and `/init`.
- **[Claude Code's Memory System: The Full Guide](https://www.youtube.com/watch?v=FRwZg6VOjvQ)** — DIY Smart Code. Explains the multi-level memory hierarchy (user/project/directory) and recursive imports in depth.

### 3.2 Custom slash commands and skills: scope, SKILL.md frontmatter, and skills vs CLAUDE.md

- **[Claude Code Skills & Agents — The .claude/ Folder Part 2](https://www.youtube.com/watch?v=tol7eILAF8w)** — Daniel Noworyta. Hands-on demo of Commands vs. Skills, building `SKILL.md` files, path-scoped skills that trigger automatically, and subagents — directly on point.
- **[Claude Code Skills: Build Custom Slash Commands](https://www.youtube.com/watch?v=hyo13fgkegQ)** — Alex To Go Eng. Live demo creating custom slash commands via `.claude/commands/` and `SKILL.md`.
- **[How to Create Claude Code Agent Skills in 2026](https://www.youtube.com/watch?v=nbqqnl3JdR0)** — Code with Beto. Hands-on tutorial building an Agent Skill from scratch, including frontmatter configuration.

### 3.3 Path-Specific Rules for Conditional Convention Loading

- **[Anatomy of the .claude/ Folder — The Secret to 10x Claude Code](https://www.youtube.com/watch?v=rX6DLHlaOhU)** — Daniel Noworyta. Directly demonstrates the `.claude/rules/` folder and scoping rules to specific file paths, showing how conventions load conditionally by glob pattern.
- _No second closely-matching video found — this is a narrow, recently-added feature with scarce dedicated coverage._

### 3.4 Plan mode vs. direct execution, and the Explore subagent

- **[Claude Code's Hidden Subagents: Plan + Explore → Team Mode](https://www.youtube.com/watch?v=FUAqVZAKFf4)** — Matt Maher. Specifically walks through the built-in Plan and Explore subagents and how they isolate discovery/planning from the main conversation.
- **[Why You Need Plan Mode in Claude Code (Pro Tips)](https://www.youtube.com/watch?v=FoRIj5qcslg)** — GritAI Studio. Hands-on demo of entering plan mode, editing plans, and guidance on when to use it vs. direct execution.
- **[Claude Code Plan Mode: Think Before You Build](https://www.youtube.com/watch?v=wwWUkBGTLUE)** — Joe Rhew. Live side-by-side demo comparing results with and without plan mode, including when *not* to use it.

### 3.5 Iterative refinement techniques: examples, test-driven iteration, the interview pattern, and batching interacting issues

- **[Red Green Refactor is OP With Claude Code](https://www.youtube.com/watch?v=hYZdIwFIy-c)** — Matt Pocock. Hands-on demo of the test-driven red-green-refactor cycle as a way to give Claude Code a precise, measurable target each round.
- **[Claude Code 'Interview' Mode in 6 Minutes](https://www.youtube.com/watch?v=vgHBEju4kGE)** — Developers Digest. Demonstrates the interview pattern directly — having Claude ask clarifying questions before implementing (interview-first, spec-second, code-last).
- **[Claude Code best practices | Code w/ Claude](https://www.youtube.com/watch?v=gv0WHhKelSE)** — Anthropic. Official talk covering broader iterative-workflow guidance (planning, feedback loops, redirecting Claude); included as the closest authoritative video touching examples-driven and batched-feedback iteration, though it doesn't isolate all four techniques individually.

### 3.6 Running Claude Code non-interactively in CI/CD with structured, deduplicated, independent review

- **[Claude Code + GitHub Actions](https://www.youtube.com/watch?v=L_WFEgry87M)** — Anthropic. Official demo showing Claude Code running non-interactively from GitHub PRs (via the Claude Code SDK/Action), responding to reviewer feedback and fixing CI errors automatically.
- **[Claude Code GitHub Action: Automated PR Reviews Setup](https://www.youtube.com/watch?v=R1MvBwoyHxw)** — The Gray Cat. Step-by-step hands-on setup of the official Claude GitHub Action for automated PR reviews, including troubleshooting.
- **[I Asked Codex to Review Claude Code's Code. And Vice Versa.](https://www.youtube.com/watch?v=lleyHrcp1is)** — AI Coding Daily. Hands-on demonstration of using an independent AI reviewer (Codex reviewing Claude Code's output and vice versa) to avoid self-review bias — relevant to the "independent instance for review" principle, though it doesn't cover the `--output-format json`/dedup-on-rerun mechanics specifically.
