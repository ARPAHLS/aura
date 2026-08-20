# Outputs

What a session produces on close (v0.3).

---

## Per session

| Artifact | Path | Contents |
|---|---|---|
| **Audit trail** | `{session_id}.jsonl` | Append-only AuraEvents with causal ids + hash chain |
| **Summary** | `{session_id}.summary.json` | Metadata, conformance, audit report |
| **OTel JSONL** | `{session_id}.otel.jsonl` | Span-style records mapped from events |

CLI: `aura export`, `aura export-otel`, `aura compare`.

---

## Audit report (summary JSON)

```json
{
  "verdict": "pass",
  "scorecard": { "policy": {}, "tools": {}, "sequencer": {}, "events": 12 },
  "findings": [],
  "recommendations": ["..."],
  "hash_chain_valid": true
}
```

Rule-based today — findings cite `event_id`s; recommendations suggest next steps (policy, sequencer, approvals).

---

## Conformance

Binary pass/fail plus violations list — declared rules and sequencer step order vs observed spine.

---

## Hash chain

Each event includes `prev_hash` and `content_hash` (SHA-256). Tampering or corruption breaks verification in the audit report.

---

## Identity on exports

Summary includes `agent_ref`, `aura_id`, `policy_version`, `snapshot_hash`, and full `agent_ids` trailer.

→ [trust-paths.md](trust-paths.md) · [aura-event.schema.json](../spec/aura-event.schema.json)
