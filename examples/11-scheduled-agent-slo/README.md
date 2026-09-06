# Example 11 — Goal drift + schedule SLO

Nickel cron **north star** from Phase D ([#46](https://github.com/ARPAHLS/aura/issues/46)): declared goal and schedule on the agent profile vs observed tool behavior on the audit spine.

## What it shows

| Posture | Mechanism |
|---|---|
| **Goal drift** | `preset: goal_drift` compares `tool.intent` / `tool.call` payloads to `variables.goal` and forbidden topics → `conformance.drift` |
| **Schedule SLO** | `preset: schedule_slo` requires `sql/append` before deadline + grace → `slo.missed` on close if incomplete |
| **Audit receipt** | `aura report show` / summary JSON surfaces `GOAL_DRIFT` and `SCHEDULE_SLO_MISS` findings |

Observers **alert only** — enforcement stays in egress rules and escalation playbooks ([#47](https://github.com/ARPAHLS/aura/issues/47)).

## Run

```bash
pip install -e .
python examples/11-scheduled-agent-slo/main.py
```

Scenarios (env `SLO_SCENARIO`):

| Value | Behavior |
|---|---|
| `pass` (default) | Nickel research + SQL append within window — verdict `pass` |
| `drift` | Off-scope shipyard query — `GOAL_DRIFT` finding |
| `miss` | No SQL append past 09:15 grace — `SCHEDULE_SLO_MISS` finding |

```bash
# PowerShell
$env:SLO_SCENARIO="drift"; python examples/11-scheduled-agent-slo/main.py
$env:SLO_SCENARIO="miss"; python examples/11-scheduled-agent-slo/main.py
```

## Profile shape

```yaml
purpose: Daily nickel market research → SQL append
variables:
  goal: "nickel market data only"
  schedule: "0 9 * * *"
  schedule_grace_minutes: 15
observers:
  - preset: goal_drift
    id: nickel-goal
    config:
      forbidden_topics: [shipyard, steel]
  - preset: schedule_slo
    id: nickel-slo
    config:
      required_tool: sql/append
```

For tests and demos, inject wall clock via `variables._test_clock_iso` (ISO-8601) or `config.clock_iso`.

## Next

- Escalation playbooks on `slo.missed` / `conformance.drift` — [#47](https://github.com/ARPAHLS/aura/issues/47)
- Schema checks at high bind — [#78](https://github.com/ARPAHLS/aura/issues/78)
- Limit observer preset (rate/budget) — [#79](https://github.com/ARPAHLS/aura/issues/79)
