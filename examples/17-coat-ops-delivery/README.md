# Example 17 — AURA-Native Coat Ops (#49)

Demonstrates AURA-native coat operations:

1. **External escalation delivery (`coat_ops`):** `CallableCoatOp` (or `WebhookCoatOp` / `SmtpCoatOp`) delivers `escalation.email` and `escalation.wake` notifications with `delivery: "sent"` on the spine.
2. **Membrane-level coat scan (`CoatOpRunner`):** Runs a pre-egress security scan through `SkillwareHost` egress even when the inner body is plain Python.

## Run

```bash
python examples/17-coat-ops-delivery/main.py
```

