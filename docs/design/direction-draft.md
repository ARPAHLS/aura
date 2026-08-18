# AURA Harness — Strategic Analysis & Direction

*Draft for discussion. Not a spec or implementation plan.*

*By ARPA Hellenic Logical Systems — [arpacorp.net](https://arpacorp.net)*

---

## 1. The Ontology Question: Coat, Runtime, or Both?

The ARPA narrative already answers this better than most of the industry:

| Layer | What it is | Analogy |
|---|---|---|
| **Soma** | Whatever hosts the run — script, robot, cloud loop | Body |
| **Loop** | Reason → act → observe → repeat (inside Soma) | Motor cortex + reflex |
| **AURA** | Field **around** the loop while it runs | Aura / harness / governor |
| **Skillware** | Capabilities the loop can invoke | Nervous system |
| **Logical Systems** | Swappable brain | Rented nous |

**AURA is not the loop.** It is the **governed runtime envelope** that makes any loop production-viable: observable, bounded, recoverable, accountable.

Industry blurs this. DeepSeek Harness, LangChain Deep Agents, Claude Code — they ship **loop + tools + UI + persistence** as one product and call the whole thing a "harness." ARPA should **not** compete on that axis. Compete on:

> **Any loop, any body, any brain — but every run is wrapped, signed, tiered, and traceable.**

That matches the stack diagram: Soma → Aura → Rooms + Continuity. The harness is the **projection layer** between the body and the world.

---

## 2. What the Market Is Building (and Why)

### DeepSeek Harness (`dsh`) — The New Reference

**Philosophy:** *Everything is a plugin* (Cordis meta-framework).

**Architecture highlights:**

- **Append-only `SessionEvent` log** — source of truth; "model-visible = logged" is a runtime invariant
- **Typed event seams** — `agent/pre-step`, `tools/pre-execute`, `tools/post-execute`, `agent/turn-stopping` with waterfall/serial dispatch for interception
- **Profiles & bundles** — composable plugin trees at boot (`dsh-base`, web, headless)
- **Capability seams** — swappable LLM, tools, FS, shell, sandbox, subagents without forking core
- **Turn/step model** — durable turns, fork/resume, replay from log
- **Sandbox + approval policy** in base layer
- **Developer preview** — breaking changes expected

**Direction:** Composability and replaceability first. Governance exists (sandbox, approval, tool pipeline waterfalls) but **no identity chain, no UBH, no tiered autonomy contract, no cross-host soul continuity**.

**What to learn:** Event interception model, append-only causal log, plugin composition without privileged core.

**What not to copy:** Becoming a full agent OS with bundled UI, model adapters, and loop ownership — that fights ARPA's "brains are rented" principle and duplicates Skillware/Rooms territory.

**References:**

- [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)
- [Architecture docs](https://deepseek-harness.github.io/deepseek-harness/en/reference/)
- [Cordis primer](https://deepseek-harness.github.io/deepseek-harness/en/reference/cordis-primer)

---

### LangGraph + LangChain Stack

| Piece | Role |
|---|---|
| **LangGraph** | Graph **runtime** — checkpoints, interrupts, durable threads |
| **LangChain `create_agent`** | Minimal harness on top of LangGraph |
| **Deep Agents** | Opinionated harness — context mgmt, subagents, long-horizon defaults |

**Strengths:** Production durability, HITL, explicit state, LangSmith traces, OTel alignment.

**Gaps for ARPA:** No identity birth contract, no permission tiers, no multi-Soma soul graph, graph-centric (harder to wrap foreign loops).

---

### OpenAI Agents SDK

Lightweight loop + guardrails + built-in tracing. Fast path for OpenAI stack. Provider-bound; governance is guardrail-shaped, not constitutional.

---

### Microsoft Agent Framework / AutoGen Successor

Enterprise workflows, OTel GenAI semconv, Azure Foundry guardrails (PII, injection). Strong for .NET/Azure shops. Same gap: **accountability primitives are org-level, not agent-birth-level**.

---

### AWS Strands, Pydantic AI, etc.

Model-driven loops with OTel tracing, typed tools, execution limits. Good **local loop hygiene**; weak on **cross-system continuity and legal binding**.

---

### Observability Layer (OTel + Langfuse + Phoenix)

Industry converging on **OpenTelemetry GenAI semantic conventions** as the flight recorder. Traces capture model spans, tool spans, session IDs.

**Gap:** Traces explain *what happened*; they don't explain *who is liable*, *what tier was authorized*, or *what constitution was in force* — unless you bolt that on (ARPA's job).

---

## 3. ARPA's Dual Mandate

Two modes that feel like one product:

### A. ARPA-Native (Full Stack)

When Live ID → SoulSig → Soma → AURA → Skillware → Rooms → MnemoLink → Legacy are present:

- Guardrails **compiled from SoulSig** at birth
- Skills **audited through Skillware** with harness correlation IDs
- Sessions **bound to Rooms** with multi-species context
- Memory **governed by MnemoLink** policies (what to keep/compress/forget)
- Audit **streams to Legacy** with UBH attribution
- **AURA Levels** enforced as hard permission contract, not prompt suggestion
- **Synapuls** hooks at surface (injection, file, API, future BCI)

### B. Universal Wrap (Foreign Loops)

When someone brings LangGraph, a Python while-loop, Cursor agent, dsh plugin tree, or a fridge firmware loop:

- AURA attaches via **adapters**, not rewrite
- Core services still run: monitor, audit, track, limit, safeguard, break, recover
- Identity may be **external** (API key, org ID) until Live ID is adopted — but events are still structured for later SoulSig binding
- Skillware/Rooms/Legacy integrate **opportunistically** when detected

**Design rule:** Native mode is strict; universal mode is permissive but never silent (always logs, always bounds something).

---

## 4. How the Coat Actually Intercepts (Technical Model)

Three rings, not one monolith:

```
┌─────────────────────────────────────────────────────────┐
│  ENVELOPE — Identity, SoulSig context, Legacy export    │
│  ┌───────────────────────────────────────────────────┐  │
│  │  FIELD — Parallel services (monitor, limit, …)    │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  ADAPTER — Hooks on the loop (the Soma)     │  │  │
│  │  │     [ Brain → tool → result → … ]           │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Adapter Hooks (Inspired by dsh, Generalized)

| Hook | When | AURA Can |
|---|---|---|
| `pre_turn` | Before model sees input | Strip injection, inject constitution, reject |
| `pre_step` | Before each reasoning step | Scope check, budget check, level check |
| `pre_tool` | Before tool execution | Sandbox, approve, rewrite args, block |
| `post_tool` | After tool result | Validate output, redact, log causal link |
| `on_drift` | Loop anomaly detected | Break, correct via prompt, escalate to human |
| `on_error` | Failure | Recover, retry policy, fallback path |
| `turn_end` | Step/turn complete | Compress memory, emit Legacy chunk, Rooms broadcast |

**Parallel field services** run continuously (monitor, audit, track, limit, safeguard, wake, break, conserve, recover, remember, learn, attach) — they consume the same **AuraEvent stream**, not the loop directly.

### The Event Stream (Non-Negotiable)

One **append-only, signed, timestamped** log per run:

- Identity token + SoulSig ref + Soma ref + AURA Level
- Every model call, tool call, directory touch, API call, correction, human override
- **Causal IDs** linking reasoning → action → outcome
- OTel-compatible export **plus** ARPA extensions (UBH, tier, constitution hash)

This is how you answer "what did it do last night and why?" without vendor lock-in.

---

## 5. Comparison Matrices

### Matrix A — Architectural Stance

| System | Owns the loop? | Plugin/composable | Durable event log | Interception hooks | Identity/accountability | Tiered autonomy |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **DeepSeek Harness** | Yes (default loop is a plugin) | ★★★★★ | ★★★★★ | ★★★★★ | ★ | ★★ |
| **LangGraph** | Yes (you define graph) | ★★★ | ★★★★★ (checkpoints) | ★★★★ | ★ | ★★★ (interrupts) |
| **OpenAI Agents SDK** | Yes | ★★ | ★★★ | ★★★ | ★ | ★★ |
| **MS Agent Framework** | Yes | ★★★ | ★★★★ | ★★★ | ★★ | ★★★ |
| **ARPA AURA (proposed)** | **No** (wraps any) | ★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ |

### Matrix B — Capability Coverage vs ARPA Narrative

| Capability | DeepSeek | LangGraph | ARPA Today (Spec) | ARPA Should Build |
|---|---|---|---|---|
| Real-time loop correction | Via events | Via interrupts | Narrated | **Yes — core** |
| Prompt injection at boundary | Partial (sandbox) | Partial | Narrated | **Yes — Synapuls surface** |
| Full audit trail | Session log | Traces/checkpoints | Narrated | **Yes — AuraEvent + Legacy** |
| Token/cost conservation | Telemetry | External | Conserve service | **Yes** |
| Runaway loop break | turn-stopping | Graph limits | Break service | **Yes** |
| Wake/resume | fork/resume | thread_id | Wake service | **Yes** |
| Multi-agent / Rooms | Subagents | Multi-agent graphs | Rooms separate | **Integrate via adapter** |
| Skills marketplace | Plugin tools | Tools | Skillware | **Native Skillware bridge** |
| Cross-host continuity | Session fork | Checkpoints | SoulSig/Legacy | **Differentiator** |
| Legal UBH binding | ✗ | ✗ | Live ID narrative | **Differentiator** |
| Biosecurity / thought security | ✗ | ✗ | Synapuls narrative | **Future seam** |
| Works on foreign loops | ✗ (must use dsh) | ✗ | Implied | **Explicit adapters** |

### Matrix C — Build vs Integrate vs Ignore

| Area | Verdict | Rationale |
|---|---|---|
| Own the agent loop | **Don't** | Brains rented; Skillware/Rooms own orchestration patterns |
| Append-only event log | **Build** | Non-negotiable for audit; align with OTel GenAI semconv |
| Plugin system | **Integrate pattern** | Cordis-style events/adapters, not full Cordis fork |
| Web UI | **Don't (v1)** | dsh/LangSmith win here; ship CLI + API + log viewer later |
| Model adapters | **Don't** | Proxy/wrap existing providers |
| Sandbox execution | **Integrate** | Wrap Firecracker, E2B, local subprocess policy |
| AURA Levels | **Build** | Unique; no market equivalent |
| SoulSig binding | **Build** | Native ARPA; optional in universal mode |
| Legacy export | **Build** | Continuity is the point of the stack |
| dsh plugin | **Build adapter** | `dsh-aura` plugin listening to `tools/*`, `agent/*` |
| LangGraph middleware | **Build adapter** | Node wrapper / checkpointer decorator |
| Plain Python loop | **Build SDK** | `@aura.wrap` decorator / context manager |

### Matrix D — What Others Will Do in 12–24 Months (AURA Should Be Ready)

| Trend | Industry Move | AURA Opportunity |
|---|---|---|
| Agent = model + harness | DeepSeek, LangChain doubling down | Be the **governance harness** that sits *under* or *around* theirs |
| OTel GenAI standard | Everyone emits similar spans | Extend schema with identity/tier/constitution |
| Prompt injection arms race | Model-level defenses | **Surface-level** harness filter before model sees bytes |
| Multi-agent swarms | Rooms/orchestrators explode | Aura per agent + **room-level** aggregate audit |
| Physical agents (robots, edge) | Soma diversifies | Host metadata in every event (device, location, firmware) |
| Agent inheritance / death | Barely discussed | **Legacy Protocol** integration — ARPA moat |
| Regulatory pressure (EU AI Act, etc.) | Audit + human oversight | UBH + AURA Levels map cleanly to compliance |
| BCI / bio interfaces | Synapuls territory | Harness as **thought IO gate** before it hits loop |

---

## 6. Proposed Direction for `AURA_Harness` Repo

### Positioning (One Sentence)

**AURA Harness is an identity-aware runtime coat that wraps any agent loop — enforcing tiered autonomy, producing causal audit trails, and projecting governed operation into Rooms and Legacy.**

### Core Design Principles

1. **Wrap, don't replace** — loop stays in Soma; AURA is adjacent
2. **Events before features** — AuraEvent schema first; services consume it
3. **Native when present, useful when absent** — degrade gracefully without Live ID
4. **Intercept at seams** — pre/post hooks, not prompt-only guardrails
5. **Parallel field** — monitor/limit/break don't block the hot path
6. **Export everything** — OTel + ARPA extensions + Legacy chunks

### Suggested Repo Structure (Future, Not Now)

```
aura-harness/
├── spec/           # AuraEvent schema, AURA Levels, hook contract
├── core/           # Event log, field services, level enforcement
├── adapters/
│   ├── python/     # @wrap, sidecar
│   ├── langgraph/
│   ├── dsh/        # Cordis plugin
│   └── generic/    # HTTP proxy for tool calls
├── bridges/
│   ├── skillware/
│   ├── rooms/
│   ├── liveid/     # SoulSig loader
│   └── legacy/     # Continuity export
└── docs/
```

### Phased Roadmap (Discussion)

| Phase | Focus | Outcome |
|---|---|---|
| **0 — Spec** | AuraEvent + hook API + AURA Levels formalized | Interop document other ARPA repos can target |
| **1 — Universal SDK** | Python wrap on any loop; append-only log; limit/break/audit | Works without full ARPA stack |
| **2 — ARPA bridges** | Skillware tool correlation, Rooms session ID, SoulSig constitution load | Native mode |
| **3 — Adapters** | dsh plugin, LangGraph middleware | "Bring your loop" |
| **4 — Legacy stream** | Signed export, replay, "what happened last night" UI | Continuity path complete |
| **5 — Synapuls surface** | Injection/file/API gates | Security layer |

---

## 7. Answers to Specific Questions

**"Uses runtime or includes runtime or is runtime?"**

AURA **is** the governed runtime **envelope** for a hosted Soma — not the reasoning loop itself. It **includes** scheduling, logging, enforcement, and recovery **services** that run alongside the loop. Say: *"AURA is runtime governance; the loop is guest code inside the coat."*

**"How can it get any kind of inputs…?"**

Through **adapters** at standardized hooks + a unified **AuraEvent** ingest (stdout parser, OTel span receiver, dsh session/event subscriber, direct SDK calls). Everything normalizes to one log.

**"Correct with a prompt if wrong?"**

Yes — `on_drift` / `agent/pre-step` style interception: inject correction, truncate context, or reject step. Same mechanism as dsh waterfalls, but **constitution-aware** (SoulSig rules) and **level-aware** (Mid can self-correct; Low must escalate).

**"Protect from malicious file / injection at harness level?"**

Yes — **before** `pre_turn`: sanitize files, strip injection patterns, enforce Synapuls policy. Model never sees raw hostile input if harness blocks it.

**"Trace last night — reasoning, tools, timestamps, directories, APIs?"**

AuraEvent log + Legacy projection. Causal graph: turn → step → tool → filesystem/API → result, each signed and UBH-attributed.

---

## 8. Recommended Strategic Bet

| Do | Don't |
|---|---|
| Event-sourced governance wrap | Full agent OS competing with dsh |
| AURA Levels as enforceable contract | Autonomy as prompt text |
| Adapters for top 3 runtimes (plain Python, LangGraph, dsh) | 20 frameworks day one |
| OTel-compatible + ARPA extensions | Proprietary trace silo |
| Tight Skillware/Rooms/Legacy bridges | Monolithic all-in-one repo |
| Spec-first open repo | Code before schema |

**The wedge:** DeepSeek proves the market wants **composable harness infrastructure**. ARPA's wedge is **composable harness infrastructure that knows who was born, who is liable, how much reality they may touch, and what survives when the host dies.**

---

## 9. Open Decisions (For Next Session)

1. **Strictness of universal mode** — Can unauthenticated loops run under AURA at all, or read-only audit only?
2. **dsh relationship** — First-class plugin vs parallel project vs "inspired by"?
3. **Where Synapuls lives in v1** — Inside AURA repo or separate bridge?
4. **Legacy export format** — Append to SoulSig trail vs separate Legacy Protocol stream?
5. **AURA Level enforcement** — In-process only, or network gate for physical/API actions?

---

## See Also

- [readme.md](readme.md) — current AURA Harness narrative spec
- [../reference.md](../reference.md) — stack definitions
- [../manifesto/readme.md](../manifesto/readme.md) — architecture diagram
- [../graph.md](../graph.md) — dependency graphs

---

*Draft · ARPA Hellenic Logical Systems · [arpacorp.net](https://arpacorp.net)*
