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
| `constitution` | Emits gate event; rules enforced on egress |
| `budget` | Emits gate event; token rules apply on tool events |

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

## Middleware stack (roadmap)

Ordered operations applied per step or per model request — schema exists; handlers are stubs:

```yaml
middleware:
  scope: per_step
  order:
    - op: firewall
    - op: pii_mask
```

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
