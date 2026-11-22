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
| **Signed pack** (opt-in) | `{session_id}.pack.json` | Detached HMAC-SHA256 / Ed25519 signature over `chain_root` and artifact SHA-256 digests ([#50](https://github.com/ARPAHLS/aura/issues/50)); verify via `aura verify pack <path> [--key <key> \| --keyring <path>]` |

CLI: `aura report show <session_id>`, `aura report show <session_id> --json`, `aura export`, `aura export-otel`, `aura compare`, `aura verify chain <path>`, `aura verify pack <path>`.

**Export commit:** Summary and OTel files are written to staging paths and renamed atomically on success. If export fails, neither artifact is committed (the live JSONL trail may still exist from the session). With `export=False`, the SDK still builds `run.summary` and `run.audit_report` in memory.

**Closed session:** After close, `emit`, `approve`, and a second `close()` raise `SessionClosedError`. `session_id` and `trace_id` are fixed at open. `open_snapshot_hash` captures rules + sequencer at open for conformance; `snapshot_hash` in the summary may update when skills bind at runtime.

**Spine events (identity):** When an operator adapter binds, the session emits `identity.bound` after `session.open`. Operator fields appear under `agent_ids.ids.operator` on subsequent events. JSONL retains full fields; summary and OTel apply [redaction defaults](../integrations/identity/README.md).

**Spine events (escalation & coat ops):** When `profile.escalations[]` is set, trigger events (`slo.missed`, `conformance.drift`, `observer.alert`, `constraint.violated`) may emit `escalation.fired` and action events (`membrane.nudge`, `escalation.email`, `escalation.wake`). With `coat_ops` configured (`WebhookCoatOp`, `SmtpCoatOp`, `CallableCoatOp`, or `AURA_COAT_WEBHOOK_URL`), `escalation.email` and `escalation.wake` record `delivery: "sent"` (or `"failed"` with `delivery_error`); otherwise `"stub"`. Membrane-level scans via `CoatOpRunner` emit `coat.op.executed`. See [observers.md](observers.md#3-escalation-playbooks--profileescalations-47).

**Spine events (spectrum):** `session.open` and `membrane.ingress` carry a `spectrum` summary when the profile has a `spectrum` block. `session.open` also includes `services_activation` — which presets wired at open (`activated`, `skipped_explicit`, `unknown`) — and `verified_identity_required` + source when the verified-ID gate applies ([#73](https://github.com/ARPAHLS/aura/issues/73)). See [aura-levels.md](aura-levels.md).

**Spine events (capabilities):** When `profile.capabilities[]` is set, `session.open` spectrum summary includes a capabilities block (`count`, `ids`, `gated_tools`, `secret_refs`, broker kind). Scope misses emit `constraint.violated` (with `audit_only` at spectrum `low`). `constraint.passed` lists only rules that passed. Successful inject emits `capability.injected` (capability id + secret **refs** and targets in `injected[]`, never values; [#86](https://github.com/ARPAHLS/aura/issues/86)). Secret-like payload keys (`token`, `api_key`, …) are redacted on every emit, including sessions without capabilities. Findings: `CAPABILITY_DENIED`, `CAPABILITY_AUDIT`, `SECRET_BROKER_ERROR`. See [capabilities.md](capabilities.md).

**Spine events (schema):** When `variables.schema_refs` or `schema_check` rules are active, `session.open` spectrum summary includes a `schema` block (`refs`, `active_rules`, `auto_enforced`). Malformed `tool.call` args or `tool.result` payloads emit `constraint.violated`. Audit finding: **`SCHEMA_VIOLATION`**. Conformance includes a `schema` check on close. See [aura-levels.md](aura-levels.md#profile-spec).

**Spine events (middleware & PII masking):** When sequencer steps or boundaries execute middleware (e.g. `middleware.pii_mask` [#58](https://github.com/ARPAHLS/aura/issues/58)), the session emits `middleware.applied` containing detection counts (`entities_detected`), total redactions, strategy (`redact`, `mask`, `pseudonymize`), and modified fields. Raw PII is strictly forbidden from the spine. Audit scorecard records `scorecard.middleware = {"applied": count, "pii_redactions": count}` and surfaces finding **`PII_MASKED`** (`severity: info`). See [sequencer.md](sequencer.md#middleware-pii-masking).

**Spine events (break preset & observer alerts):** When observer presets (such as `break` [#93](https://github.com/ARPAHLS/aura/issues/93)) detect runaway cycles or repetition, the session emits `observer.alert` containing pattern (`ACTION_FIXATION`, `OSCILLATION_CYCLE`, `CHOREOGRAPHY_CYCLE`, `ERROR_STATUS_CHURN`, `REASONING_INERTIA`), structured `remedial_directive`, and non-repudiable cryptographic hashes (`cycle_entry_hash`, `cycle_recurrence_hash`). Audit scorecard records `scorecard.observers = {"alerts": count, "loop_cycles": count}` and surfaces finding **`COGNITIVE_CYCLE_DETECTED`** (`severity: warn`). See [observers.md](observers.md#break).

**Spine events (Skillware 0.6.2+ dispatch bridge, FinOps & Manifest v2):** `guarded_tool_call` and `guarded_tool_call_async` attach structured `telemetry` (`latency_ms`, `skill_id`, `skill_version`, `model`, `prompt_tokens`, `completion_tokens`, `estimated_cost_usd`, `provenance_hash`, `skillware_event_hash`) and `span_id` on `tool.result` and `tool.error` (plus `error_type`). Bridged `SkillContext` dispatches emit `skill.dispatch` with `egress_guarded: true|false`; out-of-band calls bypassing egress also emit `skill.egress_bypass` and surface **`UNGUARDED_SKILL_DISPATCH`** (`severity: high`). Manifest v2 binding records `taxonomy`, `manifest_validation`, `deprecated`, and `physical_target` on `skill.registered` (or `skill.manifest_invalid` in strict mode), surfacing findings **`MANIFEST_SCHEMA_INVALID`**, **`SKILL_DEPRECATED`**, and **`PHYSICAL_TARGET_REGISTERED`**. Audit scorecard includes `scorecard.finops` (prompt/completion tokens, total USD spend, cost by model and skill, latency stats) and `scorecard.skillware`. Dual-ledger logs (AURA JSONL + Skillware JSONL) can be cross-verified offline via `verify_dual_audit_chain(aura_jsonl, skillware_jsonl)`. See [skillware-integration.md](skillware-integration.md).


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

Binary pass/fail plus violations list — declared rules, sequencer step order, goal/SLO drift, and schema rule violations vs observed spine.

---

## Hash chain

Each event includes `prev_hash` and `content_hash` (SHA-256). Tampering or corruption breaks verification in the audit report.

Use `aura verify chain <path>` to validate an exported JSONL audit trail directly. Pass `--skillware-log <skillware_audit.jsonl>` to run optional dual-ledger cross-verification against a Skillware hash-chained log. It prints a JSON object with `hash_chain_valid`; when the chain is broken, the object also identifies the first affected `event_id` (or dual-ledger mismatch details) and the command exits with status 1.

Use `aura verify pack <path>` (or `verify_audit_pack(pack_path, key=..., keyring=...)`) to verify a signed `.pack.json` bundle offline. Pass `--key <secret-or-ref>` (defaults to `AURA_SIGNING_KEY`) for single-key verification, or `--keyring <keyring.json>` (a JSON object mapping `key_id` to a secret/PEM string, `SecretBroker` ref, or key file path) to resolve rotated keys by the pack's `key_id` ([#101](https://github.com/ARPAHLS/aura/issues/101)). Keyring mode fails closed when `key_id` is missing or not found in the keyring.

---

## Identity on exports

Summary includes `agent_ref`, `aura_id`, `policy_version`, `snapshot_hash`, and full `agent_ids` trailer.

## OTel spans

`aura export-otel` writes `{session_id}.otel.jsonl`. Spans inherit promoted attributes where available:

- `aura.agent_ref`, `aura.policy_version` — session identity
- `aura.principal` — approver on gated calls
- `aura.operator.subject`, `aura.operator.method`, `aura.operator.verified` — session operator when identity adapter bound
- `aura.skill_id`, `aura.skill_shape`, `aura.skill_tier`, `aura.skill_target` — skill identity and Manifest v2 taxonomy on registration/tool events
- `aura.latency_ms`, `aura.model`, `aura.estimated_cost_usd` — FinOps and execution latency telemetry
- `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.tool.name`, `error.type` — OpenTelemetry GenAI semantic conventions alongside `aura.*`
- `aura.provenance_hash`, `aura.skillware_event_hash`, `aura.egress_guarded`, `aura.error_type` — Skillware provenance, dual-ledger anchor, and egress/error metadata
- `status.code` (`ERROR` on `tool.error`, `constraint.violated`, `skill.egress_bypass`, `skill.manifest_invalid`; `OK` otherwise) and ISO-8601 `start_time_unix_nano`

→ [trust-paths.md](trust-paths.md) · [aura-event.schema.json](../spec/aura-event.schema.json) · [reference-tool-host-capstone.md](guides/reference-tool-host-capstone.md)
