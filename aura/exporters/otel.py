"""Map AuraEvent stream to OpenTelemetry-style span records (JSON)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aura.core.spine import AuditSpine


def events_to_spans(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for event in events:
        spans.append(
            {
                "trace_id": event.get("trace_id"),
                "span_id": event.get("event_id"),
                "parent_span_id": event.get("parent_id"),
                "name": event.get("kind"),
                "start_time_unix_nano": None,
                "attributes": {
                    "aura.session_id": event.get("session_id"),
                    "aura.aura_id": event.get("aura_id"),
                    "aura.step_id": event.get("step_id"),
                    "aura.agent_ids": json.dumps(event.get("agent_ids") or {}),
                    "aura.payload": json.dumps(event.get("payload") or {}),
                },
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
    events = AuditSpine.read_jsonl(log_path)
    out_path = sessions_dir / f"{session_id}.otel.jsonl"
    return export_otel_jsonl(events, out_path)
