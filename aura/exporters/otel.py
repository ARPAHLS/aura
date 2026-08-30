"""Map AuraEvent stream to OpenTelemetry-style span records (JSON)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aura.core.spine import AuditSpine


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
        spans.append(
            {
                "trace_id": event.get("trace_id"),
                "span_id": event.get("event_id"),
                "parent_span_id": event.get("parent_id"),
                "name": event.get("kind"),
                "start_time_unix_nano": None,
                "attributes": attributes,
                "status": {"code": "OK"},
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
