# Outputs

What a session produces on close (v0.3).

Identity fields on export: [trust-paths.md](trust-paths.md). Session-close workflow: [using-aura.md](using-aura.md).

---

## Per session

| Artifact | Path | Contents |
|---|---|---|
| **Audit trail** | `{session_id}.jsonl` | Append-only AuraEvents with causal ids + hash chain |
| **Summary** | `{session_id}.summary.json` | Metadata, conformance, audit report |
| **OTel JSONL** | `{session_id}.otel.jsonl` | Span-style records mapped from events; written on close by default and refreshed by `aura export-otel` |

CLI: `aura report show <session_id>`, `aura report show <session_id> --json`, `aura export`, `aura export-otel`, `aura compare`, `aura verify chain <path>`.

**Export commit:** Summary and OTel files are written to staging paths and renamed atomically on success. If export fails, neither artifact is committed (the live JSONL trail may still exist from the session). With `export=False`, the SDK still builds `run.summary` and `run.audit_report` in memory.

**Closed session:** After close, `emit`, `approve`, and a second `close()` raise `SessionClosedError`. `session_id` and `trace_id` are fixed at open. `open_snapshot_hash` captures rules + sequencer at open for conformance; `snapshot_hash` in the summary may update when skills bind at runtime.

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

Use `aura report show` for a human-readable audit report from the session summary JSON, or add `--json` for CI and other machine consumers. See [using-aura.md](using-aura.md) for the complete session-close workflow.

---

## Conformance

Binary pass/fail plus violations list — declared rules and sequencer step order vs observed spine.

---

## Hash chain

Each event includes `prev_hash` and `content_hash` (SHA-256). Tampering or corruption breaks verification in the audit report.

Use `aura verify chain <path>` to validate an exported JSONL audit trail directly. It prints a JSON object with `hash_chain_valid`; when the chain is broken, the object also identifies the first affected `event_id` and the command exits with status 1.

---

## Identity on exports

Summary includes `agent_ref`, `aura_id`, `policy_version`, `snapshot_hash`, and full `agent_ids` trailer.

## OTel spans

`aura export-otel` writes `{session_id}.otel.jsonl`. Spans inherit promoted attributes where available:

- `aura.agent_ref`, `aura.policy_version` — session identity
- `aura.principal` — approver on gated calls
- `aura.skill_id` — skill on tool and registration events

→ [trust-paths.md](trust-paths.md) · [aura-event.schema.json](../spec/aura-event.schema.json) · [reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md)
