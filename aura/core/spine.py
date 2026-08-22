"""Append-only AuraEvent audit spine with JSONL persistence and hash chain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator
import json
import uuid


def _canonical_event_body(event: "AuraEvent") -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "parent_id": event.parent_id,
        "trace_id": event.trace_id,
        "span_id": event.span_id,
        "step_id": event.step_id,
        "task_id": event.task_id,
        "session_id": event.session_id,
        "aura_id": event.aura_id,
        "agent_ids": event.agent_ids,
        "kind": event.kind,
        "timestamp": event.timestamp,
        "payload": event.payload,
        "telemetry": event.telemetry,
    }


def compute_content_hash(event: "AuraEvent", prev_hash: str | None) -> str:
    blob = json.dumps(_canonical_event_body(event), sort_keys=True, ensure_ascii=False)
    prefix = prev_hash or "genesis"
    return sha256(f"{prefix}:{blob}".encode()).hexdigest()


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
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    telemetry: dict[str, Any] = field(default_factory=dict)
    prev_hash: str | None = None
    content_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = _canonical_event_body(self)
        data["prev_hash"] = self.prev_hash
        data["content_hash"] = self.content_hash
        return data


class AuditSpine:
    """Append-only log — in-memory with optional JSONL file backend."""

    def __init__(self, session_id: str, aura_id: str, log_path: Path | None = None) -> None:
        self.session_id = session_id
        self.aura_id = aura_id
        self.log_path = log_path
        self._events: list[AuraEvent] = []
        self._last_event_id: str | None = None
        self._last_content_hash: str | None = None
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
        event.prev_hash = self._last_content_hash
        event.content_hash = compute_content_hash(event, self._last_content_hash)
        self._events.append(event)
        self._last_event_id = event.event_id
        self._last_content_hash = event.content_hash
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

    @classmethod
    def from_jsonl(
        cls,
        path: Path,
        *,
        session_id: str | None = None,
        aura_id: str | None = None,
    ) -> "AuditSpine":
        """Rebuild an in-memory spine from a JSONL log (for verify / tamper checks)."""
        rows = cls.read_jsonl(path)
        sid = session_id or (rows[0].get("session_id") if rows else "unknown")
        aid = aura_id or (rows[0].get("aura_id") if rows else "unknown")
        spine = cls(str(sid), str(aid), log_path=None)
        if rows:
            spine.trace_id = rows[0].get("trace_id") or spine.trace_id
        for row in rows:
            event = AuraEvent(
                kind=row["kind"],
                session_id=str(row.get("session_id", sid)),
                aura_id=str(row.get("aura_id", aid)),
                payload=dict(row.get("payload") or {}),
                event_id=row["event_id"],
                parent_id=row.get("parent_id"),
                trace_id=row.get("trace_id"),
                span_id=row.get("span_id"),
                step_id=row.get("step_id"),
                task_id=row.get("task_id"),
                agent_ids=dict(row.get("agent_ids") or {}),
                timestamp=row.get("timestamp") or "",
                telemetry=dict(row.get("telemetry") or {}),
            )
            event.prev_hash = row.get("prev_hash")
            event.content_hash = row.get("content_hash")
            spine._events.append(event)
            spine._last_event_id = event.event_id
            spine._last_content_hash = event.content_hash
        return spine


def verify_hash_chain(spine: AuditSpine) -> bool | None:
    """Return True if chain valid, False if broken, None if no hashes recorded."""
    prev: str | None = None
    saw_hash = False
    for event in spine.stream():
        if event.content_hash is None:
            continue
        saw_hash = True
        expected = compute_content_hash(event, prev)
        if event.content_hash != expected:
            return False
        prev = event.content_hash
    return True if saw_hash else None


def first_broken_event_id(spine: AuditSpine) -> str | None:
    """Return the first event_id whose content hash does not match the chain."""
    prev: str | None = None
    for event in spine.stream():
        if event.content_hash is None:
            continue
        if compute_content_hash(event, prev) != event.content_hash:
            return event.event_id
        prev = event.content_hash
    return None


def verify_hash_chain_dicts(events: list[dict[str, Any]]) -> bool | None:
    prev: str | None = None
    saw_hash = False
    for row in events:
        content_hash = row.get("content_hash")
        if content_hash is None:
            continue
        saw_hash = True
        event = AuraEvent(
            kind=row["kind"],
            session_id=row["session_id"],
            aura_id=row["aura_id"],
            payload=dict(row.get("payload") or {}),
            event_id=row["event_id"],
            parent_id=row.get("parent_id"),
            trace_id=row.get("trace_id"),
            span_id=row.get("span_id"),
            step_id=row.get("step_id"),
            task_id=row.get("task_id"),
            agent_ids=dict(row.get("agent_ids") or {}),
            timestamp=row.get("timestamp") or "",
            telemetry=dict(row.get("telemetry") or {}),
        )
        expected = compute_content_hash(event, prev)
        if content_hash != expected:
            return False
        prev = content_hash
    return True if saw_hash else None
