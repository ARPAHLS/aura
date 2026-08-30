# Operator identity

Optional verified operator trailer for enterprise session receipts ([#55](https://github.com/ARPAHLS/aura/issues/55)).

## Default (unchanged)

No identity adapter → lite `agent_ref` + `aura_id` only. No login, no extra fields.

## Enable mock (CI / local)

```bash
export AURA_MOCK_OPERATOR_SUBJECT=ci-operator@corp.com
```

```yaml
# ~/.aura/config.yaml or aura.project.yaml
identity:
  adapter: mock
  subject: ci-operator@corp.com
identity_export_pii: false
```

## OIDC / Auth0

```yaml
identity:
  adapter: auth0
  domain: your-tenant.auth0.com
  audience: your-api-audience
```

```bash
export AURA_AUTH0_TOKEN="<access_token>"
# or AURA_OIDC_TOKEN
pip install "aura-harness[identity]"
```

Signature verification uses JWKS (`pyjwt` + `cryptography`).

## SDK

```python
from aura import agent, configure
from aura.identity.adapters.mock import MockIdentityAdapter

configure()
ag = agent("bot")
adapter = MockIdentityAdapter(subject="ops@corp.com")
with ag.session(identity_adapter=adapter) as run:
    run.emit("turn.start", {})
print(run.summary["identity"])
```

Manual (unverified) operator on profile:

```yaml
ids:
  operator:
    subject: ops@corp.com
    verified: false
    method: manual
```

## Spine

Successful bind emits `identity.bound`. Operator appears under `agent_ids.ids.operator` on **every event** for SIEM parity.

## Export redaction

By default, `email` / `name` / `phone` are stripped from summary and OTel export. Full PII:

```yaml
identity_export_pii: true
```

CLI: `aura identity show`

→ [trust-paths.md](../docs/trust-paths.md) · [examples/09-operator-identity](../examples/09-operator-identity/main.py)
