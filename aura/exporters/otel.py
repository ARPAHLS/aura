"""Map AuraEvent stream to OpenTelemetry-style span records (JSON)."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from aura.core.spine import AuditSpine

_ERROR_EVENT_KINDS = frozenset(
    {"tool.error", "constraint.violated", "skill.egress_bypass", "skill.manifest_invalid"}
)


def _timestamp_to_unix_nano(ts: Any) -> int | None:
    if not isinstance(ts, str) or not ts.strip():
        return None
    try:
        dt = datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))
        return int(dt.timestamp() * 1_000_000_000)
    except ValueError:
        return None


def _promoted_attributes(event: dict[str, Any]) -> dict[str, Any]:
    """First-class identity fields for SIEM parity with the JSONL spine."""
    attrs: dict[str, Any] = {}
    agent_ids = event.get("agent_ids") or {}
    payload = event.get("payload") or {}
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}

    policy_version = (
        payload.get("policy_version")
        or agent_ids.get("policy_version")
        or context.get("policy_version")
    )
    if policy_version is not None:
        attrs["aura.policy_version"] = str(policy_version)

    agent_ref = payload.get("agent_ref") or context.get("agent_ref")
    if agent_ref:
        attrs["aura.agent_ref"] = str(agent_ref)

    principal = payload.get("principal")
    if principal:
        attrs["aura.principal"] = str(principal)

    skill_id = payload.get("skill_id")
    if skill_id:
        attrs["aura.skill_id"] = str(skill_id)

    manifest_hash = payload.get("manifest_snapshot_hash")
    if manifest_hash:
        attrs["aura.manifest_snapshot_hash"] = str(manifest_hash)

    step_id = event.get("step_id") or payload.get("step_id")
    if step_id:
        attrs["aura.step_id"] = str(step_id)

    ids = agent_ids.get("ids") if isinstance(agent_ids.get("ids"), dict) else {}
    operator = ids.get("operator") if isinstance(ids, dict) else None
    if isinstance(operator, dict):
        if operator.get("verified") is not None:
            attrs["aura.operator.verified"] = str(operator["verified"]).lower()
        if operator.get("method"):
            attrs["aura.operator.method"] = str(operator["method"])
        if operator.get("subject"):
            attrs["aura.operator.subject"] = str(operator["subject"])
        if operator.get("subject_hash"):
            attrs["aura.operator.subject_hash"] = str(operator["subject_hash"])

    telemetry = event.get("telemetry") if isinstance(event.get("telemetry"), dict) else {}
    if telemetry.get("latency_ms") is not None:
        attrs["aura.latency_ms"] = float(telemetry["latency_ms"])
    elif payload.get("duration_ms") is not None:
        attrs["aura.latency_ms"] = float(payload["duration_ms"])

    model = telemetry.get("model") or payload.get("model")
    if model:
        attrs["aura.model"] = str(model)
        attrs["gen_ai.request.model"] = str(model)
    if telemetry.get("prompt_tokens") is not None:
        attrs["gen_ai.usage.input_tokens"] = int(telemetry["prompt_tokens"])
    if telemetry.get("completion_tokens") is not None:
        attrs["gen_ai.usage.output_tokens"] = int(telemetry["completion_tokens"])
    if payload.get("tool") and str(event.get("kind") or "").startswith("tool."):
        attrs["gen_ai.tool.name"] = str(payload["tool"])
    if telemetry.get("estimated_cost_usd") is not None:
        attrs["aura.estimated_cost_usd"] = float(telemetry["estimated_cost_usd"])
    if telemetry.get("provenance_hash") or payload.get("provenance_hash"):
        attrs["aura.provenance_hash"] = str(
            telemetry.get("provenance_hash") or payload.get("provenance_hash")
        )
    if telemetry.get("skillware_event_hash") or payload.get("skillware_event_hash"):
        attrs["aura.skillware_event_hash"] = str(
            telemetry.get("skillware_event_hash") or payload.get("skillware_event_hash")
        )
    if payload.get("error_type"):
        attrs["aura.error_type"] = str(payload["error_type"])
        attrs["error.type"] = str(payload["error_type"])
    if "egress_guarded" in payload:
        attrs["aura.egress_guarded"] = str(bool(payload["egress_guarded"])).lower()

    taxonomy = payload.get("taxonomy") if isinstance(payload.get("taxonomy"), dict) else {}
    if taxonomy.get("shape"):
        attrs["aura.skill_shape"] = str(taxonomy["shape"])
    if taxonomy.get("tier"):
        attrs["aura.skill_tier"] = str(taxonomy["tier"])
    if taxonomy.get("target"):
        targets = taxonomy["target"]
        attrs["aura.skill_target"] = (
            ",".join(str(t) for t in targets) if isinstance(targets, list) else str(targets)
        )

    return attrs


def redact_events_for_export(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from aura.identity.redaction import redact_agent_ids

    redacted: list[dict[str, Any]] = []
    for event in events:
        copy_event = dict(event)
        if "agent_ids" in copy_event:
            copy_event["agent_ids"] = redact_agent_ids(copy_event.get("agent_ids"))
        redacted.append(copy_event)
    return redacted


def events_to_spans(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for event in events:
        promoted = _promoted_attributes(event)
        attributes = {
            "aura.session_id": event.get("session_id"),
            "aura.aura_id": event.get("aura_id"),
            "aura.step_id": event.get("step_id"),
            "aura.agent_ids": json.dumps(event.get("agent_ids") or {}),
            "aura.payload": json.dumps(event.get("payload") or {}),
            **promoted,
        }
        kind = str(event.get("kind") or "")
        payload = event.get("payload") or {}
        is_error = (kind in _ERROR_EVENT_KINDS) or (
            isinstance(payload, dict) and payload.get("status") == "error"
        )
        spans.append(
            {
                "trace_id": event.get("trace_id"),
                "span_id": event.get("event_id"),
                "parent_span_id": event.get("parent_id"),
                "name": event.get("kind"),
                "start_time_unix_nano": _timestamp_to_unix_nano(event.get("timestamp")),
                "attributes": attributes,
                "status": {"code": "ERROR" if is_error else "OK"},
            }
        )
    return spans


def export_otel_jsonl(events: list[dict[str, Any]], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for span in events_to_spans(events):
            f.write(json.dumps(span, ensure_ascii=False) + "\n")
    return out_path


def export_session_otel(session_id: str, sessions_dir: Path) -> Path:
    log_path = sessions_dir / f"{session_id}.jsonl"
    events = redact_events_for_export(AuditSpine.read_jsonl(log_path))
    out_path = sessions_dir / f"{session_id}.otel.jsonl"
    return export_otel_jsonl(events, out_path)
