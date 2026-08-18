# AURA Harness — Inputs, Spectrum & Output Model

*Direction draft 2 — extends [direction-draft.md](direction-draft.md)*

*Draft for discussion. Not a spec or implementation plan.*

*By ARPA Hellenic Logical Systems — [arpacorp.net](https://arpacorp.net)*

---

## 1. Core Reframe: Inputs → Process → Outputs

From [direction-draft.md](direction-draft.md), AURA is a **coat around the loop**, not the loop itself. Draft 2 adds a product-shaped framing:

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUTS (anything, from anywhere)                               │
│  brain · identity · skills · memory · runtime · soma · config   │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  PROCESS — AURA Spectrum + field services                       │
│  guardrails · levels · hooks · monitor · limit · break · …      │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  OUTPUTS (always normalized)                                    │
│  AuraEvent stream · audit · analytics · exports · API · Legacy  │
└─────────────────────────────────────────────────────────────────┘
```

**The promise:** throw what you have in → tune the **Aura Spectrum** → get the same class of output every time, regardless of whether the brain is Gemini, Claude, Ollama, or a custom framework.

This is how AURA stays **native to ARPA** and **broad enough for any loop**.

---

## 2. The Slot Model

AURA does not own brain, skills, or identity. It **declares slots** — typed attachment points — and **adapters** that normalize foreign stacks into an internal **Run Context**.

### Slot overview

| Slot | Required? | If empty / omitted | ARPA-native default | Universal fallback |
|---|---|---|---|---|
| **Brain** | Yes (something must think) | Error — no run | Logical Systems profile from SoulSig | Declared provider + endpoint (OpenAI, Claude, Ollama, custom) |
| **Identity** | No | Auto `session_id` (ephemeral) | Live ID + sub Live ID + UBH | Custom label (`"george"`) or external ID API |
| **Soul / Birth** | No | No constitution; spectrum-only governance | SoulSig bundle auto-loaded | Manual guardrails in config |
| **Skills** | No | Loop runs with whatever tools it already has | Skillware (deep audit, schemas, training export) | LangChain tools, MCP, custom functions, mem0 actions, etc. |
| **Memory** | No | Harness does not manage long-term memory | MnemoLink matrix | mem0, vector DB, file, none |
| **Runtime / Soma** | Implicit | AURA infers host (process, container, script path) | Soma metadata from SoulSig | User-declared host descriptor |
| **Spectrum** | Partial defaults | Minimal monitor + audit | Full SoulSig + AURA Level profile | User-defined YAML/API params |

### Why a Brain slot matters (and why treat models differently)

Logical Systems are not interchangeable in practice — only in marketing. AURA should **know** where thinking comes from and **adapt policy** accordingly:

| Brain class | Examples | Why AURA might treat differently |
|---|---|---|
| **Cloud API** | Gemini, Claude, GPT | Rate limits, cost telemetry, data residency, prompt-injection surface via API |
| **Local / edge** | Ollama, llama.cpp, vLLM | No egress by default; different latency profile; may allow higher tool autonomy |
| **Framework-hosted** | LangGraph agent, dsh loop | Intercept via adapter hooks, not raw HTTP |
| **Custom / opaque** | Fine-tuned, proprietary | Conservative defaults; richer logging; human approval bias |

**This is not favoritism.** It is **provider-aware governance**: the same AURA Level may mean different enforcement (e.g. Full on local Ollama vs Mid on cloud API with PII). The Brain slot exposes **capabilities + constraints** to the Spectrum engine.

```
Brain Adapter reports:
  provider, model_id, context_window, streaming, tool_native,
  data_residency, cost_per_token_estimate, injection_risk_tier
        ↓
Spectrum engine adjusts: limits, approval gates, logging granularity
```

---

## 3. Identity: Live ID vs Session ID vs SoulSig

Three different time horizons — do not collapse them:

| Concept | Lifetime | What it identifies | ARPA path | BYO path |
|---|---|---|---|---|
| **Live ID** | Permanent | Accountable human / org (UBH) | `arpalive.id` registration, 2FA, agreement | External org ID or none |
| **Agent ID** | Permanent (for that agent) | The logical system as entity | Sub Live ID + SoulSig | Custom `"george"` or UUID you assign |
| **Session ID** | Runtime loop | This run, this host, this chapter | Auto per Soma activation | Auto-generated if omitted |
| **SoulSig** | Permanent on agent | Birth contract — constitution at creation | Signed between Live IDs | Not available without Live ID |

**Live ID ≠ Session ID.** Live ID is the garage and the owner. Session ID is the ignition key for one trip.

**If Identity slot is blank:** AURA generates `{session_id}` — unique, ephemeral, still fully auditable inside that run. No UBH, no Legacy persistence guarantee, no SoulSig trail. Acceptable for dev; not acceptable for production autonomy affecting others.

**If Identity slot is `"george"` (unverified):** Treated as **display identity** — logged, not trusted. Spectrum defaults lean conservative (Lower effective AURA Level, more audit, more break triggers).

---

## 4. Skills Slot: Skillware as Default, Not Gate

AURA wraps **any** skill surface:

| Skills source | Adapter | Audit depth | Training data export |
|---|---|---|---|
| **Skillware** | Native bridge | ★★★★★ — tool schema, step lineage, skill version | ★★★★★ |
| **MCP servers** | MCP adapter | ★★★★ — call/result/timing | ★★★ |
| **LangChain / LangGraph tools** | Framework adapter | ★★★★ | ★★★ |
| **Raw Python functions** | Introspection / wrapper | ★★★ | ★★ |
| **None (model-only)** | N/A | ★★ — model I/O only | ★ |

Skillware is **favorable**, not **mandatory** — same pattern as Brain: deepest integration when present, graceful degradation when not.

When Skillware is detected, AURA can correlate: `skill_id → tool_call → AuraEvent → Legacy chunk → optional training corpus`.

---

## 5. The Aura Spectrum

The **Spectrum** is the tunable field — predefined runtime behavior selected alongside inputs. Think of it as the harness **control surface**, not the agent prompt.

### Spectrum dimensions (draft)

| Dimension | What it controls | Examples |
|---|---|---|
| **AURA Level** | How much reality the agent may touch without approval | Low / Mid / High / Full |
| **Guardrails** | Hard limits (from SoulSig or manual) | blocked tools, paths, APIs, topics |
| **Services** | Which field services are active | monitor, audit, break, conserve, recover, … |
| **Hooks** | Interception depth | pre_turn, pre_tool, on_drift, turn_end |
| **Budgets** | Tokens, cost, time, tool calls per session | max 50k tokens, $2 cap, 30 min |
| **Output profile** | Export shape | `aura-json`, OTel, CSV, webhook, Legacy |
| **Recovery** | Retry, fallback, escalate | 3 retries → human queue |
| **Memory policy** | What harness remembers mid-run | compress after N steps, redact PII |

**Predefined spectra** ship as profiles — e.g. `dev`, `production`, `regulated`, `physical-device` — composable with SoulSig or API overrides.

```
SoulSig birth bundle  ──┐
Manual API config     ──┼──►  Spectrum Resolver  ──►  Active Run Context
Environment / host    ──┘
```

---

## 6. Outputs: Always the Same Shape

Regardless of inputs, AURA **normalizes** output into a stable envelope others can build on:

### AuraOutput layers

| Layer | Contents | Consumers |
|---|---|---|
| **AuraEvent stream** | Append-only causal log (turn, step, tool, correction, …) | Replay, debug, compliance |
| **Session summary** | Aggregates: cost, duration, outcome, anomalies | Dashboards, ERP |
| **Audit pack** | Signed bundle: identity refs, constitution hash, full trail | Legal, UBH review |
| **Analytics slice** | Structured metrics for training / improvement | Skillware, internal ML |
| **Export adapters** | JSON, CSV, OTel spans, webhook POST, DB sink | Customer infra |

**Key principle:** ChatGPT brain + mem0 + LangChain and Claude + Skillware + SoulSig both emit **compatible AuraEvent schemas**. Downstream apps do not re-parse vendor formats.

---

## 7. Two Paths: ARPA-Native vs Bring-Your-Own

Your instinct to offer both is correct. **Do not require Live ID for the harness to exist.** Require it only for **full ARPA guarantees**.

### Path A — ARPA Live ID (accountable autonomy)

```
Human registers Live ID (arpalive.id)
        │
        ▼
Creates agent → SoulSig birth
  "X created agent Y at T with brain Z, skills S, goals G, restrictions R"
        │
        ▼
SoulSig bundle auto-formats → AURA Harness inputs
  (Live ID, sub Live ID, brain profile, spectrum, Skillware ref, …)
        │
        ▼
AURA wraps Soma → runs → outputs
        │
        ▼
Results + audit tied to Live ID → sessions listed under agent → Legacy-eligible
```

**What the user gets without thinking about slots:** model, identity, session, guardrails, audit destination — populated from SoulSig.

**What ARPA gets:** UBH chain, legal standing, continuity, genomics graph, upgrade path across stack.

### Path B — BYO API (universal wrap)

```
User calls AURA API / SDK with explicit parameters:
  brain: { provider: openai, model: gpt-4o }
  identity: { label: "george" }          # optional
  skills: { type: langchain, … }
  memory: { type: mem0, … }
  spectrum: { level: mid, services: [audit, limit, break], output: csv }
        │
        ▼
AURA wraps whatever loop → normalized output
        │
        ▼
User sinks to own DB / cloud / API — raw, CSV, webhook
```

**What the user gets:** governance coat without ARPA account overhead.

**What ARPA does not guarantee:** verified UBH, SoulSig constitution, Legacy inheritance, Live ID genomics.

### Comparison

| | Path A — Live ID + SoulSig | Path B — BYO API |
|---|---|---|
| **Setup friction** | Higher (registration, agreement) | Low (API key, docs) |
| **Identity trust** | Verified UBH | Self-declared or ephemeral |
| **Auto-population** | SoulSig → slots filled | Manual / partial |
| **Audit persistence** | Live ID + Legacy path | User-owned storage |
| **AURA Level enforcement** | Contractual + technical | Technical only |
| **Skillware depth** | Full | Available, not assumed |
| **Best for** | Production agents, regulated, physical | Dev, migration, existing stacks |
| **Upgrade path** | Already native | Bind Live ID later → migrate agent to SoulSig |

**Recommendation:** Path B is the **on-ramp**. Path A is the **destination** for anything that touches money, people, or infrastructure. Same harness binary; different **trust tier** and **output retention policy**.

---

## 8. Worked Examples

### Example 1 — BYO stack (your ChatGPT + LangChain + mem0 + "george")

**Inputs:**

```yaml
brain:
  provider: openai
  model: gpt-4o
runtime:
  framework: langchain
  loop: agent_executor
skills:
  adapter: langchain_tools
  tools: [web_search, calculator]
memory:
  adapter: mem0
identity:
  label: george          # unverified
spectrum:
  level: mid
  services: [monitor, audit, limit, break, conserve]
  output: [aura-json, csv]
session:                 # omitted → auto-generated
  # → aura_sess_8f3a2c...
```

**Process:** Brain adapter tags OpenAI cloud tier → Spectrum applies API-appropriate limits → hooks wrap LangChain tool calls → mem0 reads/writes logged as memory events.

**Outputs:** `aura_sess_8f3a2c` event stream + CSV summary → user's S3 bucket. No Live ID record. `"george"` appears in logs as display name only.

---

### Example 2 — ARPA-native agent

**Inputs:** SoulSig bundle (auto — user clicked "Create agent" in Live ID console)

```yaml
# Populated by SoulSig — user does not hand-write this
live_id: live_human_abc
agent_id: live_agent_xyz
soulsig: sig_2026_04_01T120000Z
ubh: live_human_abc
brain:
  profile: logical_systems/claude-sonnet-prod
skills:
  adapter: skillware
  bundle: [research-v2, code-exec-v1]
memory:
  adapter: mnemolink
  matrix: persona_analyst_v3
spectrum:
  level: high
  constitution_hash: sha256:…
  services: [all]
  output: [aura-json, legacy-stream, otel]
soma:
  host: cloud-worker-07
session:               # new on each activation
  # → aura_sess_9d1b4e...
```

**Process:** Full constitution loaded → Skillware calls get skill-level lineage → MnemoLink policy governs compression → Legacy stream receives signed chunks → Rooms session ID linked if in collaboration.

**Outputs:** Everything under `live_agent_xyz` in Live ID console; session `9d1b4e` nested; Legacy-eligible; UBH attributable.

---

## 9. Analysis: Is This a Good Idea?

### What works strongly

| Idea | Verdict | Why |
|---|---|---|
| **Input slots + adapters** | ✅ Strong | Matches dsh seams + ARPA "wrap any loop" — implementable, market-aligned |
| **Aura Spectrum as control plane** | ✅ Strong | Separates governance from agent prompt — unique vs competitors |
| **Normalized output always** | ✅ Strong | ERP/DB/API story; training data pipeline; Legacy feed |
| **Optional identity with auto session** | ✅ Strong | Lowers BYO friction; clear upgrade to Live ID |
| **Skillware as default, not gate** | ✅ Strong | Adoption funnel — don't block foreign tools |
| **Brain-aware policy** | ✅ Strong | Practical (cost, residency, injection) — not marketing |
| **Two paths (Live ID vs API)** | ✅ Strong | Revenue + openness; same codebase |

### Risks and mitigations

| Risk | Mitigation |
|---|---|
| Slot explosion (100 adapters) | Tier 1: Python SDK, LangGraph, dsh, MCP, Skillware. Tier 2: community adapters |
| `"george"` identity abused | Mark unverified; cap AURA Level; watermark exports |
| SoulSig auto-format becomes magic black box | Publish open **SoulSig → AURA input** schema; BYO can mimic subset |
| reference.md says "AURA requires Live ID" | Reframe: **accountable AURA** requires Live ID; **universal AURA** does not |
| Output schema churn | Version `AuraEvent v1`; breaking changes only major versions |
| Users expect AURA to fix bad loops | Document: coat governs and records; does not replace reasoning |

### Live ID as gate for all AURA?

**Not recommended as sole path.** Your BYO example is the adoption wedge. Live ID as **required** should apply only to:

- AURA Levels above Mid affecting external systems
- Legacy persistence guarantees
- Physical / financial Soma classes
- ARPA-hosted Rooms with liability

Otherwise you compete with dsh on "must sign up first" — and lose.

---

## 10. Combined Architecture (Draft 1 + Draft 2)

```
                    ┌──────────────────────────────────────┐
                    │         INPUT SLOTS (adapters)        │
                    │  Brain · Identity · Skills · Memory   │
                    │  Runtime/Soma · SoulSig (optional)    │
                    └──────────────────┬───────────────────┘
                                       │
                    ┌──────────────────▼───────────────────┐
                    │      RUN CONTEXT (normalized)         │
                    │  provider traits · trust tier · ids   │
                    └──────────────────┬───────────────────┘
                                       │
         ┌─────────────────────────────▼─────────────────────────────┐
         │                    AURA SPECTRUM                           │
         │  Level · guardrails · services · hooks · budgets · output  │
         └─────────────────────────────┬─────────────────────────────┘
                                       │
              ┌────────────────────────▼────────────────────────┐
              │  ADAPTER RING (hooks on loop)                    │
              │  pre_turn · pre_tool · on_drift · turn_end · …    │
              └────────────────────────┬────────────────────────┘
                                       │
              ┌────────────────────────▼────────────────────────┐
              │  FIELD SERVICES (parallel)                       │
              │  monitor · audit · break · conserve · recover · … │
              └────────────────────────┬────────────────────────┘
                                       │
                    ┌──────────────────▼───────────────────┐
                    │     AuraEvent stream (append-only)    │
                    └──────────────────┬───────────────────┘
                                       │
                    ┌──────────────────▼───────────────────┐
                    │  OUTPUT ADAPTERS                      │
                    │  JSON · OTel · CSV · webhook · Legacy │
                    └──────────────────────────────────────┘
```

---

## 11. Decision Matrix — What to Build First

| Priority | Component | Path A | Path B | Notes |
|:---:|---|:---:|:---:|---|
| P0 | AuraEvent schema v1 | ✓ | ✓ | Foundation for everything |
| P0 | Spectrum resolver (levels + services) | ✓ | ✓ | Product control surface |
| P0 | Auto session_id | ✓ | ✓ | Identity slot default |
| P1 | Brain adapter interface | ✓ | ✓ | Claude / OpenAI / Ollama first |
| P1 | Python loop `@aura.wrap` | ✓ | ✓ | Universal on-ramp |
| P1 | Output exporters (JSON, CSV, webhook) | ✓ | ✓ | BYO promise |
| P2 | Skillware bridge | ✓ | partial | Depth when present |
| P2 | SoulSig → input auto-loader | ✓ | — | Path A magic |
| P2 | Live ID session registry | ✓ | — | Results under agent |
| P3 | LangGraph / dsh adapters | partial | ✓ | Ecosystem |
| P3 | MnemoLink / mem0 memory adapters | ✓ | ✓ | Memory slot |
| P4 | Legacy stream signer | ✓ | — | Continuity |

---

## 12. Open Questions (Draft 2)

1. **SoulSig bundle format** — JSON? Signed JWT? Separate ARPA spec repo?
2. **Trust tiers** — Formal enum: `ephemeral`, `unverified`, `verified_live_id`?
3. **Session nesting** — Can one session fork into child sessions (dsh-style) under same agent?
4. **Spectrum presets** — Ship with harness or with SoulSig templates?
5. **BYO output retention** — Does ARPA store anything for Path B, or strictly pass-through?
6. **Brain slot and Synapuls** — Does injection scanning live in Brain adapter or Spectrum?

---

## 13. Summary Position

AURA Harness should be built as an **input-agnostic governance transformer**:

- **Slots** accept any brain, skills, identity, memory, runtime
- **Spectrum** configures how hard the coat presses during this run
- **Outputs** always speak AuraEvent — portable to ERP, DB, API, Legacy

**Live ID + SoulSig** is not a prerequisite to *use* AURA. It is the prerequisite to **trust** AURA with autonomy that binds a human, persists beyond a session, and inherits through Legacy.

That keeps ARPA native **and** market-wide — the same move DeepSeek made with plugins, but with accountability and continuity as the ARPA-shaped output no one else standardizes.

---

## See Also

- [direction-draft.md](direction-draft.md) — market comparison, three-ring model, phased roadmap
- [readme.md](readme.md) — current narrative spec
- [../reference.md](../reference.md) — stack definitions (may need Live ID requirement softening)
- [../manifesto/readme.md](../manifesto/readme.md) — architecture diagram

---

*Draft 2 · ARPA Hellenic Logical Systems · [arpacorp.net](https://arpacorp.net)*
