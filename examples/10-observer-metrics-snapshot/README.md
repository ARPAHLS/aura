# Example 10 — Observer metrics snapshot (tailored coat)

**AURA-native** tailored-coat pattern — no third-party KPI skills required.

| Piece | Role |
|---|---|
| **Monitor preset** | Aggregates tool calls and timing on the spine |
| **`metrics_snapshot` note** | Structured payload at session close for playbooks / export consumers |
| **Session export** | `.summary.json` + JSONL for external schedulers (optional) |

Use when you need lightweight metrics before **goal/SLO presets** ([#46](https://github.com/ARPAHLS/aura/issues/46) — see [example 11](../11-scheduled-agent-slo/)), **Limit** preset (shipped via [#77](https://github.com/ARPAHLS/aura/issues/77) — see [example 07](../07-observer-presets/)), or escalation playbooks ([#47](https://github.com/ARPAHLS/aura/issues/47)). Third-party registry skills may *read* the export later; AURA enforcement stays on **observers + egress rules**.

```powershell
.venv\Scripts\activate
python examples/10-observer-metrics-snapshot/main.py
```

→ [07-observer-presets](../07-observer-presets/) · [using-aura.md](../../docs/using-aura.md) · [aura-levels.md](../../docs/aura-levels.md)
