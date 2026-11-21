# Example 16 — Skillware 0.6.2+ Audit Bridge, FinOps & Manifest v2 Safety

Demonstrates AURA paired with Skillware 0.6.2+ capabilities:

- **Async egress (`SkillwareHost.aexecute`)** with bounded concurrency (`max_concurrency=4`) and FinOps `audit_meta` (`model`, `prompt_tokens`, `completion_tokens`)
- **Single-ledger default vs. optional dual-ledger cross-anchoring:** `SkillwareHost.create_context()` bridges `on_dispatch` directly into AURA's `AuditSpine` (zero duplicate disk I/O by default); passing `audit_log_path` adds optional Skillware JSONL cross-verification via `verify_dual_audit_chain()` or `aura verify chain <aura.jsonl> --skillware-log <sw.jsonl>`
- **Manifest v2 physical substrate safety gate (`hardware_gate`):** exclusively physical `target: ["hardware"]` / `["bioware"]` skills automatically require explicit operator approval (`run.approve()`) unless `allow_hardware_execution=True` is set
- **USD cost circuit breaker** via `LimitObserver` (`max_cost_usd` + optional `model_pricing` overrides)

## Run (mock default — no Skillware required)

```bash
python examples/16-skillware-audit-bridge/main.py
```

## Run live with Skillware 0.6.2+

```powershell
$env:SKILLWARE_LIVE = "1"
python examples/16-skillware-audit-bridge/main.py
```

