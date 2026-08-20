# Trust & identity (v0.3)

AURA does **not** run a central identity service. Identity is **layered** so humans, CI, and audit logs can correlate runs without Live ID.

## Layers

| Layer | Field | Role |
|---|---|---|
| **Human / CI anchor** | `agent_ref` | Stable slug, e.g. `acme/compliance-bot` |
| **Internal id** | `aura_id` | ULID (time-sortable) or your supplied id |
| **Tenant** | `ids.tenant` | Auto-filled from `agent_ref` when present |
| **Skillware** | `ids.skillware` | Bundle / skill references (your structure) |
| **External** | `ids.external` | Your CMDB, assistant ids, tickets |
| **Run** | `session_id`, `trace_id`, `step_id` | One activation, causal grouping |
| **Policy** | `policy_version` | Label for constitution version at session open |
| **Binding** | `snapshot_hash` | Hash of rules + sequencer at open |

Legacy profiles with `AURA-000n` ids still load.

## Lookup

```python
agent("acme/compliance-bot")   # by agent_ref
agent("my-alias")              # by name alias
agent(aura_id="01J...")        # by internal id
```

CLI: `aura agent create --ref acme/bot --policy-version 2`

## Sessions

Each run gets `aura_sess_*`. Events carry `agent_ids` trailer (ref, policy version, external ids).

Optional future adapters may add more fields — core behavior is unchanged when they are absent.

→ [concepts.md](concepts.md) · [outputs.md](outputs.md)
