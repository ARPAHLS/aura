# AURA Levels

> **Optional / roadmap** — autonomy tiers; runtime enforcement UX tracked in [#27](https://github.com/ARPAHLS/aura/issues/27). Today use postures in [using-aura.md](using-aura.md), sequencer gates, and profile `spectrum`.

**Permissioned autonomy** — not binary on/off.

From [narrative.md](narrative.md). Enforced by Spectrum + conformance engine + hook pipeline (enforcement wiring expands in #27).

---

## Three planes (always / enforce / escalate)

| Plane | Coat | What runs |
|---|---|---|
| **Audit** | Loose | Spine + export receipt — always on in production profiles |
| **Enforce** | Tight | Egress rules, sequencer gates, constitution at `tool.call` |
| **Escalate** | Tailored | Observers (Monitor, Break), metrics snapshots, future playbooks ([#38](https://github.com/ARPAHLS/aura/issues/38)) |

AURA-native tailored patterns use **observers + export** — see [example 10](../../examples/10-observer-metrics-snapshot/). Third-party registry skills may consume exports optionally; AURA does not require them for SLO visibility.

---

| Level | Posture | Typical coat |
|---|---|---|
| **Low** | Suggest only. Human approves before action. | Loose |
| **Mid** | Act within defined scope. Escalate at boundaries. | Tight |
| **High** | Independent within enforced guardrails. Periodic human oversight. | Tight + observers |
| **Full** | Self-directed within constitution. Accountability via audit — not per-action supervision. | Tailored |

---

## Properties

- **Permission contract** — not a badge
- **Enforced by harness** — visible in logs, revocable by UBH
- **Effective level** may be capped by **trust tier** (Path B ≤ Path A ceiling)
- **Provider-aware** — same level, different enforcement for cloud vs local brain (see [trust-paths.md](trust-paths.md))

---

## Gates

Sequencer and hooks consult level for:

- Tool execution without approval
- External API / filesystem / chain transactions
- Self-correction vs human escalation on drift
- Confirmation gates (`human_confirm`)

---

## Profile spec (preview)

```yaml
spectrum:
  level: mid   # low | mid | high | full
  services:
    - monitor
    - audit
```

Stored on agent profiles; summarized on `membrane.ingress` when set. Full level→deny behavior wiring: [#27](https://github.com/ARPAHLS/aura/issues/27).

Schema: [manifest.schema.json](../spec/manifest.schema.json)

---

Industry gap: *how much reality may this agent touch, and who decided?* — AURA Levels are ARPA's answer.
