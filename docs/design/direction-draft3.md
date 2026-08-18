# AURA Harness — Extensible Type System & Conformance Model

*Direction draft 3 — extends [direction-draft.md](direction-draft.md) and [direction-draft2.md](direction-draft2.md)*

*Draft for discussion. Not a spec or implementation plan.*

*By ARPA Hellenic Logical Systems — [arpacorp.net](https://arpacorp.net)*

---

## 1. Design Principle: Hardcode Core, Never Hardcode the World

Drafts 1–2 named slots (brain, identity, skills, …). Draft 3 generalizes:

> **The harness core is fixed. Everything the harness governs is a registered type.**

| Hardcoded (framework core) | Never hardcoded (extensions) |
|---|---|
| Event spine (AuraEvent append-only log) | Brain providers (Gemini today, unknown tomorrow) |
| Type registry & plugin lifecycle | Skill frameworks (Skillware, MCP, custom) |
| Hook pipeline (pre/post interception order) | Identity protocols (Live ID, OAuth, ephemeral) |
| Spectrum engine (levels, budgets, service toggles) | Memory backends |
| Conformance engine (declared vs observed) | Soma/host kinds (VM, script, robot, fridge) |
| Session lifecycle (birth → run → close) | Guardrail dialects |
| Output normalizers | Environment/Rooms backends |
| Auth *interface* (not any one provider) | Drive/goal schemas |
| Capability negotiation at birth | Future types not invented yet |

**Scalability rule:** adding a new type must not require editing core loop logic — only registering a plugin that declares what it **contributes**, what it **consumes**, and which **Aura operations** it participates in.

---

## 2. Architecture: Three Layers

```
┌────────────────────────────────────────────────────────────────────┐
│  EXTENSIONS — Type plugins (brain, drive, guardrails, skillware,   │
│               soma, identity, memory, environment, … + future)       │
└───────────────────────────────┬────────────────────────────────────┘
                                │ register · bind · emit · validate
┌───────────────────────────────▼────────────────────────────────────┐
│  CORE — Type registry · Manifest parser · Session manager            │
│         Hook pipeline · Spectrum · Conformance · Audit spine       │
└───────────────────────────────┬────────────────────────────────────┘
                                │ AuraEvent stream
┌───────────────────────────────▼────────────────────────────────────┐
│  OUTPUTS — Exporters (JSON, OTel, CSV, webhook, Legacy, …)           │
└────────────────────────────────────────────────────────────────────┘
```

The coat does two jobs — always, for every session:

| Job | Name | Meaning |
|---|---|---|
| **A** | **Conformance** | Agent runs **as declared** at birth — goals, guardrails, levels, type constraints |
| **B** | **Auditability** | **Everything** from first step to last — reasoning, tools, APIs, files, corrections — recorded in causal order |

Everything else (token limits, drift break, prompt compression, security) is **Aura operation** — some core-provided, some type-provided, all emitting events on the same spine.

---

## 3. The Type System (Not a Slot List)

### 3.1 What is an Aura Type?

An **Aura Type** is a versioned, registrable kind of input binding:

```yaml
# Conceptual — not final syntax
type_id: arpa.brain.gemini          # namespaced, versioned
version: 1
plugin: @aura-types/brain-gemini    # package that implements handler
```

Types are grouped by **role** (taxonomy for humans and docs), not hard limits:

| Role (examples) | Purpose | Illustrative type IDs |
|---|---|---|
| `brain` | Where thinking comes from | `arpa.brain.gemini`, `arpa.brain.ollama`, `custom.brain.*` |
| `drive` | Intent, goals, schedules | `arpa.drive.goal`, `arpa.drive.cron`, `custom.drive.*` |
| `guardrails` | Constraints, policy | `arpa.guardrails.ruleset`, `arpa.guardrails.whitelist` |
| `identity` | Who / what agent | `arpa.identity.live_id`, `arpa.identity.ephemeral` |
| `skills` | Tool/capability surface | `arpa.skills.skillware`, `mcp.tools`, `langchain.tools` |
| `memory` | Retention/persona | `arpa.memory.mnemolink`, `mem0`, `none` |
| `soma` | Body / host | `arpa.soma.process`, `arpa.soma.vm`, `arpa.soma.device` |
| `environment` | External context / Rooms | `arpa.env.rooms`, `arpa.env.none` |
| `auth` | Operator authentication | `arpa.auth.live_id_cli`, `api_key`, `none` |

**Tomorrow:** `arpa.chain.evm`, `arpa.sensor.bci`, `arpa.legacy.inheritance` — same registration path, zero core fork.

### 3.2 Type Plugin Contract

Each type plugin implements a standard interface (language-agnostic concept):

| Method / facet | Responsibility |
|---|---|
| `register()` | Declare type_id, version, role, schema for config blob |
| `validate(manifest_fragment)` | Reject invalid birth declarations early |
| `bind(session, config)` | Attach to runtime; return **capabilities** |
| `capabilities()` | What Aura operations this binding enables or requires |
| `hooks()` | Which pipeline stages to subscribe to |
| `telemetry()` | Extra fields to attach to AuraEvents |
| `conformance_rules()` | How to check declared vs observed for this type |
| `teardown()` | Clean unbind on session end |

**Capabilities** are the bridge between birth declaration and runtime behavior:

```yaml
# Example capability flags returned by brain.gemini bind()
capabilities:
  emits: [model.request, model.response, token.usage]
  accepts_ops: [limit.tokens, conserve.redundant_calls, safeguard.injection_scan]
  requires_ops: [audit.log]
  conformance:
    - brain.model_must_match_declared
```

The **core** reads capability unions from all bound types and activates the **Spectrum** + **operation set** for this session. No `if gemini` in core — only `if capability X, run op Y`.

### 3.3 Supported vs Custom Types

| Class | Discovery | Trust |
|---|---|---|
| **Supported** | Shipped or ARPA-verified plugins in registry catalog | Full docs, schema, conformance tests |
| **Community** | `dsh-plugin`-style topic / npm package | User assumes risk; sandbox defaults |
| **Private** | Org-internal plugins | Enterprise path |

Catalog is data, not code — `aura types list`, `aura types info arpa.brain.gemini`.

---

## 4. Birth Manifest vs Runtime Session

### 4.1 Aura Manifest (birth)

The **Manifest** is the declarative contract — what the operator intends. May come from:

- Hand-written YAML/JSON (BYO path)
- SoulSig bundle (ARPA path — auto-generated, signed)
- CLI wizard (`aura init`, `aura run`)

```yaml
manifest_version: 1
bindings:
  - type: arpa.brain.gemini
    config: { model: gemini-2.5-pro, … }
  - type: arpa.drive.goal
    config: { objective: "…", schedule: "…" }
  - type: arpa.guardrails.ruleset
    config: { rules: […] }
  # … arbitrary future types
spectrum:
  level: mid
  services: [monitor, audit, limit, break, conserve]
```

At parse time, core:

1. Validates all bindings against type schemas
2. Resolves capability union
3. Computes **effective operation set** for this birth
4. Stores **constitution hash** on the session record

### 4.2 Aura Session (runtime)

| Field | Scope |
|---|---|
| `manifest_id` / constitution hash | From birth — immutable for session |
| `session_id` | This run — new per activation unless resume |
| `agent_id` | Permanent agent entity (if declared) |
| `live_id` / `ubh` | If identity type present |
| `soma_instance` | Host instance descriptor (VM id, pid, device) |
| `parent_session_id` | Optional fork/resume chain |

**Live ID ≠ session ID** (from draft 2). Session nests under agent under Live ID when ARPA path is used.

### 4.3 Auth as a Type (not baked into CLI only)

Live ID auth should be **`arpa.auth.live_id_cli`** (or similar) — a type plugin the CLI loads by default, not special-case code in core.

```
aura auth login          → invokes auth type plugin → UBH token in local vault
aura agents list         → reads from identity provider API (Live ID)
aura run --agent live_x  → manifest + session; optional resume if policy allows
```

BYO users skip auth type or use `api_key`. Same core.

---

## 5. Aura Operations (Extensible, Not a Fixed Service List)

Draft 1 listed monitor, audit, break, … — those are **core operation plugins**, same extensibility model as input types:

| Operation kind | Owner | Trigger |
|---|---|---|
| `audit.log` | Core | Always on |
| `limit.tokens` | Core | Capability + spectrum |
| `safeguard.injection_scan` | Core or Synapuls type | brain + spectrum |
| `conformance.check_goal` | drive type | drive bound |
| `conformance.check_guardrail` | guardrails type | guardrails bound |
| `skillware.audit_tool` | skills type | skillware bound |
| `soma.lifecycle` | soma type | vm/device bound |
| `compress.prompt` | Core | spectrum + memory caps |

**Hook pipeline** (fixed order, extensible handlers):

```
pre_manifest → post_bind → pre_turn → pre_step → pre_tool → post_tool
→ post_step → on_drift → on_error → turn_end → post_session
```

Handlers register by operation id. Types and core both register handlers. **Audit spine** wraps every handler: emit AuraEvent before/after regardless of who owns the op.

---

## 6. Conformance Engine (Job A)

Conformance = **observed runtime ⊆ declared manifest**.

| Source | Example rule |
|---|---|
| **guardrails type** | "Only search xyz exchanges" → block tool/API call if domain ∉ whitelist |
| **drive type** | "Every Monday morning" → scheduler op wakes session; drift if run off-schedule without override |
| **brain type** | Declared model must match actual model id in requests |
| **soma type** | VM must terminate when drive reports goal complete |
| **skills type** | Only declared skill IDs may execute |
| **spectrum level** | Full autonomy blocked if identity trust tier insufficient |

On violation, core chooses (from spectrum): **reject**, **correct** (inject prompt / rewrite args), **break** (stop loop), **escalate** (human approval queue). All violations → AuraEvent `conformance.violation` + optional `conformance.corrected`.

Conformance rules live in **type plugins**, not in a giant central switch statement.

---

## 7. Audit Spine (Job B)

**Invariant:** if it happened and it mattered, it is on the log.

| Category | Logged as |
|---|---|
| Model request/response/chunks | `brain.*` events (via brain type telemetry) |
| Tool call args/results | `tool.call`, `tool.result` |
| Third-party HTTP | `external.api` (via adapter or proxy) |
| File system | `fs.*` |
| Guardrail decision | `guardrail.allow` / `guardrail.deny` |
| Conformance | `conformance.*` |
| Human override | `human.approval` |
| Session lifecycle | `session.start`, `session.end`, `session.fork` |
| Type-specific | Plugin-defined, schema-registered |

Causal graph: every event has `parent_id`, `session_id`, `constitution_hash`, timestamps, optional `ubh`.

**Model-visible = logged** (DeepSeek invariant) — adopted as ARPA invariant where applicable.

Replay: rebuild "what happened last night" from stream alone.

---

## 8. Worked Examples (Illustrative Only)

These clarify the model. They are **not** the full product surface.

### Example A — Minimal BYO (brain + drive + guardrails)

**User declares:**

```yaml
bindings:
  - type: arpa.brain.gemini
    config: { model: gemini-2.5-pro }
  - type: arpa.drive.goal
    config:
      objective: "Find best tech stocks; deliver report to mail every Monday 08:00"
      schedule: "cron:0 8 * * 1"
  - type: arpa.guardrails.ruleset
    config:
      rules:
        - deny_data_source: yahoo_finance
        - allow_exchanges: [nasdaq, nyse, arca]
spectrum:
  level: mid
  services: [monitor, audit, limit, break, conserve]
```

**What AURA does (conceptually):**

| Phase | Behavior |
|---|---|
| **Birth** | Parse manifest; bind three types; schedule type registers cron wake; guardrails type registers domain/exchange validators on `pre_tool` / `external.api` |
| **Monday 08:00** | `soma` default (local process) starts session; `session.start` logged |
| **Run** | Brain type wraps Gemini calls → token usage → `limit.tokens` active |
| **Agent searches** | Each search tool call → `pre_tool`: guardrails checks exchange/source → deny or allow → `audit.log` |
| **Violation** | Agent tries Yahoo → `guardrail.deny` → `conformance.violation` → break or correct per spectrum |
| **Complete** | Drive type evaluates "report sent to mail" → `drive.goal.complete` → session closes → CSV/JSON export |

No Live ID. Ephemeral or label identity. Full audit for **this session**; no Legacy guarantee unless user adds identity + export types later.

---

### Example B — ARPA path (Live ID + agent + VM + DeFi + Skillware)

**User flow:**

```bash
aura auth login                    # arpa.auth.live_id_cli
aura agents list                   # sees agent live_id_x under UBH
aura run --agent live_id_x \
  --resume optional                # new session_id unless policy resumes
```

**Manifest (from SoulSig + overrides):**

```yaml
bindings:
  - type: arpa.auth.live_id_cli
    config: { ubh: live_human_abc, agent: live_agent_x }
  - type: arpa.identity.live_id
    config: { agent_id: live_agent_x, soulsig: sig_… }
  - type: arpa.soma.vm
    config: { provider: cloud, lifecycle: until_task_done }
  - type: arpa.brain.claude
    config: { model: claude-sonnet-prod }
  - type: arpa.drive.goal
    config:
      objective: "Grow wallet from $100 to $200 via Uniswap v2 on Base"
      success_metric: { wallet_balance_gte: 200 }
  - type: arpa.guardrails.evm
    config:
      chain_id: 8453                    # Base only
      deny_bridges: true
      contract_whitelist: [0x…, 0x…]
  - type: arpa.skills.skillware
    config:
      skills: [wallet-screening, evm-tx-handler, uniswap-v2-swap, …]
spectrum:
  level: high
  services: [monitor, audit, limit, break, safeguard, recover]
  output: [aura-json, legacy-stream]
```

**What AURA does (conceptually):**

| Phase | Behavior |
|---|---|
| **Auth** | UBH verified; agent ownership checked; constitution loaded from SoulSig |
| **Birth** | Capability union: EVM guardrails + Skillware + VM soma + drive → rich op set |
| **VM bind** | `soma.vm` tracks host id, uptime; logs infra metadata on every event |
| **Each tx skill call** | `pre_tool`: chain_id check, contract ∈ whitelist, no bridge pattern → deny if fail |
| **Wallet screening skill** | Skillware type emits enriched `tool.call` with skill version + screening result |
| **Drift** | Agent attempts non-whitelisted contract → `conformance.violation` → break + escalate to UBH |
| **Progress** | Drive type reads wallet balance facet → logs toward $200 goal |
| **Success / fail** | Goal met or bounded failure → VM teardown per soma type → `legacy-stream` chunk signed under agent Live ID |

Complexity scales by **adding types**, not rewriting harness.

---

## 9. Standardized Coat: How It Envelops Anything

The coat is not one wrapper function. It is **five mechanisms** working together:

```
1. MANIFEST    — declare types + config at birth
2. BIND        — plugins attach; capabilities negotiated
3. PIPELINE    — hooks intercept every step
4. FIELD       — parallel ops (limits, monitor, compress) on event stream
5. SPINE       — append-only AuraEvent log ties everything together
```

Any loop — LangGraph, while-true Python, dsh, cron script — enters the coat if something implements **`arpa.runtime.*`** type (or generic `wrap` adapter) that connects loop ticks to the hook pipeline.

**The loop stays dumb. The coat stays smart.**

---

## 10. Strategic Implications

### 10.1 What changes from draft 2

| Draft 2 | Draft 3 |
|---|---|
| Fixed slot table | **Type registry** with roles |
| Listed adapters | **Plugin contract** + capability negotiation |
| Spectrum as config | Spectrum + **effective ops** derived from types |
| Two paths (A/B) | Same — manifest source differs, core identical |
| Skillware favored | Skillware is a **type plugin**, deepest in its role |

### 10.2 What stays from draft 1

- Wrap, don't replace the loop
- Event-sourced audit
- AURA Levels as permission contract
- OTel-compatible + ARPA extensions
- Legacy / Rooms / Synapuls as **future type plugins**, not v1 blockers

### 10.3 Core repo shape (conceptual)

```
aura-harness/
├── core/                 # HARD: registry, session, pipeline, spine, conformance, spectrum
├── ops/                  # Core operation plugins (audit, limit, break, …)
├── types/                # Supported type plugins (brain-*, drive-*, …)
├── types-community/      # Optional / third-party
├── spec/
│   ├── manifest.schema.json
│   ├── aura-event.schema.json
│   ├── type-plugin.contract.md
│   └── capability.registry.json
└── cli/                  # Thin — loads auth + manifest types
```

### 10.4 Anti-patterns to avoid

| Anti-pattern | Why |
|---|---|
| `switch (provider)` in core | Use brain type plugins |
| Required Live ID in core | Auth is a type; trust tier gates features |
| Monolithic guardrail parser | Guardrails are a type family |
| Separate audit per adapter | One spine; types enrich events |
| Versionless type IDs | Breaking config = new type version |
| Features without conformance rules | Job A fails silently |

---

## 11. Comparison Matrix — Harness Approaches

| Dimension | DeepSeek Harness | LangGraph | ARPA AURA (draft 3) |
|---|---|---|---|
| Extensibility model | Cordis plugins | Graph nodes + checkpointers | **Type registry + op registry** |
| Birth contract | Profile/bundle | Code/graph | **Aura Manifest** (+ SoulSig) |
| Conformance to intent | Partial (approval policy) | Partial (graph edges) | **First-class engine (Job A)** |
| Audit completeness | Session log (strong) | Traces/checkpoints | **Audit spine (Job B)** + type telemetry |
| New capability without fork | Plugin | New node | **New type plugin** |
| Identity/accountability | Weak | Weak | **identity type + trust tiers** |
| ARPA stack depth | N/A | N/A | Native types; BYO types coexist |

---

## 12. Build Order (Revised)

| Phase | Deliverable | Proves |
|---|---|---|
| **0** | `manifest.schema`, `aura-event.schema`, type plugin contract | Extensibility before features |
| **1** | Core: registry, session, spine, pipeline (empty handlers) | Coat exists |
| **2** | Types: `brain.*` (1 provider), `guardrails.ruleset`, `drive.goal` | Example A works |
| **3** | Ops: audit, limit, break, conformance shell | Jobs A + B minimal |
| **4** | CLI + `auth.live_id` type stub | Example B path opens |
| **5** | Types: `skills.skillware`, `soma.vm`, `guardrails.evm` | Example B partial |
| **6** | Output exporters + Legacy type | Continuity |
| **7** | Community type publishing docs | Scale |

---

## 13. Open Questions

1. **Manifest signing** — SoulSig signs manifest bytes, or manifest hash embedded in SoulSig?
2. **Type capability language** — JSON schema, or small DSL for conformance rules?
3. **Cross-type dependencies** — e.g. `guardrails.evm` requires `skills.evm-tx` — declared in plugin metadata?
4. **Resume semantics** — Which types allow session resume vs force new session_id?
5. **Operation ordering conflicts** — Priority registry when two types hook same stage?
6. **Rate of catalog growth** — ARPA-only types vs open namespace `custom.*`?

---

## 14. Summary

AURA Harness should be built as a **type-driven conformance and audit runtime**:

- **Inputs** = versioned, registrable **Aura Types** (not a fixed slot enum)
- **Birth** = **Manifest** declares bindings; capabilities derive **what the coat can do**
- **Runtime** = hook pipeline + field ops enforce **Job A** (as declared) and **Job B** (full log)
- **Outputs** = normalized AuraEvent stream + exporters — unchanged from draft 2
- **Core** stays small; the world scales through plugins

The two examples (Monday stocks, Base DeFi) are the same machine at different manifest complexity — not two products.

---

## See Also

- [direction-draft.md](direction-draft.md) — market analysis, three-ring model
- [direction-draft2.md](direction-draft2.md) — inputs/spectrum/outputs, two paths
- [readme.md](readme.md) — narrative spec
- [../reference.md](../reference.md) — stack definitions

---

*Draft 3 · ARPA Hellenic Logical Systems · [arpacorp.net](https://arpacorp.net)*
