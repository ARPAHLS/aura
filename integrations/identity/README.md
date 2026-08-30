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

Signature verification uses JWKS (`pyjwt` + `cryptography`). **Do not use `verify_signature: false` in production** — that mode is for local tests only.

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

## Bring your own adapter

Implement the protocol and pass it to `session()` — no central AURA identity service required:

```python
from aura.identity.models import OperatorIdentity
from aura.identity.protocol import IdentityContext


class CorpSsoAdapter:
    method = "corp_sso"

    def resolve(self, context: IdentityContext) -> OperatorIdentity | None:
        token = context.env.get("CORP_SSO_TOKEN")
        if not token:
            return None
        # validate with your IdP here
        return OperatorIdentity(
            verified=True,
            method=self.method,
            subject="user-123",
            session_ref=context.session_id,
        )


with ag.session(identity_adapter=CorpSsoAdapter()) as run:
    run.emit("turn.start", {})
```

For opaque third-party ids without verification, nest under `ids.external` on the agent profile — no adapter needed.

Profile `types` entry (built-in adapter names):

```yaml
types:
  - role: identity
    type_id: arpa.identity.oidc
    config:
      adapter: oidc
      issuer: https://login.example.com/
      audience: aura-api
```

## Spine and export

Successful bind emits `identity.bound`. Operator appears under `agent_ids.ids.operator` on **every event** for SIEM parity.

By default, `email` / `name` / `phone` are stripped from **summary and OTel** export (JSONL spine keeps full fields for forensic review):

```yaml
identity_export_pii: true   # opt in to include PII on export surfaces
identity_required: true     # fail session open when no operator resolves
```

CLI: `aura identity show`

→ [trust-paths.md](../docs/trust-paths.md) · [examples/09-operator-identity](../examples/09-operator-identity/main.py)
