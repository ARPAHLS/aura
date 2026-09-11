# Example 09 — Audit pipeline

Two sessions, audit report receipt, programmatic compare, hash-chain verify, OTel export assert, and CLI follow-ups (mock ToolHost; no live Skillware).

```bash
pip install -e ".[dev]"
python examples/09-audit-pipeline/main.py
```

Then inspect artifacts:

```bash
aura report show <session_id>
aura export <session_id>
aura export-otel <session_id>
aura compare <session_a> <session_b>
aura verify chain ~/.aura/sessions/<session_id>.jsonl
```

→ [onboarding.md](../../docs/onboarding.md#examples-learning-path) step 9
