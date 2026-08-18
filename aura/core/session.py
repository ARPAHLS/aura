"""Session lifecycle — open, run, close with modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import uuid

from aura.agents.profile import AgentProfile
from aura.core.constraints import (
    ApprovalRequired,
    ConstraintContext,
    ConstraintEngine,
    ConstraintViolation,
)
from aura.core.spine import AuditSpine


class SessionMode(str, Enum):
    SCRIPT = "script"
    TASK = "task"
    CONTINUOUS = "continuous"


@dataclass
class Session:
    """One runtime activation of an agent."""

    profile: AgentProfile
    mode: SessionMode = SessionMode.SCRIPT
    session_id: str = field(default_factory=lambda: f"aura_sess_{uuid.uuid4().hex[:12]}")
    task_id: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
    snapshot_hash: str | None = None
    rules: list[dict[str, Any]] = field(default_factory=list)
    spine: AuditSpine | None = None
    _engine: ConstraintEngine = field(default_factory=ConstraintEngine)
    _approved: set[str] = field(default_factory=set)
    _open: bool = False
    _closed: bool = False
    _log_path: Path | None = None
    _goal_reached: bool = False

    def open(self, sessions_dir: Path) -> None:
        if self._open:
            return
        self.snapshot_hash = _snapshot_hash(self.profile, self.rules)
        self._log_path = sessions_dir / f"{self.session_id}.jsonl"
        self.spine = AuditSpine(
            session_id=self.session_id,
            aura_id=self.profile.aura_id,
            log_path=self._log_path,
        )
        self._open = True
        self.emit(
            "session.open",
            {
                "mode": self.mode.value,
                "snapshot_hash": self.snapshot_hash,
                "purpose": self.profile.purpose,
            },
        )

    def close(self, reason: str = "normal") -> dict[str, Any]:
        if self._closed:
            return self.state.get("_summary", {})
        if self.spine:
            self.emit("session.close", {"reason": reason, "goal_reached": self._goal_reached})
        self._closed = True
        self._open = False
        return {"session_id": self.session_id, "log_path": str(self._log_path) if self._log_path else None}

    def emit(self, kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.spine:
            raise RuntimeError("Session not open")
        ctx = ConstraintContext(
            event_kind=kind,
            payload=dict(payload or {}),
            rules=self.rules,
            session_state=self.state,
            approved_requests=self._approved,
        )
        constraint_results: list[dict[str, Any]] = []
        try:
            results = self._engine.check_emit(ctx)
            constraint_results = [
                {"passed": r.passed, "message": r.message, "rule": r.rule} for r in results
            ]
        except ApprovalRequired as exc:
            self.spine.append(
                "constraint.approval_required",
                {
                    "request_id": exc.request_id,
                    "message": str(exc),
                    "rule": exc.rule,
                    "pending_event": {"kind": kind, "payload": payload or {}},
                },
                agent_ids=self.profile.id_trailer(),
            )
            raise
        except ConstraintViolation as exc:
            self.spine.append(
                "constraint.violated",
                {"message": str(exc), "rule": exc.rule, "event": exc.event},
                agent_ids=self.profile.id_trailer(),
            )
            raise

        event = self.spine.append(
            kind,
            payload or {},
            agent_ids=self.profile.id_trailer(),
            task_id=self.task_id,
        )
        if constraint_results:
            self.spine.append(
                "constraint.passed",
                {"results": constraint_results, "for_event": event.event_id},
                agent_ids=self.profile.id_trailer(),
            )
        return event.to_dict()

    def approve(self, request_id: str) -> None:
        self._approved.add(request_id)
        if self.spine:
            self.spine.append(
                "constraint.approved",
                {"request_id": request_id},
                agent_ids=self.profile.id_trailer(),
            )

    def complete_goal(self, result: dict[str, Any] | None = None) -> None:
        """Signal task completion (task mode)."""
        self._goal_reached = True
        self.emit("task.complete", result or {})

    @property
    def log_path(self) -> Path | None:
        return self._log_path

    @property
    def is_open(self) -> bool:
        return self._open and not self._closed


def _snapshot_hash(profile: AgentProfile, rules: list[dict[str, Any]]) -> str:
    blob = json.dumps(
        {
            "aura_id": profile.aura_id,
            "name": profile.name,
            "purpose": profile.purpose,
            "variables": profile.variables,
            "rules": rules,
        },
        sort_keys=True,
    )
    return sha256(blob.encode()).hexdigest()[:16]
