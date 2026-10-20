# D5 · Context Management & Reliability — Video Resources

Videos that explain or demonstrate the [Concept Explainers](../content/concepts.json) for
Domain 5. See [`README.md`](README.md) for scope and how these were sourced.

### 5.1 Managing conversation context to preserve critical information across long interactions

- **[Effective context engineering for AI agents by Anthropic](https://www.youtube.com/watch?v=139Cfcrt2Mk)** — Oran Danon. Walks through Anthropic's context-engineering guide, including compaction, note-taking/scratchpads, and sub-agent architectures for keeping critical facts intact over long sessions.
- **[Anthropic Workshop: Build Agents That Run for Hours — Ash Prabaker & Andrew Wilson](https://www.youtube.com/watch?v=mR-WAvEPRwE)** — AI Engineer. Anthropic's own Applied AI team demonstrates hands-on techniques (structured handoffs, note-passing across context resets) for surviving context rot in multi-hour agent sessions — directly relevant even though framed around long-running agents rather than pure chat.

### 5.2 Escalation Triggers and Ambiguity Resolution

- **[Build an AI Customer Support Email Agent using Claude Code | Agentic AI Project](https://www.youtube.com/watch?v=ImbmSEPo7qI)** — Sunny Savita. Closest match found after extensive search: a hands-on walkthrough of building a Claude-based support agent; it covers the general support-agent build but does not specifically demonstrate the disambiguation-by-additional-identifier pattern, so treat it as a broader-topic stand-in.

### 5.3 Error propagation strategies across multi-agent systems

- **[Building more effective AI agents](https://www.youtube.com/watch?v=uhJJgc-0iTQ)** — Anthropic. Alex Albert interviews Erik Schluntz on orchestrator/subagent design, including how agents recover from errors and when subagent architectures help vs. hurt.
- **[How We Build Effective Agents: Barry Zhang, Anthropic](https://www.youtube.com/watch?v=D7_ipDqhtwk)** — AI Engineer. Anthropic Applied AI's Barry Zhang on agent design fundamentals — environment, tools, and "thinking from the agent's context window," which underpins why generic error statuses fail; broader agent-design talk rather than error-propagation-specific.
- **[Exploring Multi-Agent Systems: Key Insights from Anthropic and Cognition](https://www.youtube.com/watch?v=evDb9SQ15CQ)** — Richmond Alake. Reviews Anthropic's and Cognition's published multi-agent lessons, including coordination/failure pitfalls in orchestrator-subagent handoffs.

### 5.4 Managing context in large codebase exploration

- **[Context Management in Claude Code](https://www.youtube.com/watch?v=eW3oTyfeWZ0)** — Claude (Anthropic's official channel). Hands-on guidance on when to use `/compact` vs `/clear` to keep a long Claude Code session usable — directly demonstrates the in-place context-reduction technique.
- **[Context Window Management in Claude Code](https://www.youtube.com/watch?v=lN5tLx2_7HQ)** — CampusX. Explains what fills Claude Code's context window during real sessions, useful groundwork for understanding degradation during large-codebase exploration; more explainer than live large-repo demo.

### 5.5 Human review workflows and confidence calibration: seeing past aggregate accuracy

- **[Confidence scores for Box AI Extract: Know when to rely on your extractions](https://www.youtube.com/watch?v=sTXMYV6gcvw)** — Box. Hands-on demo of field-level confidence scores driving auto-approve vs. human-review routing in a real extraction product — the closest real-world demonstration found of calibrated-confidence-driven review workflows (note: a general document-extraction product demo, not CCAR-F-specific, but matches the mechanics closely).

### 5.6 Preserving provenance and handling uncertainty in multi-source synthesis

- **[Anthropic's Secret: How we Build Multi-Agent AI](https://www.youtube.com/watch?v=os5Qxk9tfr0)** — Discover AI. Detailed walkthrough of Anthropic's multi-agent research system, including the citation-agent/structured claim-source mapping approach that prevents attribution from decaying during synthesis.
- **[How Anthropic built their multi-agent research system?](https://www.youtube.com/watch?v=9l4tvyRA1Ts)** — The AI Insider. Second take on the same Anthropic architecture, reinforcing how subagent findings are preserved and reattached to sources at synthesis time.
- **[#322 How to resolve knowledge conflicts during RAG in LLMs?](https://www.youtube.com/watch?v=kc49P8VDwkI)** — Data Science Gems. Covers detecting and surfacing (rather than arbitrarily averaging or dropping) conflicting information from multiple retrieved sources — a broader RAG-focused video, not multi-agent-specific, included as the closest match for the conflict-annotation half of this concept.
