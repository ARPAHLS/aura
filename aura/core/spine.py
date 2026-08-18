"""Append-only AuraEvent audit spine."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class AuraEvent:
    kind: str
    session_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    step_id: str | None = None
    task_id: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    telemetry: dict[str, Any] = field(default_factory=dict)


class AuditSpine:
    """In-memory event log — durable backend pluggable later."""

    def __init__(self) -> None:
        self._events: list[AuraEvent] = []

    def append(self, event: AuraEvent) -> AuraEvent:
        self._events.append(event)
        return event

    def stream(self) -> list[AuraEvent]:
        return list(self._events)
