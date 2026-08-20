"""Sequencer engine — delegates to SequencerRunner."""

from __future__ import annotations

from typing import Any

from aura.core.session import Session
from aura.sequencer.runner import DefaultStepBackend, HostStepBackend, SequencerRunner
from aura.sequencer.spec import merge_sequencer_spec


class SequencerEngine:
    """Drive declared multi-step work inside an open session."""

    def __init__(
        self,
        session: Session,
        *,
        host: Any | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.session = session
        merged = merge_sequencer_spec(session.sequencer_spec or session.profile.sequencer, spec)
        if host is not None:
            backend = HostStepBackend(session, host)
        else:
            backend = DefaultStepBackend(session)
        self._runner = SequencerRunner(session, backend, merged)

    def run(self, spec: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._runner.run(spec)
