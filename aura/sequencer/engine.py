"""Sequencer engine — ordered step pipelines inside a session."""

from typing import Any

from aura.core.session import Session
from aura.core.spine import AuditSpine, AuraEvent
from aura.sequencer.middleware import MiddlewarePolicy, MiddlewareStack
from aura.sequencer.step import SequencerStep


class SequencerEngine:
    """Drive declared multi-step work; emit per-step telemetry on the audit spine."""

    def __init__(self, session: Session, spine: AuditSpine) -> None:
        self.session = session
        self.spine = spine
        middleware = MiddlewarePolicy.from_manifest(session.manifest)
        self.middleware = MiddlewareStack(middleware) if middleware else None

    def load_steps(self) -> list[SequencerStep]:
        raw = (self.session.manifest.get("sequencer") or {}).get("steps") or []
        return [
            SequencerStep(
                id=s["id"],
                step_type=s["type"],
                ref=s.get("ref"),
                version=s.get("version"),
                depends_on=list(s.get("depends_on") or []),
                retry=dict(s.get("retry") or {}),
                gates=list(s.get("gates") or []),
                config=dict(s.get("config") or {}),
            )
            for s in raw
        ]

    def run(self) -> None:
        steps = self.load_steps()
        trace_id = self.session.session_id
        for step in steps:
            self.spine.append(
                AuraEvent(
                    kind="sequencer.step.start",
                    session_id=self.session.session_id,
                    step_id=step.id,
                    trace_id=trace_id,
                    payload={"type": step.step_type, "ref": step.ref},
                )
            )
            ctx: dict[str, Any] = {"step": step, "state": self.session.state}
            if self.middleware:
                ctx = self.middleware.run_inbound(ctx)
            self.spine.append(
                AuraEvent(
                    kind="sequencer.step.end",
                    session_id=self.session.session_id,
                    step_id=step.id,
                    trace_id=trace_id,
                    payload={"status": "pending"},
                )
            )
