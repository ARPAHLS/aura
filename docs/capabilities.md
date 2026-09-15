# Capability broker

Named service access **without credential custody** ([#48](https://github.com/ARPAHLS/aura/issues/48)).

The **model is generic**: a capability is an id, optional tool/skill bind, an `allowed` dict of **labels** (any keys you care about), and an optional secret **ref**. Payment (`shop-x` / milk / card Y) is the issue's example, not a special case. The same shape covers `github.api` + `repo`, `slack.post` + `channel`, `stripe.charge` + `merchant`, and so on.

The agent names an intent (`shop-x-milk` or `gh-ledger-read`). Egress checks that intent against `profile.capabilities[]`. After the check **passes**, a **SecretBroker** injects **one** live credential into the in-memory tool args (`inject_as`, default `token`). The audit spine records allow/deny and the capability id — **never** the secret.

This is a membrane/policy feature, not an IAM product. Observers still do not enforce. Failure handling reuses [spectrum](aura-levels.md) and [escalation playbooks](observers.md#3-escalation-playbooks--profileescalations-47).

---

## Why

If a card number or API key lives on the agent JSON, the model can echo it, the spine will log it, and the wrong merchant can still be called. Capabilities invert that:

1. Profile stores **labels and refs** (`card: Y`, `secret.ref: env:…`).
2. `tool.call` must carry `capability_id` for gated tools.
3. Allowed fields are a required subset of args (wrong shop / SKU / card → deny).
4. Broker injects the token **after** policy, into execute args only.
5. Spine, summary, OTel, and `aura agent show` never persist the value.

---

## Profile

```yaml
spectrum:
  level: mid          # low = audit-only miss; mid+ = block
capabilities:
  - id: shop-x-milk
    tool: payment
    allowed:
      merchant: shop-x
      item: milk
      card: Y          # label, not a PAN
    secret:
      ref: env:AURA_CAP_SHOP_X_CARD_Y
```

| Field | Role |
|---|---|
| `id` | Stable capability id the agent must send (`capability_id` or `capability`) |
| `tool` / `skill_id` | Optional bind. If set, that tool/skill is **gated** (id required). If omitted, every `tool.call` is gated. |
| `allowed` | Required subset of args. `"*"` = any value; a list = allowlist; dotted keys (`merchant.name`) walk nested dicts. Numbers and digit-strings compare equal (`3` / `"3"`). |
| `strict_args` | When true, extra arg keys are denied. Default false so hosts may pass metadata. |
| `secret.ref` | Credential locator only (`env:VAR`, or a ref your callable broker understands). **No `value` / `token` / plaintext.** |
| `inject_as` | Live args key for the injected secret (default `token`). |

CLI:

```bash
aura agent set my-bot --capabilities-file caps.json
aura agent show my-bot   # capabilities + capabilities_summary (refs only)
```

`agent(..., capabilities=[...])` and `AgentRegistry.create/update_profile` reject plaintext secret keys.

---

## Session and broker

```python
from aura import MapSecretBroker, agent
from aura.hosts import MockSkill, SkillwareHost

broker = MapSecretBroker({"env:AURA_CAP_SHOP_X_CARD_Y": "…"})  # tests only
# production: EnvSecretBroker()  (default when capabilities are set)
# vault/KMS: CallableSecretBroker(lambda ref: vault.get(ref))

ag = agent("payer", capabilities=[...], spectrum={"level": "mid"})
with ag.session(secret_broker=broker) as run:
    host = SkillwareHost(run._session)
    host.register(MockSkill("pay", {"payment": handler}))
    host.execute("pay", "payment", {
        "capability_id": "shop-x-milk",
        "merchant": "shop-x",
        "item": "milk",
        "card": "Y",
    })
```

| Broker | Use |
|---|---|
| `EnvSecretBroker` | Default. Resolves `env:NAME` from the process environment. |
| `MapSecretBroker` | Tests and host-local maps. **Do not** persist a map on the profile. |
| `CallableSecretBroker` | Vault / KMS / custom. |
| `ChainSecretBroker` | First successful resolve wins. |

Optional profile `types` with `role: auth` and `config.provider: env` selects the env broker. Map/callable brokers cannot be declared in profile JSON.

---

## Spectrum

| Level | Capability miss |
|---|---|
| **low** | Spine `constraint.violated` with `audit_only: true`; call **still runs**; **no inject** unless scope passed. Audit finding `CAPABILITY_AUDIT`. |
| **mid** (default when spectrum unset) | **Block** (`ConstraintViolation`). Finding `CAPABILITY_DENIED`. |
| **high** / **full** | Same block. Capability `tool` / `skill_id` are added to the high/full allowlist. `full` still requires `step_id`. |

Escalations already subscribed to `constraint.violated` (`nudge`, `pause`, …) fire on denied (and audit-only) capability misses. Destructive `pause` still requires spectrum ≥ mid.

---

## Egress path

`guarded_tool_call` / `SkillwareHost.execute`:

1. `tool.intent` (redacted)
2. `tool.call` → `capability_scope` (+ other rules)
3. Strip agent-supplied secret-like keys (`token`, `api_key`, …)
4. If scope passed and `secret.ref` is set → broker resolve → inject → `capability.injected` (ref only)
5. Execute with live args
6. `tool.result` / `tool.error` (redacted; live secret substrings of length ≥ 8 are scrubbed)

Direct `run.emit("tool.call", …)` still enforces scope. There is no execute, so nothing is injected — that is expected for emit-only coats.

Unresolved refs after an allow raise `SecretNotFoundError` and emit `tool.error` (`secret_broker_unresolved`). Audit finding `SECRET_BROKER_ERROR`.

---

## Redaction

Applied on **every** `session.emit` (JSONL, then summary and OTel inherit it):

- Keys named like secrets (`token`, `api_key`, `password`, `authorization`, `*_secret`, …) become `[redacted]` on **every** spine event, including sessions with no `capabilities[]`. Usage counters (`tokens`, `token_count`) are kept. A pagination field named `token` will be redacted — rename it or treat it as sensitive.
- Values the broker actually injected are scrubbed wherever they appear (including tool results that echo the token).
- Agent-supplied tokens are **never** used as the inject channel.

`aura agent show` and profile JSON persist `secret.ref` only.

---

## Limits (not in this change)

- **One secret per capability** (`inject_as` is a single args key). AWS-style key+secret pairs need two capabilities or a callable broker that returns a composite the host unpacks.
- **Exact / list / wildcard equality** on `allowed` — not ranges (`amount <= 50`), regex, or JSON Schema. Broader constitution/schema checks remain on the roadmap.
- **Allowed values are labels**, not credentials. Strict parse rejects secret-like **keys** (`token`, `api_key`, …) and values that look like live tokens (`sk-…`, `tok_…`, `ghp_…`, …). Ordinary long strings (`acme/private-ledger`, `organic whole milk`) are valid.
- **Inject runs only on `guarded_tool_call` / ToolHost execute.** Direct `run.emit("tool.call", …)` still enforces scope but does not inject (there is no execute).
- **Not** rewind, retry-N, or Skillware `SecretProvider` types.

Runnable demo: [examples/14-capability-broker](../examples/14-capability-broker/). Stress: `python scripts/aura_capability_stress_sim.py`.
