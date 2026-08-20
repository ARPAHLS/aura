"""Public SDK — configure, agent, session."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from aura.agents.profile import AgentProfile
from aura.agents.registry import AgentRegistry
from aura.config import configure as _configure, get_config
from aura.core.conformance import ConformanceEngine
from aura.core.constraints import ApprovalRequired
from aura.core.session import Session, SessionMode
from aura.exporters.jsonl import export_session


@dataclass
class SessionRun:
    """Active session handle returned from agent.session()."""

    _session: Session
    exports: dict[str, str] = field(default_factory=dict)

    @property
    def session_id(self) -> str:
        return self._session.session_id

    @property
    def aura_id(self) -> str:
        return self._session.profile.aura_id

    def emit(self, kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._session.emit(kind, payload)

    def approve(self, request_id: str) -> None:
        self._session.approve(request_id)

    def complete_goal(self, result: dict[str, Any] | None = None) -> None:
        self._session.complete_goal(result)

    def run_sequencer(
        self,
        spec: dict[str, Any] | None = None,
        *,
        host: Any | None = None,
    ) -> dict[str, Any]:
        from aura.sequencer.engine import SequencerEngine

        engine = SequencerEngine(self._session, host=host, spec=spec)
        return engine.run(spec)


_current_run: ContextVar[SessionRun | None] = ContextVar("aura_current_run", default=None)


def current_session() -> SessionRun | None:
    """Active session inside a `with agent.session()` or `aura run` block."""
    return _current_run.get()


@dataclass
class AgentHandle:
    profile: AgentProfile
    _registry: AgentRegistry

    @contextmanager
    def session(
        self,
        mode: str | None = None,
        *,
        rules: list[dict[str, Any]] | None = None,
        export: bool | None = None,
        sequencer: dict[str, Any] | None = None,
    ) -> Iterator[SessionRun]:
        cfg = get_config()
        session = _build_session(self, mode, rules, sequencer)
        run = SessionRun(_session=session)
        session.open(cfg.sessions_dir())
        token = _current_run.set(run)
        try:
            yield run
        finally:
            _current_run.reset(token)
            session.close()
            do_export = export if export is not None else cfg.values.get("export_on_close", True)
            if do_export and session.spine:
                report = ConformanceEngine().summarize(
                    session.spine,
                    session.rules,
                    session.snapshot_hash,
                    sequencer_spec=session.sequencer_spec or session.profile.sequencer,
                )
                run.exports = export_session(session, cfg.sessions_dir(), conformance=report)


def _build_session(
    agent: AgentHandle,
    mode: str | None,
    rules: list[dict[str, Any]] | None,
    sequencer: dict[str, Any] | None,
) -> Session:
    mode_str = mode or agent.profile.default_mode
    try:
        session_mode = SessionMode(mode_str)
    except ValueError:
        session_mode = SessionMode.SCRIPT
    merged_rules = list(agent.profile.rules)
    if rules:
        merged_rules.extend(rules)
    from aura.sequencer.spec import merge_sequencer_spec

    seq_spec = merge_sequencer_spec(agent.profile.sequencer, sequencer)
    return Session(
        profile=agent.profile,
        mode=session_mode,
        rules=merged_rules,
        sequencer_spec=seq_spec if seq_spec.get("steps") else None,
    )


def configure(project_dir: str | Path | None = None, **overrides: Any) -> Any:
    return _configure(project_dir=project_dir, **overrides)


def agent(
    name: str | None = None,
    *,
    create: bool = True,
    aura_id: str | None = None,
    **profile_kwargs: Any,
) -> AgentHandle:
    """Get or create an agent by name or aura_id."""
    reg = AgentRegistry()
    if aura_id:
        profile = reg.get_by_id(aura_id)
    elif name:
        if create:
            profile = reg.get_or_create(name, **profile_kwargs)
        else:
            profile = reg.get_by_name(name)
    else:
        profile = reg.create(**profile_kwargs)
    return AgentHandle(profile=profile, _registry=reg)


def create_agent(**kwargs: Any) -> AgentHandle:
    reg = AgentRegistry()
    profile = reg.create(**kwargs)
    return AgentHandle(profile=profile, _registry=reg)


def list_agents(include_archived: bool = False) -> list[AgentProfile]:
    return AgentRegistry().list_agents(include_archived=include_archived)


__all__ = [
    "configure",
    "agent",
    "create_agent",
    "list_agents",
    "AgentHandle",
    "SessionRun",
    "ApprovalRequired",
    "current_session",
]
