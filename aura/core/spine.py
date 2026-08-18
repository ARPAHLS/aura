"""Append-only AuraEvent audit spine with JSONL persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
import json
import uuid


@dataclass
class AuraEvent:
    kind: str
    session_id: str
    aura_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    step_id: str | None = None
    task_id: str | None = None
    agent_ids: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    telemetry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "parent_id": self.parent_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "step_id": self.step_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "aura_id": self.aura_id,
            "agent_ids": self.agent_ids,
            "kind": self.kind,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "telemetry": self.telemetry,
        }


class AuditSpine:
    """Append-only log — in-memory with optional JSONL file backend."""

    def __init__(self, session_id: str, aura_id: str, log_path: Path | None = None) -> None:
        self.session_id = session_id
        self.aura_id = aura_id
        self.log_path = log_path
        self._events: list[AuraEvent] = []
        self._last_event_id: str | None = None
        self.trace_id = uuid.uuid4().hex
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        kind: str,
        payload: dict[str, Any] | None = None,
        *,
        agent_ids: dict[str, Any] | None = None,
        parent_id: str | None = None,
        step_id: str | None = None,
        task_id: str | None = None,
        telemetry: dict[str, Any] | None = None,
    ) -> AuraEvent:
        event = AuraEvent(
            kind=kind,
            session_id=self.session_id,
            aura_id=self.aura_id,
            payload=dict(payload or {}),
            parent_id=parent_id or self._last_event_id,
            trace_id=self.trace_id,
            step_id=step_id,
            task_id=task_id,
            agent_ids=dict(agent_ids or {}),
            telemetry=dict(telemetry or {}),
        )
        self._events.append(event)
        self._last_event_id = event.event_id
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def stream(self) -> list[AuraEvent]:
        return list(self._events)

    def iter_dicts(self) -> Iterator[dict[str, Any]]:
        for event in self._events:
            yield event.to_dict()

    @classmethod
    def read_jsonl(cls, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        events: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events
