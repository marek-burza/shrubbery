# Notes on Agentic Systems

This is a living document I keep my loose notes on Agentic Systems.

## General Rules

- Agents run sandboxed, with least privilege, least dependencies installed (and certainly no arbitrary ones), and least network access possible.
- Threat-model against the [OWASP Top 10 for Agentic Applications](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) (goal hijack incl. prompt injection, tool misuse, identity and privilege abuse, supply chain, unexpected code execution, memory and context poisoning, insecure inter-agent communication, cascading failures, human-agent trust exploitation, rogue agents).
- Anything that can be left to deterministic software, solvers or policies should be left to such specialized deterministic tools.

## Guardrails

- Where an LLM is part of the product itself (labeling, data extraction, etc.), I also find alternative means and require consensus between them to counterbalance the LLM.
- Budget caps & rate limits, blast-radius limits, and a decision on how to gracefully degrade when a cap/limit is reached.
- Lethal trifecta: an agent with private data, untrusted content and an outbound channel in one session can be tricked into leaking data, so remove one leg. Untrusted text is read by a quarantined model that returns only typed fields to the agent that can act (dual-LLM / [CaMeL](https://arxiv.org/abs/2503.18813)-style privilege separation).

## Use Cases for AI vs. Deterministic Software

AI should be used where the right answer can't be fully specified in advance but can be checked, and where it offers an edge over a classical approach (e.g. resulting in better metrics) or augments human or fully automated capability. AI should never act alone and unchecked; it is often best used in tandem with deterministic software. For example:

Deterministic software:
- Hardware drivers, protocol execution, state machines, etc.
- Identity (of physical items, human operators and technological artifacts) & security (authentication & authorization, sandboxing, etc.).
- Executing a chain of actions (with clear and validated interface contracts).
- Hard constraints and safety: operating limits (ranges of physical values), physical safety (e.g. collision avoidance) and domain logic (e.g. checking that a schedule is feasible, ordering does not breach invariants). These live in code and policy engines, never only in a prompt.
- The audit trail. Every technological artifact is versioned and traceable: code, prompts, model versions, tool definitions, the ontology (reviewed and tested like code), retrieval indexes, eval sets and datasets. Every fact an agent uses links back to its source record (provenance). Every run is one trace (model calls, tool calls, input snapshots, approvals), with a correlation ID carried across services, subagents and resulting records, structured as steps a human reviewer can follow and reason about.

AI:
- Turning an operator's intent into a draft protocol or a plan, which is then validated against the constraints above.
- Dynamic scheduling and replanning when hardware goes down or runs short of the items it operates on. An optimizer agent proposes, and a solver and the digital twin check the proposal before anything runs.
- Recovering from errors that a fixed rule doesn't cover: reasoning over physical system or hardware state, history, available resources, and past incidents and their remedies to suggest the next step.
- Interpreting messy signals: images, anomalies, free-text notes, etc.

## Patterns

Based on Anthropic's [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) (Schluntz & Zhang). Start from a single LLM call augmented with retrieval, tools and memory; add a pattern only when it measurably beats that, and an agent only when its role has its own tools, context or permissions. Workflows (fixed code paths) come before agents (the LLM directs its own steps). An agent is an LLM that runs tools in a loop to achieve a goal, the goal being the stopping condition ([Willison](https://simonwillison.net/2025/Sep/18/agents/); Anthropic uses the same definition).

- Prompt chaining: fixed sequence of LLM calls with programmatic gates between steps. Use when the task splits cleanly into known steps (e.g. draft a protocol, validate it, then translate it into instrument commands).
- Routing: classify the input, dispatch to a specialized prompt, tool or model. Use when inputs fall into distinct categories handled better separately (e.g. small or local models for simple classification and extraction, frontier models for multi-step reasoning).
- Parallelization: sectioning (independent subtasks run concurrently) or voting (same task run several times, results aggregated). Use for speed, or for confidence through consensus (e.g. guardrail checks, review of risky changes).
- Orchestrator-workers: a lead LLM decomposes the task at runtime, delegates to workers and synthesizes. Use when subtasks can't be predicted in advance (e.g. multi-file code changes, research across many sources).
- Evaluator-optimizer: a generator and a critic in a loop. Use when evaluation criteria are clear and iteration measurably improves the result (e.g. translation, iterative search, plan refinement against a solver's feedback).
- Autonomous agent: an LLM in a loop with tools, grounded in environment feedback, with stopping conditions (max iterations, budget). Use for open-ended problems with an unpredictable number of steps, only in sandboxed environments with checkpoints for human review.
- Blackboard (not in Anthropic's list; classic AI pattern, see [kadhar.dev](https://kadhar.dev/blog/multi-agent-systems-from-scratch)): no central coordinator, agents read and write a shared workspace and act when they can contribute. Use when the next step depends on discoveries (e.g. debugging, incident investigation). Hard to test and prone to loops, so it needs hop limits and a budget.

## Context Engineering

Assembling, at every model call, the smallest set of high-signal tokens (system prompt, tools, examples, history, retrieved data) that makes the desired behavior most likely. Output is a product of context and weights, and improving the context is cheaper and faster than a bigger model or more thinking. Based on Drew Breunig's [The State of Context Engineering](https://www.dbreunig.com/2026/10/24/the-state-of-context-engineering.html) and [How Contexts Fail and How to Fix Them](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html), Anthropic's [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), Manus' [Lessons from Building Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus) and Chroma's [Context Rot](https://research.trychroma.com/context-rot).

Pitfalls:
- Context rot: recall and reasoning degrade gradually as the window fills, in every model. Context is an attention budget, and a long window fits more information but also more errors.
- Context poisoning: a hallucination or wrong fact enters the context and keeps being referenced.
- Context distraction: a long context makes the model focus on it rather than its base knowledge and repeat past actions instead of planning anew.
- Context confusion: superfluous content (too many tools or skills, unrelated memories) steers answers unpredictably.
- Context clash: parts of the context contradict each other; examples in the history can override explicit instructions.
- Context inertia: the model keeps pursuing a hypothesis or subtask after it should have stopped.
- Fighting the weights: instructions that run against model's training. Shape tools and formats to what the model already knows.
- Self-imposed few-shot rut: a repetitive action-observation history makes the model imitate itself. Add controlled variation in serialization and phrasing.
- Memory accumulation: long-lived agents pile up conflicting memories and skills; strategic forgetting is unsolved.

Best practices and tactics:
- System prompt at the right altitude: between brittle if-else rules and vague guidance, in sections (XML tags or Markdown headers). Start minimal on the best model and add instructions only for observed failures. A few diverse, canonical examples beat a list of edge-case rules.
- Tools: few, non-overlapping, clearly scoped, with token-efficient outputs. If a human can't tell which tool to use, neither can the agent.
- Tool loadout: expose only the tools and skills a request needs (selected by a small model or a state machine). Mask tools rather than removing them mid-task, which keeps the cache and the history consistent.
- Just-in-time retrieval: keep lightweight references (paths, queries, URLs) and load data with tools when needed (progressive disclosure), combined with a small up-front context (e.g. `CLAUDE.md`).
- Offloading: keep state outside the window (files, database, todo list), with restorable compression: drop the content, keep its path or URL.
- Recitation: rewrite the plan or todo list at the end of the context to keep the goal in recent attention.
- Pruning and compaction: drop turns no longer needed, clear old tool results, summarize near the limit. Tune the summary for recall first, then precision; a small model can filter what is relevant before summarizing.
- Quarantine: subagents explore in clean windows and return condensed summaries (1-2k tokens) to the lead agent.
- Reset: start fresh (Breunig at around 200k-300k tokens), or reset periodically with a short handoff note while the environment persists.
- Keep errors in: failed actions and stack traces in the context keep the model from repeating them.
- KV-cache: stable prefix (no timestamps at the top), append-only context, deterministic serialization. Cached input tokens can be ~10x cheaper.
- Deterministic first: assemble the context in code wherever possible and leave to the model only what can't be specified.
- Typed domain model: ground agents in an ontology (objects, states, relations, allowed actions) rather than flat documents; a typed knowledge graph lifted industrial agents from 65% to 82-83% accuracy, so the data layer matters more than the model. Validate data contracts (schema, units, timezones) on ingestion, show the agent the data's age, and let tools turn raw signals into statistics and events instead of feeding the model raw arrays.

## Designing MCPs

Based on Anthropic's [Writing Effective Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents) (Aizawa) and the MCP spec's [Security Best Practices](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices). Tools are a contract between deterministic software and a non-deterministic agent, so they are designed for the agent, not mirrored from an API.

- Workflows, not endpoints: a few targeted tools for high-impact tasks instead of wrapping every API endpoint. Consolidate multi-step operations (`schedule_event` over `list_users` + `list_events` + `create_event`) and prefer search over list. Use all MCP primitives: schema and reference data as resources, standard procedures as prompts.
- Namespacing: prefix by service and resource (`asana_projects_search`) so overlapping tools stay distinguishable across servers.
- Descriptions as onboarding: explain niche terms, query formats and relations between resources as to a new hire. Unambiguous parameter names (`user_id`, not `user`), units, an example call, and strict, typed schemas.
- Meaningful, token-efficient output: natural-language names over opaque IDs, a `response_format` (concise or detailed), pagination, filtering and truncation with sensible defaults. Errors and truncation notices tell the agent what to do next, not just a code or traceback.
- Read vs. write: mark tools with annotations (read-only, destructive, open-world) and keep state-changing tools typed and permissioned. Propose returns a draft, diff and simulation result; a commit is separate (and is gated with an approval/authorization and relies on an idempotency key). Expose task-level skills (`start_changeover`) that check preconditions, never raw writes.
- Security: least-privilege scopes escalated incrementally, never pass the client's token through to downstream APIs (accept only tokens issued to the server), sessions are not authentication, and local servers run sandboxed over `stdio`. Pin and review third-party server versions, since tool descriptions can change after approval. Tool output is untrusted input to the agent.

## Evaluation

- Eval set before the feature (like TDD): replay real incidents with known outcomes, keep a held-out split.
- Four levels: retrieval (recall@k), generation (groundedness, citations), trajectory (tool choice, arguments, steps, cost) and business outcome. Measure the decision, not the text.
- Hallucination checks: every ID, number and code must exist in the domain model or the source; split answers into claims and verify each against evidence. Track abstention rate alongside accuracy so confident guessing isn't rewarded.
- CI gate on every change to prompts, models, tools, ontology or index; pin model versions, canary rollouts.
- LLM-as-judge only after calibration against experts (100-200 samples).
- Failure analysis with [MAST](https://arxiv.org/abs/2503.13657): specification, inter-agent misalignment, verification.
- Evaluation: prototype in a local server, then run realistic multi-call tasks with verifiable outcomes and held-out sets. Track tool calls, tokens and errors, read the transcripts, and let an agent refactor the tools from them.

## Autonomy Spectrum

How AI earns more autonomy:

- Workflow first, agent second. Known procedures stay fixed code paths; agents handle investigation, where the path can't be scripted but progress can be checked.
- Simulate before acting. Every plan generated by AI runs against the simulator or the digital twin first. Simulated instruments also give the agents that change system state a fast, safe feedback loop before it touches real physical system.
- Graded autonomy, configurable per workflow: 0 inform, 1 recommend, 2 act with approval, 3 act and notify. A workflow moves up a level only after its accuracy has been measured at the level below, starting in shadow mode next to the scientists. Sign-off stays with a named person where liability sits.
- Separate read tools from write tools. Queries are free; anything that changes (physical) state (moving a robot arm, starting a chemical reaction or writing a database record) is a typed, permissioned tool where the AI proposes and a separate step commits. Writes are idempotent and reversible (dry-run, rollback or compensation), and long approvals run in durable workflows.
- Abstention. When confidence is low or the data is stale, the system says so and hands over to a human. Confidence scores are calibrated against observed accuracy (conformal prediction for classic ML).
- The physical system must keep running without AI. A kill switch drops any workflow back to manual or fully deterministic execution.

## Measuring Adoption

- Leading indicators: Share of workflow executions with use of AI/agent. Additionally, a share of these executions which were sustained (were not corrected, redone, etc.).
- Real indicators: Domain oriented, such as cycle/turnaround time stats, etc.
- Guardrail indicators: quality trend, incident trend, complexity trend, override and acceptance rate per recommendation type (automation complacency, alert fatigue).

## Agentic Tech

### Prompt Programming & Optimization

- [DSPy](https://github.com/stanfordnlp/dspy) (Stanford NLP): declarative framework for programming LLMs in Python instead of hand-writing prompts. Pipelines are composed of modules with typed signatures (inputs and outputs), and optimizers (e.g. MIPROv2, GEPA) tune the prompts, few-shot examples or weights against a metric on a dataset.

### Durable Workflows

- [Temporal](https://github.com/temporalio/temporal): retries, idempotency and long-running human approvals.

### Policy Engines

- [OPA](https://github.com/open-policy-agent/opa): action authorization outside the prompt.

### Observability & Evals

- [Langfuse](https://github.com/langfuse/langfuse) (ClickHouse): tracing of every model and tool call, datasets and LLM-as-judge scoring.
- [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) (UK AI Security Institute): eval harness for tasks, agent trajectories and sandboxed tool use.

### Model Access

- [Pydantic AI](https://github.com/pydantic/pydantic-ai) (Pydantic team): one typed API over many providers, with validated structured outputs and fallback models, in-process instead of a separate proxy.

### Sandboxes

- [gVisor](https://github.com/google/gvisor), [Firecracker](https://github.com/firecracker-microvm/firecracker): isolation for agent-executed code.

### Agent Coordination

- Orchestration frameworks (in-process): [LangGraph](https://github.com/langchain-ai/langgraph) (state graph), [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) (handoffs), [Google ADK](https://github.com/google/adk-python) (sequential, parallel and loop workflow agents), [CrewAI](https://github.com/crewAIInc/crewAI) (role-based crews).
- [A2A](https://github.com/a2aproject/A2A) (Linux Foundation): protocol for agent-to-agent discovery and task delegation, complementing MCP (agent-to-tool).
- Event buses for loosely coupled agents: MQTT ([Mosquitto](https://github.com/eclipse-mosquitto/mosquitto), [EMQX](https://github.com/emqx/emqx); the shop-floor and IoT standard), [Kafka](https://github.com/apache/kafka) (durable, replayable event log), [NATS](https://github.com/nats-io/nats-server) (lightweight, cloud and edge).
