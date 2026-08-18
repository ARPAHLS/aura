# AURA Levels

**Permissioned autonomy** — not binary on/off.

From [narrative.md](narrative.md). Enforced by Spectrum + conformance engine + hook pipeline.

---

| Level | Posture |
|---|---|
| **Low** | Suggest only. Human approves before action. |
| **Mid** | Act within defined scope. Escalate at boundaries. |
| **High** | Independent within enforced guardrails. Periodic human oversight. |
| **Full** | Self-directed within constitution. Accountability via Live ID + audit — not per-action supervision. |

---

## Properties

- **Permission contract** — not a badge
- **Enforced by harness** — visible in logs, revocable by UBH
- **Effective level** may be capped by **trust tier** (Path B ≤ Path A ceiling)
- **Provider-aware** — same level, different enforcement for cloud vs local brain (see draft 2)

---

## Gates

Sequencer and hooks consult level for:

- Tool execution without approval
- External API / filesystem / chain transactions
- Self-correction vs human escalation on drift
- Confirmation gates (`human_confirm`)

---

## Spec

```yaml
spectrum:
  level: mid   # low | mid | high | full
```

Schema: [manifest.schema.json](../spec/manifest.schema.json)

---

Industry gap: *how much reality may this agent touch, and who decided?* — AURA Levels are ARPA's answer.
