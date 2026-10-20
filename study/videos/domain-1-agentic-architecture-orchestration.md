# D1 · Agentic Architecture & Orchestration — Video Resources

Videos that explain or demonstrate the [Concept Explainers](../content/ccarf-concepts.json) for
Domain 1. See [`README.md`](README.md) for scope and how these were sourced.

### 1.1 The Agentic Loop and stop_reason

- **[Claude Certified Architect: Full Course Ep 01: Agentic Loops & stop_reason Explained](https://www.youtube.com/watch?v=ldqOnljDINc)** — Peace Of Code. Walks through the request/inspect-`stop_reason`/execute-tools/append-`tool_result` loop and how it terminates on `end_turn`, directly matching this task statement.
- **[How We Build Effective Agents: Barry Zhang, Anthropic](https://www.youtube.com/watch?v=D7_ipDqhtwk)** — AI Engineer (conference talk by an Anthropic Applied AI team member). Broader talk on agent design principles rather than a `stop_reason` code walkthrough, but it's an official-source explanation of why model-driven tool selection (vs. hard-coded flows) matters.

### 1.2 Coordinator-subagent orchestration in hub-and-spoke multi-agent systems

- **[Multi-Agent Systems & Coordinator Patterns Explained | Claude Certified Architect Ep 02](https://www.youtube.com/watch?v=ejPWvBcc_DU)** — Peace Of Code. Explains the hub-and-spoke coordinator model directly: delegation, isolated context, and routing all communication through the coordinator.
- **[Exploring Subagents in Claude Code with Addy Osmani](https://www.youtube.com/watch?v=o-kN3vkZcZ4)** — O'Reilly. Hands-on discussion of subagent isolation and orchestration patterns in Claude Code from a serious, reputable dev voice.

### 1.3 Subagent invocation, context passing, and spawning

- **[Claude Certified Architect Ep 03 | Subagent Context Passing & Session Management | Full Course](https://www.youtube.com/watch?v=a2N6vKdQUfE)** — Peace Of Code. Covers subagents starting with zero inherited memory/context and how context must be explicitly passed.
- **[Claude Certified Architect Ep 04 | Multi-Agent System in Python & Claude SDK | Hands On](https://www.youtube.com/watch?v=e7ijjK173zI)** — Peace Of Code. Hands-on coded build of a multi-agent system with the Claude Agent SDK, demonstrating the Task-tool/`AgentDefinition` mechanics live rather than just describing them.

### 1.4 Enforcement and handoff patterns in multi-step workflows

- **[Claude Certified Architect: Full Course Ep 05 — PreToolUse, PostToolUse Hooks & Task Decomposition](https://www.youtube.com/watch?v=JJBcpwpsKzk)** — Peace Of Code. Note: this episode's primary framing is hooks and task decomposition rather than "enforcement vs. handoff" by name, but it directly demonstrates the prerequisite-gate mechanism (PreToolUse blocking a downstream tool call) that this concept is built on — the closest match found.

### 1.5 Agent SDK Hooks for Tool Interception and Data Normalization

- **[Claude Certified Architect: Full Course Ep 05 — PreToolUse, PostToolUse Hooks & Task Decomposition](https://www.youtube.com/watch?v=JJBcpwpsKzk)** — Peace Of Code. Directly covers PostToolUse result transformation and PreToolUse call interception.
- **[Hooks in Claude Code — Full Theory + Practical Use](https://www.youtube.com/watch?v=oo1oADOiVmM)** — CampusX. Hands-on, practical walkthrough of hook configuration and blocking/transforming tool behavior deterministically.

### 1.6 Task decomposition strategies: prompt chaining vs. dynamic adaptive decomposition

- **[#14 Prompt Chaining vs Dynamic Decomposition | DevCompass | Claude Certified Architect Prep Cohort](https://www.youtube.com/watch?v=kEWsUYtldrA)** — DevCompass. Title-matches this exact concept: fixed sequential pipelines vs. adaptive, discovery-driven replanning.
- **[Claude Certified Architect: Full Course Ep 05 — PreToolUse, PostToolUse Hooks & Task Decomposition](https://www.youtube.com/watch?v=JJBcpwpsKzk)** — Peace Of Code. Also covers task decomposition as part of its broader hooks discussion.

### 1.7 Managing session state: resumption, forking, and knowing when context is stale

- **[Claude Certified Architect Ep 03 | Subagent Context Passing & Session Management | Full Course](https://www.youtube.com/watch?v=a2N6vKdQUfE)** — Peace Of Code. Covers session management alongside context passing, including when re-supplying context beats reuse of stale history.
- **[Stop Memorizing Random IDs 🛑 Claude Code Sessions Explained](https://www.youtube.com/watch?v=GWG89MIjfHw)** — AUTOHOTKEY Gurus. Hands-on demo of Claude Code's `/resume` and `/branch` (fork) commands for named-session resumption and branching.
