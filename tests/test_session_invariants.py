"""Session lifecycle and export invariant tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from aura import agent
from aura.core.errors import ExportError, SessionAlreadyOpenError, SessionClosedError
from aura.core.session import Session, SessionMode, _snapshot_hash
from aura.exporters.jsonl import export_session


def test_export_false_builds_in_memory_summary(aura_home: Path):
    ag = agent("inv-no-export")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
        trace_id = run.trace_id
    assert run.summary is not None
    assert run.audit_report is not None
    assert run.summary["session_id"] == run.session_id
    assert run.summary["trace_id"] == trace_id
    assert run.summary["snapshot_hash"] == run._session.snapshot_hash
    assert run.summary["open_snapshot_hash"] == run._session.open_snapshot_hash
    assert run.exports == {}
    assert not (aura_home / "sessions" / f"{run.session_id}.summary.json").exists()


def test_export_true_writes_all_artifacts(aura_home: Path):
    ag = agent("inv-export")
    with ag.session() as run:
        run.emit("turn.start", {})
    sessions = aura_home / "sessions"
    sid = run.session_id
    assert (sessions / f"{sid}.jsonl").is_file()
    assert (sessions / f"{sid}.summary.json").is_file()
    assert (sessions / f"{sid}.otel.jsonl").is_file()
    assert run.summary is not None
    assert run.audit_report == run.summary.get("audit_report")


def test_double_close_raises(aura_home: Path):
    ag = agent("inv-double-close")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
    with pytest.raises(SessionClosedError):
        run._session.close()


def test_emit_after_close_raises(aura_home: Path):
    ag = agent("inv-emit-after")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
    with pytest.raises(SessionClosedError):
        run.emit("turn.end", {})


def test_double_open_raises(aura_home: Path):
    ag = agent("inv-double-open")
    session = Session(profile=ag.profile, mode=SessionMode.SCRIPT)
    session.open(aura_home / "sessions")
    with pytest.raises(SessionAlreadyOpenError):
        session.open(aura_home / "sessions")
    session.close()


def test_session_id_immutable_after_open(aura_home: Path):
    ag = agent("inv-immutable-id")
    session = Session(profile=ag.profile, mode=SessionMode.SCRIPT)
    session.open(aura_home / "sessions")
    with pytest.raises(AttributeError):
        session.session_id = "aura_sess_override"
    session.close()


def test_trace_id_stable_for_session(aura_home: Path):
    ag = agent("inv-trace")
    with ag.session(export=False) as run:
        first = run.trace_id
        run.emit("turn.start", {})
        assert run.trace_id == first
    assert run.summary["trace_id"] == first


def test_snapshot_hash_matches_conformance_when_rules_unchanged(aura_home: Path):
    ag = agent("inv-snapshot", rules=[{"type": "allow", "tools": ["search"]}])
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
        open_hash = run._session.open_snapshot_hash
    assert run.conformance is not None
    assert run.conformance.snapshot_hash == open_hash
    assert run.summary["open_snapshot_hash"] == open_hash


def test_declared_rules_frozen_after_open(aura_home: Path):
    ag = agent("inv-rules-freeze", rules=[{"type": "allow", "tools": ["search"]}])
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
        original_hash = run._session.open_snapshot_hash
        run._session.rules.append({"type": "deny", "tools": ["delete"]})
        assert run._session.open_snapshot_hash == original_hash
        assert len(run._session.declared_rules) == 1
    assert run.conformance is not None
    assert len(run.conformance.declared_rules) == 1


def test_export_atomic_on_otel_failure(aura_home: Path, monkeypatch: pytest.MonkeyPatch):
    ag = agent("inv-export-fail")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})

    sessions = aura_home / "sessions"
    sid = run.session_id

    def _boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("aura.exporters.jsonl._write_staging_otel", _boom)
    with pytest.raises(ExportError):
        export_session(run._session, sessions)

    assert (sessions / f"{sid}.jsonl").is_file()
    assert not (sessions / f"{sid}.summary.json").exists()
    assert not (sessions / f"{sid}.otel.jsonl").exists()


def test_close_summary_includes_trace_and_snapshot(aura_home: Path):
    ag = agent("inv-close-meta")
    session = Session(profile=ag.profile, mode=SessionMode.SCRIPT)
    session.open(aura_home / "sessions")
    session.emit("turn.start", {})
    meta = session.close()
    assert meta["trace_id"] == session.trace_id
    assert meta["open_snapshot_hash"] == _snapshot_hash(session.profile, session.declared_rules)
