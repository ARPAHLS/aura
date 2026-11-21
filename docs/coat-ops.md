# Coat Ops & Escalation Delivery

AURA-native **coat ops** (`aura.core.coat_ops`) provide zero-dependency operational primitives for **escalation delivery** (`email`, `wake`, `webhook`) and **membrane-level scans** routed through `SkillwareHost` egress.

> AURA is a runtime coat, not another agent framework—it governs and attests your loop without taking ownership of orchestration or credentials.

---

## Escalation Delivery (`CoatOpDispatcher`)

When an `EscalationEngine` rule fires with `action: "email"` or `action: "wake"`, AURA dispatches through a configured `CoatOpDispatcher` (or records `delivery: "stub"` when no coat op is wired) and emits `escalation.email` or `escalation.wake` on the `AuditSpine`:

- **`WebhookCoatOp`**: Sends JSON payloads to an HTTP/HTTPS endpoint with SSRF URL validation (blocks loopback/private/link-local targets unless explicitly allowed) and optional `X-AURA-Signature` HMAC-SHA256 signing.
- **`SmtpCoatOp`**: Sends escalation emails via Python's stdlib `smtplib` (zero external dependencies).
- **`CallableCoatOp`**: Wraps any Python callable `(event_type, payload) -> dict` for custom delivery backends.

```python
from aura import agent
from aura.core.coat_ops import CoatOpDispatcher, WebhookCoatOp

dispatcher = CoatOpDispatcher(
    wake=WebhookCoatOp(url="https://hooks.example.com/aura-wake", secret="whsec_...")
)

ag = agent("acme/ops-bot", policy_version="1")
with ag.session(coat_ops=dispatcher) as run:
    ...
```

---

## Membrane Scans (`CoatOpRunner`)

`CoatOpRunner` executes membrane-level scans (using Skillware skills or `MockSkill` implementations) through `SkillwareHost` egress so every scan is subject to policy gates, secret redaction, and spine logging.

---

## See Also

- Runnable example: [examples/17-coat-ops-delivery/](../examples/17-coat-ops-delivery/README.md)
- Escalation playbooks & observers: [observers.md](observers.md)
- Skillware integration: [skillware-integration.md](skillware-integration.md)

