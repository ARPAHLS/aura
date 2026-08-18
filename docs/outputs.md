# Outputs & Bridges

Normalized output — regardless of input stack.

---

## Audit Spine

**AuraEvent** — append-only, causal, timestamped.

| Invariant | Meaning |
|---|---|
| Everything material is logged | Tools, APIs, files, corrections, human overrides |
| Causal IDs | `parent_id`, `trace_id`, `step_id`, `task_id` |
| OTel-compatible + ARPA extensions | UBH, constitution hash, input references |

Schema: [aura-event.schema.json](../spec/aura-event.schema.json)

---

## Output Layers

| Layer | Contents |
|---|---|
| **Event stream** | Full causal log — replay, debug, compliance |
| **Session summary** | Cost, duration, outcome, anomalies |
| **Audit pack** | Signed bundle + constitution hash |
| **Analytics slice** | Metrics for improvement and training |
| **Exports** | JSON, CSV, OTel, webhook |

Implementation: `aura/exporters/`

---

## Bridges

Optional integrations when the ARPA stack is present:

| Bridge | Project | Role |
|---|---|---|
| `liveid` | Live ID | Manifest, session registry, UBH |
| `legacy` | Legacy Protocol | Continuity stream |
| `rooms` | Rooms | Session environment |
| `skills` | Skills frameworks | Native bundle integration |
| `synapuls` | Synapuls | Surface security |
| `mnemolink` | MnemoLink | Memory policy |

Export profiles:

```yaml
spectrum:
  output: [aura-json, otel, csv, legacy-stream, webhook]
```

---

See [sequencer.md](sequencer.md) · [trust-paths.md](trust-paths.md)
