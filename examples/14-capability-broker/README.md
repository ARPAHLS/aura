# Example 14 — Capability broker

Named intents at egress without putting credentials on the agent profile ([#48](https://github.com/ARPAHLS/aura/issues/48)).

The agent asks for `shop-x-milk`. AURA checks `profile.capabilities[]` (merchant, item, card label). Only after that passes does a **SecretBroker** inject the live token into the in-memory tool call. The audit spine records the capability id and allow/deny — never the secret.

| Spectrum | Off-scope call |
|---|---|
| `low` | Record `constraint.violated` (`audit_only`) and still run (no inject) |
| `mid` / `high` / `full` | Block before execute |

Pair with [example 02](../02-guarded-tools/) (tool allow/deny) and [example 12](../12-escalation-playbooks/) (`constraint.violated` playbooks). Guide: [docs/capabilities.md](../../docs/capabilities.md).

## Run

```bash
pip install -e .
python examples/14-capability-broker/main.py
```

Single scenario:

```bash
# PowerShell
$env:CAPABILITY_SCENARIO="deny_wrong_card"
python examples/14-capability-broker/main.py
```

| `CAPABILITY_SCENARIO` | What it shows |
|---|---|
| `allow_inject` | Matching scope → broker injects → spine has no secret |
| `deny_wrong_card` | `card=Z` blocked at mid; finding `CAPABILITY_DENIED` |
| `low_audit` | Same miss at `spectrum.level: low` still runs, no inject |
| `missing_id` | Gated tool without `capability_id` is denied |
| `multi_inject` | Dual secrets (AWS access key + secret) and `headers.Authorization` with `Bearer ` prefix ([#86](https://github.com/ARPAHLS/aura/issues/86)) |
| `all` | Every row (default) |

## Profile sketch

Single secret (legacy or compact):

```yaml
spectrum:
  level: mid
capabilities:
  - id: shop-x-milk
    tool: payment
    allowed:
      merchant: shop-x
      item: milk
      card: Y
    secret:
      ref: env:AURA_CAP_SHOP_X_CARD_Y
```

Multiple secrets & HTTP headers ([#86](https://github.com/ARPAHLS/aura/issues/86)):

```yaml
spectrum:
  level: mid
capabilities:
  - id: s3-dual
    tool: s3_read
    allowed:
      bucket: ledger
    inject:
      - ref: env:AWS_ACCESS_KEY_ID
        as: aws_access_key_id
      - ref: env:AWS_SECRET_ACCESS_KEY
        as: headers.Authorization
        prefix: "Bearer "
```

Never put `secret.value`. Bind a broker at session open (`MapSecretBroker` in this demo; `EnvSecretBroker` in production).
