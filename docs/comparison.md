# Comparison: AURA Harness vs. Alternatives

AURA Harness is a **framework-agnostic runtime membrane** — a sidecar that wraps agent loops for audit and policy at the I/O boundary. It is **not** an orchestrator, eval suite, or tool framework.

For architecture and current scope, see [architecture.md](architecture.md) and [ROADMAP.md](ROADMAP.md).

This document clarifies how AURA compares to **DeepSeek Harness (DSH)**, **LangGraph**, **CrewAI**, **LangSmith / eval harnesses**, **DeepEval / RAGAS**, **MCP**, and generic **observability** stacks.

**Ecosystem note**: AURA does not compete with [Skillware](https://github.com/arpahls/skillware) (installable capabilities) or [Rooms](https://github.com/arpahls/rooms) (multi-agent environments). Tools live inside the core cavity; AURA wraps the cavity. Skillware can supply tools *inside*; AURA records and gates what crosses the edge.

---

## Production agent run: same task, different approaches

**Running a Python agent that calls tools and must prove what happened** — qualitative comparison:

| Approach | Build inside their stack? | Full causal audit | Policy before world effects | Works with existing script |
| :--- | :--- | :--- | :--- | :--- |
| **AURA Harness** | No — wrap what you have | Yes (JSONL + audit report + hash chain) | Yes (constitution, gates, egress on wired paths) | Yes (SDK + Skillware host; broader intercept roadmap) |
| **DeepSeek Harness** | Yes — plugins, profiles, session model | Yes (SessionEvent log) | Partial (sandbox, approval in base) | No — adopt DSH runtime |
| **LangGraph** | Yes — graph nodes and state | Via LangSmith / custom | Via graph logic you write | No — model as graph |
| **CrewAI** | Yes — crews, roles, tasks | Via external logging | Via agent/task design | No — CrewAI workflow |
| **LangSmith / tracing** | Optional | Traces and spans | No — observe only | Partial — instrument calls |
| **DeepEval / RAGAS** | N/A — offline eval | Post-hoc on datasets | No | N/A — batch eval |

AURA optimizes for **provenance and boundary control** on live runs, not benchmark scores on fixed datasets.

---

## The fundamental split: Orchestrator vs. Membrane

Most agent frameworks are **orchestrators**: you express logic in their primitives (graph nodes, crew tasks, plugin trees, turn loops).

AURA is a **membrane** (sidecar):

```
External in → Ingress → [ Your logic — black box ] → Egress → World + Audit sink
```

| | Orchestrator | AURA membrane |
| :--- | :--- | :--- |
| **Owns control flow** | Yes | No |
| **Owns model/tools** | Often bundled | No — any subset inside cavity |
| **You build for it** | Yes | No — drop in what exists |
| **Primary output** | Completed task | Session export + audit report (receipt) |
| **Long-term role** | Application framework | Infrastructure coat |

You can run LangGraph, CrewAI, DSH, or a 10-year-old script **inside** the cavity and wrap it with AURA.

---

## Prompt harness vs. membrane configuration

Much of today's agent engineering — prompt libraries, reviewer agents, merge gates, "define done in the system prompt" — optimizes **inside the cavity**: better instructions, more orchestration, more models reviewing each other.

AURA optimizes **at the boundary**: ingress normalization, egress policy, mechanical gates, and a **session receipt** on close.

| Concern | Typical workflow / prompt harness | AURA membrane |
| :--- | :--- | :--- |
| **What "done" means** | Described in prompts; humans judge output | Declared in **gates**, rules, and export invariants; **verdict** on session close |
| **Rules** | Documented for the model to read | Encoded in **constitution / constraints**; violations on the spine |
| **Review** | Secondary reviewer agents or human diff review | **Constraint engine** blocks or denies at egress; humans **steer policy**, not every token |
| **Failure handling** | Rewrite prompts, add examples | **Gate deny → structured event → retry step** (sequencer); tighten membrane rules so the class of failure cannot exit again |
| **Proof** | Logs, traces, screenshots | **Causal audit trail** (JSONL) + summary + **audit report** + hash chain (signed packs on roadmap) |
| **Your job** | Babysit the agent loop | **Configure the coat** — profile, rules, gates, approvals — then review the receipt |

This is the same insight behind repeatability-and-constraints thinking in modern AI engineering — but implemented as **runtime enforcement and provenance**, not as another layer of prompts or orchestrator nodes.

AURA is **not** a guide for building the agent. It is infrastructure for **configuring what may cross the perimeter** and **proving what did**.

---

## 1. AURA vs. DeepSeek Harness (DSH)

[DeepSeek Harness](https://github.com/deepseek-ai/DeepSeek-Harness) treats composability as core: plugins for model, tools, sandbox, session events, profiles at boot.

### Similarities

* Append-only session log as source of truth
* Interception seams (pre/post tool, turn)
* Sandbox and approval concepts

### Key differences

* **Positioning**: DSH is a **runtime you adopt** — "everything is a plugin" *inside* DSH. AURA is a **wrapper around whatever runtime you already have**.
* **Identity / accountability chain**: DSH focuses on session integrity; AURA adds `agent_ref` (ULID), audit report, and hash-chained spine events without requiring a central identity service (optional enrichment adapters on roadmap).
* **Long term**: DSH competes on composable agent OS; AURA competes on **agnostic governance layer** — including the option to wrap DSH itself inside the cavity.

---

## 2. AURA vs. LangGraph

[LangGraph](https://github.com/langchain-ai/langgraph) models agents as **stateful graphs** — nodes, edges, checkpoints, human-in-the-loop.

### Key differences

* **Graph is the product**: LangGraph requires you to structure work as a graph. AURA does not require a graph, steps, or nodes.
* **Observability**: LangGraph pairs with LangSmith for traces. AURA produces a **session-native audit trail** (JSONL + audit report + conformance summary) designed for provenance and compliance export, not only LLM debugging.
* **Complementary**: LangGraph inside the cavity; AURA on the boundary — policy and audit outside the graph definition.

---

## 3. AURA vs. CrewAI (and AutoGen)

[CrewAI](https://www.crewai.com/) and [AutoGen](https://microsoft.github.io/autogen/) orchestrate **multi-agent workflows** — roles, handoffs, conversation patterns.

### Key differences

* **Problem domain**: CrewAI/AutoGen answer *who does what in what order*. AURA answers *what crossed the perimeter and was it allowed*.
* **Tools**: Crew agents often use ad-hoc Python tools. AURA does not supply tools; it governs tool **intents** at egress (confirm-before-send, allow/deny lists in v0.1).
* **Complementary**: Same pattern as Skillware — orchestrator inside, AURA outside.

---

## 4. AURA vs. LangSmith, Phoenix, and tracing tools

[LangSmith](https://www.langchain.com/langsmith), [Arize Phoenix](https://github.com/Arize-ai/phoenix), and similar products focus on **LLM observability** — traces, spans, evals, prompt debugging.

### Key differences

* **Observe vs. enforce**: Tracers record what happened; they rarely **block** an action before execution. AURA's constitution and constraint engine enforce **policy at the boundary** on wired egress paths (broader intercept on roadmap).
* **Scope**: Tracing tools center on model calls and chains. AURA's audit trail is **agent-run scoped** — tools, approvals, violations, session lifecycle — not only tokens.
* **Complementary**: Export audit JSONL to OTel ([outputs.md](outputs.md)) or ingest into LangSmith later ([ROADMAP](ROADMAP.md)).

---

## 5. AURA vs. eval harnesses (DeepEval, RAGAS, OpenAI Evals)

[DeepEval](https://github.com/confident-ai/deepeval), [RAGAS](https://github.com/explodinggradients/ragas), and batch eval frameworks measure **quality on datasets** — faithfulness, relevance, pass@k.

### Key differences

* **When**: Eval harnesses run **offline** on test cases. AURA runs **inline** on production or dev sessions.
* **Output**: Eval scores and metrics vs. **causal audit trail + audit report + conformance summary**.
* **Purpose**: Eval answers "how good is the model?" AURA answers "what did this agent do, under which rules, with what provenance?"
* **Complementary**: Session exports can **feed** eval pipelines later; AURA is not a replacement for RAGAS.

---

## 6. AURA vs. Model Context Protocol (MCP)

[MCP](https://modelcontextprotocol.io) standardizes **tool transport** — client-server JSON-RPC for capabilities.

### Key differences

* **Layer**: MCP connects models to tools. AURA wraps the **whole run** — ingress, cavity, egress, audit sink.
* **Complementary**: MCP server inside the cavity; AURA can gate MCP tool calls at egress as adapter matures.

---

## 7. AURA vs. OpenTelemetry / generic logging

OpenTelemetry and structured logging provide **telemetry primitives** — spans, metrics, logs.

### Key differences

* **Agent semantics**: AURA events carry **agent identity**, session mode, constitution violations, and conformance — not generic spans alone.
* **Policy**: Logging does not enforce confirm-before-action or token budgets; AURA constraints do (v0.1 on explicit events; membrane intercept roadmap).
* **Complementary**: OTel exporter shipped (v0.3); audit trail maps to spans ([outputs.md](outputs.md), [ROADMAP](ROADMAP.md)).

---

## Two jobs AURA always targets

Regardless of competitor category:

| Job | Meaning |
| :--- | :--- |
| **Conformance** | Did the run stay within declared rules? (constraints, gates, sequencer steps) |
| **Auditability** | Full causal record from session open to close — replayable export with integrity checks |

Orchestrators optimize for **task completion**. Eval harnesses optimize for **quality scores**. Prompt-heavy harnesses optimize for **better instructions and reviewer loops**. AURA optimizes for **accountable execution** — mechanical boundaries and a receipt, not hope that the model understood "done."

---

## Executive summary matrix

| Feature | AURA Harness | DeepSeek Harness | LangGraph | CrewAI / AutoGen | LangSmith / tracing | DeepEval / RAGAS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary goal** | **Runtime membrane — audit & policy** | Composable agent runtime | Stateful agent graphs | Multi-agent orchestration | LLM observability | Offline quality eval |
| **Architecture** | **Sidecar / wrapper** | Plugin-based runtime | Graph framework | Agent workflow framework | SaaS / SDK tracing | Test harness |
| **Build inside it** | **No** | Yes | Yes | Yes | Instrument only | N/A |
| **Black-box agent OK** | **Yes (target)** | Partial | No | No | Partial | N/A |
| **Live policy gate** | **Yes (constraints + gates + wired egress)** | Sandbox / approval | DIY in graph | DIY in tasks | No | No |
| **Session receipt / proof** | **Yes (audit report + hash chain)** | SessionEvent log | Via external tools | Via external tools | Traces | Post-hoc |
| **Causal audit trail** | **Yes (native JSONL)** | Yes (SessionEvent) | Via external tools | Via external tools | Traces | Post-hoc |
| **Framework lock-in** | **None (intent)** | DSH ecosystem | LangChain stack | Crew/AutoGen APIs | Vendor optional | Eval library |
| **Best for** | Provenance, compliance, configure-the-membrane | Greenfield DSH apps | Graph workflows | Role-based multi-agent | Debug LLM apps | Benchmark RAG/agents |

---

## Where AURA is today (v0.3.2)

Honest scope — membrane, sequencer, and identity/audit layers shipped; full zero-intrusion wiring on every transport still growing:

| Shipped (through v0.3) | Roadmap |
| :--- | :--- |
| Agent registry, sessions, SDK `emit()` | LangGraph / MCP auto-probe |
| Constraint engine on events | Full I/O normalizer for arbitrary transports |
| Audit trail (JSONL) + session export + **audit report** | Signed audit packs |
| **Hash chain** on spine events + compare CLI | Network/shell intercept without host cooperation |
| **`agent_ref` (ULID)** + policy version on export | Skill manifest rule merge at bind |
| **Ingress** event + context normalization | Branching / parallel sequencer steps |
| **Egress** `guarded_tool_call` (Skillware host + mocks) | Broader egress adapters |
| **Sequencer** — linear steps, gates, retries | Named observer presets (monitor, break, limit) |
| **Observers** — parallel spine subscribers | Webhooks, enterprise sinks |
| **OTel exporter** | HTTP fleet API |

The **doctrine** is membrane-first: configure gates, rules, and export invariants at the boundary; keep the cavity a black box. v0.3 adds the **receipt** layer (audit report + integrity chain); v0.2 delivered the first egress path via Skillware/mock hosts per [skillware-integration.md](skillware-integration.md) and [sequencer.md](sequencer.md).

---

## Related ARPA projects

| Project | Relationship to AURA |
| :--- | :--- |
| [Skillware](https://github.com/arpahls/skillware) | Tools **inside** the cavity |
| [Rooms](https://github.com/arpahls/rooms) | Environment **outside** — optional export bridge |
| [Legacy Protocol](https://github.com/arpahls/legacy-protocol) | Long-term audit / continuity sink |

→ [getting-started.md](getting-started.md) · [stack-position.md](stack-position.md)
