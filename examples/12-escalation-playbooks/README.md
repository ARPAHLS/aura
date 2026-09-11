# Example 12 — Escalation playbooks

Tailored-coat **escalate plane**: when observers or egress policy emit trigger events, `profile.escalations[]` runs configured actions ([#47](https://github.com/ARPAHLS/aura/issues/47)).

**Where rules live:** on the **agent profile** (registry JSON under `{AURA_HOME}/agents/`), not on session **manifest bindings**. Manifests declare brain/tool bindings for a birth; playbooks are durable agent policy — same place as `rules`, `observers`, and `spectrum`. Pass `escalations=` to `agent()` / store in profile JSON; wire once per agent, not per session manifest.

Pair with [example 11](../11-scheduled-agent-slo/) (observers that emit triggers) and [observers.md](../../docs/observers.md#3-escalation-playbooks--profileescalations-47).

## Run

From repo root:

```bash
pip install -e .
python examples/12-escalation-playbooks/main.py
```

Single scenario:

```bash
# PowerShell
$env:ESCALATION_SCENARIO="drift_pause_approve"
python examples/12-escalation-playbooks/main.py
```

| `ESCALATION_SCENARIO` | Trigger | Actions demonstrated |
|---|---|---|
| `slo_miss_email` | `slo.missed` | `log`, `email:ops@company.com` (stub) |
| `drift_nudge` | `conformance.drift` | `nudge:…` → `membrane.nudge` |
| `break_alert` | `observer.alert` | `alert:…` → `observer.note` |
| `constraint_nudge` | `constraint.violated` | `log`, `nudge` after `deny_tools` |
| `drift_pause_approve` | `conformance.drift` | `pause` (mid+ spectrum) + `approve()` |
| `custom_handler` | `slo.missed` | `session(escalation_handler=…)` hook |
| `all` | — | runs every row (default) |

## Profile sketch

```yaml
escalations:
  - id: slo-ops-email
    on: slo.missed
    after_minutes: 15   # metadata for external schedulers; in-session fires immediately
    actions: [log, email:ops@company.com]
  - on: conformance.drift
    actions: [nudge:"Re-align to declared goal"]
  - on: observer.alert
    actions: [alert, log]
  - on: constraint.violated
    actions: [log, nudge:Review constitution]
```

Destructive actions (`pause`, `wake`) require spectrum **≥ mid**. Email/wake delivery is stubbed — real coat ops in [#49](https://github.com/ARPAHLS/aura/issues/49).

## Expected spine events

Each fired rule emits `escalation.fired` with action results. Audit report includes finding `ESCALATION_FIRED` when present. `session.open` lists `spectrum.escalations.rule_count` when rules are configured.

## Related

- [outputs.md](../../docs/outputs.md) — escalation spine events
- [example 07](../07-observer-presets/) — presets that emit `observer.alert`
- [example 11](../11-scheduled-agent-slo/) — `slo.missed` / `conformance.drift` sources
