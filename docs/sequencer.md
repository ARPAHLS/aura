# Sequencer

Ordered pipelines inside a session — steps, retries, middleware, gates.

---

## Purpose

The **Sequencer** runs declared work in sequence:

- Skill invocations (any skills type)
- Prompt and context assembly
- Operation steps (validate, export, notify)
- Sub-flows and branches

The hook pipeline intercepts loop ticks. The Sequencer **structures** multi-step work when the manifest declares a pipeline.

---

## Step Model

```yaml
sequencer:
  steps:
    - id: validate_input
      type: op
      ref: guardrails.check
    - id: run_task
      type: skill
      ref: category/skill_name
      version: ">=1.0.0"
      retry: { max: 3, backoff: exponential }
      gates: [human_confirm]
```

Each step emits telemetry on the audit spine: `step_id`, `trace_id`, latency, attempt count, skill reference and version when applicable.

---

## Middleware Stack

Ordered operations applied per step or per model request:

```yaml
middleware:
  scope: per_step
  order:
    - op: firewall
    - op: pii_mask
    - op: prompt_compress
```

Policy can be preset or manifest-defined. Handlers register as operation plugins — same extensibility as input types.

---

## Session State

Context carried across steps and turns:

- `task_id` — budget and limiter attribution
- `session_state` — serializable key-value passed step to step
- `turn_context` — thread, room, or host-specific handles
- Constitution hash — from manifest; checked each step

---

## Gates

| Gate | When |
|---|---|
| Hard constraint validation | Before step — schema, guardrails, constitution |
| Confirmation | Human approve before high-risk step |
| Budget cap | Token, cost, time — via spectrum and `task_id` |

Violations emit `conformance.violation` on the audit spine.

---

## Schema

[sequencer.schema.json](../spec/sequencer.schema.json) · [middleware-policy.schema.json](../spec/middleware-policy.schema.json)

Implementation: `aura/sequencer/`
