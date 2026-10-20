# D4 · Prompt Engineering & Structured Output — Video Resources

Videos that explain or demonstrate the [Concept Explainers](../content/ccarf-concepts.json) for
Domain 4. See [`README.md`](README.md) for scope and how these were sourced.

### 4.1 Explicit criteria and severity rubrics to improve precision and reduce false positives

- **[Anthropic's NEW Claude Code Review Agent (Full Open Source Workflow)](https://www.youtube.com/watch?v=nItsfXwujjg)** — Patrick Ellis. Hands-on walkthrough of Anthropic's multi-agent PR review workflow, showing how findings are verified and ranked by severity to cut false positives.
- **[Claude Certified Architect: Ep 14 | Prompt Engineering — Explicit Criteria & False Positives](https://www.youtube.com/watch?v=HqwULqy1egw)** — Peace Of Code. Exam-prep explainer video whose title and content map directly onto this task statement (explicit criteria over vague "be conservative" instructions); talking-head format rather than a live demo.

### 4.2 Few-shot prompting for output consistency and quality

- **[Prompting 101 | Code w/ Claude](https://www.youtube.com/watch?v=ysPbXH0LpIE)** — Anthropic. Official hands-on session alternating slides and live console demos, explicitly covering few-shot/multishot examples (using an insurance-claim scenario) and iterating prompts across ambiguous cases.
- **[Building with Anthropic Claude: Prompt Workshop with Zack Witten](https://www.youtube.com/watch?v=hkhDdcM5V94)** — AI Engineer. Workshop led by an Anthropic prompt engineer covering example-driven steering of Claude's outputs.

### 4.3 Enforcing structured output with tool use and JSON schemas

- **[Claude Structured Outputs Demo: Guaranteed JSON Schema Compliance (No Regex, No "Almost JSON")](https://www.youtube.com/watch?v=Qq6nTf6V10w)** — ABV — AI · Books · Validation. Hands-on demo of Claude's structured-output/tool-schema guarantee eliminating malformed JSON.
- **[Getting Started with Tool Use in the Anthropic API](https://www.youtube.com/watch?v=7xVmf9lIj14)** — Ram Vegiraju. Live-coding walkthrough of defining a tool schema and forcing Claude to call it.
- **[Claude API: Strict Response Types/Schemas (for Dummies) - Anthropic](https://www.youtube.com/watch?v=kiooXcT4E0g)** — Nodematic Tutorials. Follow-along tutorial implementing strict schema-constrained responses via the Claude API.

### 4.4 Validation, retry, and feedback loops for extraction quality

- **[#27 Validation & Retry | DevCompass | Claude Certified Architect Prep Cohort](https://www.youtube.com/watch?v=zaDhWZ0sFtg)** — DevCompass. Exam-prep episode covering retry-with-error-feedback and the syntax-vs-semantic error distinction directly; closest match found, but a talking-head/slide format rather than a live demo.
- **[Claude Code Patterns: Feedback loops](https://www.youtube.com/watch?v=CNYE5nQfRaQ)** — Delba. Broader-topic video (not extraction-specific) on designing self-verification feedback loops so Claude can check and correct its own work — included as the closest hands-on adjacent coverage.

### 4.5 Designing efficient batch processing strategies with the Message Batches API

- **[#29 Batch Processing | DevCompass | Claude Certified Architect Prep Cohort](https://www.youtube.com/watch?v=L6pcS70-whw)** — DevCompass. No dedicated hands-on Message Batches API demo video surfaced in search; this exam-prep episode is the closest matching video, covering cost/latency trade-offs and matching API to workload directly, but is a talking-head explainer rather than a live coding demo.

### 4.6 Multi-instance and multi-pass review architectures

- **[Self Code Review vs Claude Code Review](https://www.youtube.com/watch?v=SIWS3An0J2o)** — APPSIMPACT Academy. Directly contrasts self-review (generator reviewing its own work) against Claude's separated-reviewer architecture.
- **[Anthropic's NEW Claude Code Review Agent (Full Open Source Workflow)](https://www.youtube.com/watch?v=nItsfXwujjg)** — Patrick Ellis. Hands-on demo of the multi-agent, multi-pass review pipeline (parallel specialized reviewers plus a verification/aggregation pass).
- **[Multi-Agent Code Review using Generative AI and LangGraph](https://www.youtube.com/watch?v=pdnT3yLk70c)** — Data Science in your pocket. Broader-topic (LangGraph, not Claude-specific) hands-on build of a multi-agent reviewer/generator separation pattern; included since it demonstrates the underlying architecture live.
