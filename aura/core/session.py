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
from aura.membrane.ingress import ingress_event_payload
from aura.observers.base import Observer, get_registry


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
    sequencer_spec: dict[str, Any] | None = None
    spine: AuditSpine | None = None
    _engine: ConstraintEngine = field(default_factory=ConstraintEngine)
    _approved: set[str] = field(default_factory=set)
    _observers: list[Observer] = field(default_factory=list)
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
        self._attach_profile_observers()
        self.emit(
            "membrane.ingress",
            ingress_event_payload(self.profile, self.mode.value, self.snapshot_hash),
        )
        self.emit(
            "session.open",
            {
                "mode": self.mode.value,
                "snapshot_hash": self.snapshot_hash,
                "purpose": self.profile.purpose,
                "policy_version": self.profile.policy_version,
                "agent_ref": self.profile.agent_ref,
            },
        )

    def _attach_profile_observers(self) -> None:
        for entry in self.profile.observers:
            if not isinstance(entry, dict):
                continue
            obs_id = entry.get("id")
            if not obs_id:
                continue
            handler = entry.get("handler")
            if callable(handler):
                from aura.observers.base import CallableObserver

                self._observers.append(CallableObserver(obs_id, handler))
            else:
                reg = get_registry()
                obs = reg.get(obs_id)
                if obs:
                    self._observers.append(obs)

    def close(self, reason: str = "normal") -> dict[str, Any]:
        if self._closed:
            return self.state.get("_summary", {})
        if self.spine:
            self.emit("session.close", {"reason": reason, "goal_reached": self._goal_reached})
        self._closed = True
        self._open = False
        return {
            "session_id": self.session_id,
            "log_path": str(self._log_path) if self._log_path else None,
        }

    def emit(
        self,
        kind: str,
        payload: dict[str, Any] | None = None,
        *,
        step_id: str | None = None,
    ) -> dict[str, Any]:
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
            step_id=step_id,
        )
        if constraint_results:
            self.spine.append(
                "constraint.passed",
                {"results": constraint_results, "for_event": event.event_id},
                agent_ids=self.profile.id_trailer(),
            )
        self._dispatch_observers(event.to_dict())
        return event.to_dict()

    def require_approval(
        self,
        request_id: str,
        message: str,
        rule: dict[str, Any],
        *,
        step_id: str | None = None,
    ) -> None:
        """Gate helper — log approval requirement and raise."""
        if request_id in self._approved:
            return
        if self.spine:
            self.spine.append(
                "constraint.approval_required",
                {
                    "request_id": request_id,
                    "message": message,
                    "rule": rule,
                },
                agent_ids=self.profile.id_trailer(),
                step_id=step_id,
            )
        raise ApprovalRequired(request_id, message, rule)

    def approve(self, request_id: str, *, principal: str | None = None) -> None:
        self._approved.add(request_id)
        if self.spine:
            payload: dict[str, Any] = {"request_id": request_id}
            if principal:
                payload["principal"] = principal
            self.spine.append(
                "constraint.approved",
                payload,
                agent_ids=self.profile.id_trailer(),
            )

    def _dispatch_observers(self, event: dict[str, Any]) -> None:
        for obs in self._observers:
            try:
                obs.on_event(event)
            except Exception:
                continue
        get_registry().dispatch(event)

    def register_observer(self, observer: Observer) -> None:
        self._observers.append(observer)

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
            "agent_ref": profile.agent_ref,
            "name": profile.name,
            "purpose": profile.purpose,
            "policy_version": profile.policy_version,
            "variables": profile.variables,
            "rules": rules,
            "skills": profile.skills,
            "sequencer": profile.sequencer,
        },
        sort_keys=True,
    )
    return sha256(blob.encode()).hexdigest()[:16]
