# D2 · Tool Design & MCP Integration — Video Resources

Videos that explain or demonstrate the [Concept Explainers](../content/concepts.json) for
Domain 2. See [`README.md`](README.md) for scope and how these were sourced.

### 2.1 Tool descriptions as the primary tool-selection mechanism

- **[Claude Certified Architect: Full Course Ep 06: Tool Descriptions & Tool Misrouting Explained](https://www.youtube.com/watch?v=s1j1vTnCKns)** — Peace Of Code. Walks through why Claude picks the wrong tool and how vague/near-identical descriptions cause misrouting, directly matching this task statement.
- **[Getting Started with Tool Use in the Anthropic API](https://www.youtube.com/watch?v=7xVmf9lIj14)** — Ram Vegiraju. Hands-on, live-coded walkthrough of defining tools (name, description, input schema) for the Claude API; broader "tool use" scope than description-writing alone, but shows the actual description fields in practice.

### 2.2 Structured Error Responses for MCP Tools

- **[Claude Certified Architect Ep 07: Agent Error Handling & tool_choice Explained](https://www.youtube.com/watch?v=eZj6FtTVV58)** — Peace Of Code. Covers `isError`, and the transient/validation/business/permission error categories with retryable metadata that let an agent choose a recovery path; this same episode also covers `tool_choice` (see 2.3 below), so it's the closest single match found for structured MCP error responses.

### 2.3 Distributing tools across agents and configuring tool_choice

- **[Claude Certified Architect Ep 07: Agent Error Handling & tool_choice Explained](https://www.youtube.com/watch?v=eZj6FtTVV58)** — Peace Of Code. Second half of the episode explains the `auto` / `any` / forced-tool `tool_choice` modes and when each guarantees (or doesn't guarantee) a tool call.
- **[How to Use Subagents in Claude Code](https://www.youtube.com/watch?v=dk0kn2evY38)** — Tim Warner. Hands-on demo configuring distinct tool permissions per subagent (e.g., read-only research agent vs. full-edit implementation agent), demonstrating least-privilege tool distribution across agents; it doesn't cover `tool_choice` itself, included for the distribution half of this task statement.

### 2.4 Integrating MCP servers: scoping, secrets, simultaneous tools, and resources

- **[Claude Certified Architect: Full Course Ep 08 | MCP Servers, Config, Cline & More](https://www.youtube.com/watch?v=IVUxGTxSuH8)** — Peace Of Code. Covers project-level vs. user-level MCP config and the "works on my machine but not my teammate's" scoping problem this task statement targets.
- **[How to easily share the Claude Code MCP config with your team](https://www.youtube.com/watch?v=l7FFoFpHMOM)** — JointJS. Hands-on demo of committing `.mcp.json` to a repo so a team shares the same MCP servers — a concrete demonstration of project-level scoping.
- **[Adding MCP Servers to Claude Code: Real Examples That Work](https://www.youtube.com/watch?v=YA1zexKqiDg)** — Nathan Sebhastian. Walks through real MCP server configs in Claude Code, including how servers and their tools get registered/discovered.

### 2.5 Selecting and applying built-in tools (Read, Write, Edit, Grep, Glob)

- **[Claude Code Tools | E16 | Read, Edit, Write, Grep, Glob & Bash](https://www.youtube.com/watch?v=OlTyh06tj2E)** — Neetu Sharma. Hands-on walkthrough distinguishing each built-in tool (content search vs. path search vs. full read/write vs. targeted edit) with live examples.
- **[Claude Certified Architect: Ep 09 | Claude Built-in Tools Explained | Full Course Series](https://www.youtube.com/watch?v=eh-xxQpfBBY)** — Peace Of Code. Exam-aligned explainer of when to use each built-in tool and the costs of choosing the wrong one.
