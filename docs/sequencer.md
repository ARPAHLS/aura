# Sequencer

Ordered **prescriptive** pipelines inside a session — steps, retries, gates, per-step telemetry.

---

## Philosophy: sequencer vs emergent loop

| | **Sequencer** | **Emergent agent loop** |
|---|---|---|
| Who decides order | You, in the agent profile or YAML | Model at runtime |
| Best for | Compliance SOPs, fixed pipelines | Open-ended chat, research |
| Conformance | Declared step ids vs spine on close | Per-event rules only |

The sequencer is **not** the runtime. It structures work **inside** a session while your **body** (Skillware host, script) executes each step.

**Skillware 0.5.4+** also ships host-level [`run_chain()`](https://github.com/arpahls/skillware/blob/main/docs/usage/skill_chaining.md) and `SkillContext` for model tool routing. Use Skillware chains for scripts and CI; use **AURA sequencer** when you need gates, conformance proof, and session export. Example 06 mirrors Skillware's `sanitize_input` chain with full audit spine.

→ Usage: [using-aura.md](using-aura.md) · Skillware: [skillware-integration.md](skillware-integration.md)

---

## Purpose

The **Sequencer** runs declared work in sequence:

- **Skill** invocations (via `SkillwareHost` egress)
- **Prompt** steps (declared; emit on spine)
- **Operation** steps (validate, export, notify)
- **Gate** steps and inline **gates** on any step
- **Subflow** — nested step lists

---

## Step model

```yaml
sequencer:
  steps:
    - id: validate_input
      type: op
      ref: guardrails.check
    - id: run_task
      type: skill
      ref: research
      config:
        tool: search
        args: { query: "..." }
      retry: { max: 3, backoff: exponential }
      gates: [human_confirm]
    - id: notify
      type: skill
      ref: gmail
      config:
        tool: send
        args: { to: "team@example.com" }
```

Each step emits telemetry on the audit spine: `sequencer.step.start`, `sequencer.step.end`, with `step_id`, attempt count, and refs.

### Step types

| Type | Behavior |
|---|---|
| `skill` | Routed through host egress (`tool.intent` / `tool.call` / `tool.result`) |
| `op` | Emits `sequencer.op` |
| `prompt` | Emits `sequencer.prompt` |
| `gate` | Emits `sequencer.gate` |
| `subflow` | Runs nested `config.steps` |

### Gates (on any step)

| Gate | When |
|---|---|
| `human_confirm` | Raises approval; resume with `run.approve(request_id)` |
| `constitution` | Emits gate event; rules enforced on egress (including `schema_check` when declared) |
| `budget` | Emits gate event; token rules apply on tool events |

### Conditional steps (`when`)

Skip a step when a **prior step’s result** does not match — emits `sequencer.step.skipped` (order stays auditable):

```yaml
- id: compress
  type: skill
  ref: rewriter
  depends_on: [scan]
  when:
    prior_step: scan
    field: is_safe
    equals: true
```

See [example 06](../examples/06-skillware-sequencer-chain/) and [reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md).

---

## SDK

```python
with agent("bot", sequencer={"steps": [...]}).session() as run:
    host = SkillwareHost(run._session)
    host.register(mock_or_real_skill)
    run.run_sequencer(host=host)
```

Override spec per session: `agent.session(sequencer={...})`.

---

## Middleware & PII Masking

The sequencer middleware stack supports ordered operations applied at step boundaries or invoked as explicit pipeline steps ([#58](https://github.com/ARPAHLS/aura/issues/58)).

### Two-Tier Architecture

1. **Tier 1 (Built-in, Zero Dependencies):**
   - High-throughput regex + algorithmic validation.
   - **Credit Card Luhn Validation:** Eliminates false positives by verifying card checksums algorithmically before masking.
   - **Global Phone Coverage:** Detects E.164 international notation (`+44 7911 123456`), compact E.164 (`+447911123456`), national formats with trunk prefixes (`07911 123456`, `+49 (0)30 1234567`), EU/UK/Greek/Japanese/Indian patterns, and North American NANP 10-digit and 7-digit numbers without false matches on dates or serial IDs.
   - **Supported Entity Detectors:** RFC 5322 Email, E.164 / International / NANP Phone, Credit Card, SSN, IPv4 / IPv6, API Keys / JWTs / UUIDs, and IBAN.
2. **Tier 2 (Pluggable NER Provider Protocol & Callables):**
   - Implements `PiiMaskerProvider` or simple Python callables for contextual NLP/NER models (e.g. Skillware NER, ARPA `micro-f1-mask` 270M, Microsoft Presidio).
   - Register named providers via `register_pii_provider("micro-f1-mask", model_or_fn)` and reference them in YAML configs via `provider: micro-f1-mask`.
   - **Fault-Tolerant Fallback (`on_error`):** Configurable error handling (`fallback`, `fail`, `pass`). In `fallback` mode (default), if an external ML model or service times out, the engine automatically falls back to Tier 1 native regex masking to ensure zero data leakage.

### Masking Strategies

| Strategy | Description | Example Output |
|---|---|---|
| `redact` (default) | Complete redaction with entity type tag | `[EMAIL]`, `[CREDIT_CARD]` |
| `mask` | Partial obfuscation preserving operational format and international country prefix | `a***e@domain.com`, `+44***-***-3456` |
| `pseudonymize` / `tokenize` | Deterministic, session-scoped pseudonym tokens preserving entity equivalence across agent reasoning | `<EMAIL_REF_a1b2c3>` |

### Usage Patterns

#### A. Step Boundary Middleware (Automatic Inbound / Outbound Sanitization)

Attach middleware policies via `MiddlewarePolicy` to automatically sanitize step inputs and outputs:

```yaml
middleware:
  scope: per_step
  order:
    - op: middleware.pii_mask
      config:
        strategy: redact
        entities: [all]
        allowlist: ["support@company.com"]
```

#### B. Discrete Pipeline Step Op

Execute explicit PII sanitization in the pipeline DAG:

```yaml
steps:
  - id: ingest_untrusted_data
    type: skill
    ref: db_query
  - id: sanitize_customer_pii
    type: op
    ref: middleware.pii_mask
    config:
      source_step: ingest_untrusted_data
      strategy: pseudonymize
  - id: summarize_public
    type: prompt
    ref: public_summary
```

### Strict Mode & Spectrum Containment

Setting `strict: true` configures the middleware to raise `ConstraintViolation` when sensitive PII is encountered, immediately halting unapproved data flows at high spectrum postures.

### Audit Spine Telemetry & Zero Leakage Guarantee

When masking occurs, the session emits `middleware.applied` on the audit spine. The audit spine **never** records raw secret or PII values:

```json
{
  "op": "middleware.pii_mask",
  "step_id": "sanitize_customer_pii",
  "scope": "per_step",
  "direction": "outbound",
  "strategy": "redact",
  "entities_detected": {
    "email": 2,
    "phone": 1,
    "credit_card": 1
  },
  "total_redactions": 4,
  "fields_modified": ["customer.email", "billing.card"]
}
```

The session audit report captures `scorecard.middleware = {"applied": count, "pii_redactions": count}` and surfaces the **`PII_MASKED`** finding (`severity: info`).

See [middleware-policy.schema.json](../spec/middleware-policy.schema.json).

---

## Session state

- `session.state["sequencer"]` — per-step results after completion
- `step_id` on spine events links sequencer telemetry to tool egress

---

## Conformance

On session close, declared step ids are compared to `sequencer.step.end` events with `status: ok`. Missing or out-of-order steps fail conformance.

---

## Schema

[sequencer.schema.json](../spec/sequencer.schema.json)

Implementation: `aura/sequencer/` — `SequencerRunner`, `SequencerEngine`

Example: [examples/04-sequencer-pipeline](../examples/04-sequencer-pipeline/)
