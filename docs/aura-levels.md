# AURA Levels

> **Shipped** — `spectrum.level` on agent profiles drives enforcement at egress ([#27](https://github.com/ARPAHLS/aura/issues/27)). See [using-aura.md](using-aura.md).

**Permissioned autonomy** — not binary on/off.

From [narrative.md](narrative.md). Enforced by Spectrum + conformance engine + hook pipeline at session egress.

---

## Three planes (always / enforce / escalate)

| Plane | Coat | What runs |
|---|---|---|
| **Audit** | Loose | Spine + export receipt — always on in production profiles |
| **Enforce** | Tight | Egress rules, sequencer gates, constitution at `tool.call` |
| **Escalate** | Tailored | Observers (Monitor, Break, Limit), metrics snapshots, goal/SLO presets; wire via `profile.observers[]` or `spectrum.services[]` ([#77](https://github.com/ARPAHLS/aura/issues/77)) |

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

## Profile spec

```yaml
spectrum:
  level: mid   # low | mid | high | full
  services:
    - monitor
    - audit
  service_config:
    limit:
      max_tool_calls_per_minute: 30
  strict_services: false   # true → observer.alert on unknown service names
```

| Level | Coat | Enforcement | Default services (when `services` omitted) |
|---|---|---|---|
| **low** | Loose | Audit only — explicit profile `rules` still apply; off-scope tools pass | none |
| **mid** | Tight | Explicit profile rules only (default when unset) | none |
| **high** | Tight | Auto `allow_tools` from profile `skills` (+ sequencer refs) | `monitor` |
| **full** | Tailored | High bind + `tool.call` must include `step_id` (sequencer bind) | `monitor`, `break` |

When `services` is present, exactly those presets attach (except `audit`, which is implicit). Profiles **without** a `spectrum` block behave as before — no automatic service wiring.

Stored on agent profiles; summarized on `membrane.ingress` and `session.open` (`services_activation`). CLI:

```bash
aura agent set my-bot --spectrum-level high
aura agent set my-bot --spectrum-service monitor --spectrum-service limit
aura agent show my-bot   # includes effective_spectrum + enforcement_rules
```

Setting only `--spectrum-level` merges with existing `services` and `service_config` — it does not replace the whole block.

Schema: [manifest.schema.json](../spec/manifest.schema.json)

---

Industry gap: *how much reality may this agent touch, and who decided?* — AURA Levels are ARPA's answer.
