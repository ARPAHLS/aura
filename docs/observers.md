# Observers

> **Tier 2 — Build.** Parallel subscribers on the audit spine. They **observe and signal** — they do not replace egress enforcement. See [using-aura.md](using-aura.md) (membrane model) and [field-services.md](field-services.md) (twelve-service vocabulary).

---

## Model

```
Ingress → [ Body / host ] → Egress (enforce) → Audit spine
                ↑
           Observers (parallel — every spine event)
```

| Rule | Meaning |
|---|---|
| **Non-blocking** | Presets emit `observer.note` or `observer.alert`; they do not deny `tool.call` |
| **Egress enforces** | Constitution, allowlists, gates, approvals — [sequencer.md](sequencer.md), [aura-levels.md](aura-levels.md) |
| **Spine is truth** | All observer output is append-only events on the same JSONL trail |

Custom handlers: `CallableObserver` or profile entries with an `id` + handler — see [using-aura.md](using-aura.md#observers).

---

## Packaged presets

| Preset | Spine output | Purpose |
|---|---|---|
| **monitor** | `observer.note` | Tool counts, step timing, soft repeat warnings |
| **break** | `observer.alert` | Circuit-breaker on repeated identical `tool.intent` |
| **limit** | `observer.note` then `observer.alert` | Rate / token budget warnings and breach alerts |
| **goal_drift** | `conformance.drift` | Tool payloads vs declared goal / forbidden topics |
| **schedule_slo** | `slo.missed` | Required work incomplete by schedule + grace |

Runnable tours: [example 07](../examples/07-observer-presets/) (monitor, break, limit), [example 11](../examples/11-scheduled-agent-slo/) (goal_drift, schedule_slo), [example 10](../examples/10-observer-metrics-snapshot/) (custom metrics note).

---

## Wiring paths

### 1. Explicit — `profile.observers[]`

Always wins when the same preset would also come from `spectrum.services[]`.

```yaml
observers:
  - preset: monitor
    id: loop-monitor
    config:
      max_identical_intents: 5
  - preset: break
    id: loop-break
    config:
      max_identical_intents: 3
  - preset: limit
    id: budget-guard
    config:
      max_tool_calls_per_minute: 30
      max_tokens_per_step: 8000
      warn_ratio: 0.8
```

### 2. Declarative — `spectrum.services[]`

When the profile has an **`spectrum` block**, listed services wire presets at session open ([#77](https://github.com/ARPAHLS/aura/issues/77)). `audit` in the list is metadata only — the spine is always on.

```yaml
spectrum:
  level: high
  services: [monitor, limit]
  service_config:
    limit:
      max_tool_calls_per_minute: 30
  strict_services: false
```

| When `services` omitted | Level default wiring |
|---|---|
| `low` / `mid` | none |
| `high` | `monitor` |
| `full` | `monitor`, `break` |

No `spectrum` block on the profile → backward compatible; nothing auto-wires.

**Verified identity ([#73](https://github.com/ARPAHLS/aura/issues/73)):** `high` / `full` default to requiring a verified operator at session open when a `spectrum` block is present. Observers and services wiring are independent — identity is enforced at bind, before presets attach.

`session.open` includes `spectrum.services_activation` (`activated`, `skipped_explicit`, `unknown`). See [outputs.md](outputs.md), [aura-levels.md](aura-levels.md).

CLI merge (does not drop existing `services` / `service_config`):

```bash
aura agent set my-bot --spectrum-level full --spectrum-service limit
```

---

## Preset config reference

### monitor

```yaml
config:
  max_identical_intents: 0   # 0 = disabled; emit note when threshold reached
  log_path: .aura/monitor.log   # optional side log
```

### break

```yaml
config:
  max_identical_intents: 5
  window_seconds: 60
```

### limit

```yaml
config:
  max_tool_calls_per_minute: 30   # 0 = disabled
  max_tokens_per_step: 8000
  warn_ratio: 0.8                 # emit note from this fraction of max_tokens_per_step
```

### goal_drift / schedule_slo

See [example 11](../examples/11-scheduled-agent-slo/README.md) for `variables.goal`, `forbidden_topics`, `schedule`, and grace config.

---

## vs field services vs sequencer

| Layer | Doc | Role |
|---|---|---|
| **Observers** | this file | Parallel analytics / alerts on the spine |
| **Field services** | [field-services.md](field-services.md) | Twelve-service design vocabulary + roadmap |
| **Sequencer** | [sequencer.md](sequencer.md) | Declared step pipelines and gates |
| **Egress** | [guides/reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md) | ToolHost bind and guarded execution |

Code: `aura/observers/presets/` · `aura/core/spectrum_services.py`
