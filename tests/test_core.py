"""AURA Harness v0.1 tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aura import agent, configure, ApprovalRequired
from aura.agents.registry import AgentRegistry, DuplicateAgentError
from aura.core.constraints import ConstraintEngine, ConstraintContext
from aura.core.ids import is_ulid
from aura.core.spine import AuditSpine
from aura.core.spectrum import Spectrum


@pytest.fixture
def aura_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "aura_home"
    home.mkdir()
    monkeypatch.setenv("AURA_HOME", str(home))
    configure()
    return home


def test_spectrum_from_manifest_defaults():
    s = Spectrum.from_manifest({})
    assert s.level == "mid"
    assert "audit" in s.services


def test_registry_ulid_ids(aura_home: Path):
    reg = AgentRegistry()
    a1 = reg.create(name="alpha", agent_ref="acme/alpha")
    a2 = reg.create(name="beta", agent_ref="acme/beta")
    assert is_ulid(a1.aura_id)
    assert is_ulid(a2.aura_id)
    assert a1.aura_id != a2.aura_id
    assert a1.agent_ref == "acme/alpha"
    reg.archive(a2.aura_id)
    a3 = reg.create(name="gamma", agent_ref="acme/gamma")
    assert is_ulid(a3.aura_id)


def test_registry_duplicate_name(aura_home: Path):
    reg = AgentRegistry()
    reg.create(name="same")
    with pytest.raises(DuplicateAgentError):
        reg.create(name="same")


def test_spine_jsonl_persistence(aura_home: Path, tmp_path: Path):
    log = tmp_path / "test.jsonl"
    spine = AuditSpine("sess1", "AURA-0001", log_path=log)
    spine.append("turn.start", {"x": 1}, agent_ids={"aura_id": "AURA-0001"})
    spine.append("turn.end", {"x": 2})
    assert len(spine.stream()) == 2
    rows = AuditSpine.read_jsonl(log)
    assert rows[0]["kind"] == "turn.start"
    assert rows[1]["parent_id"] == rows[0]["event_id"]


def test_max_tokens_constraint():
    engine = ConstraintEngine()
    ctx = ConstraintContext(
        event_kind="tool.call",
        payload={"tokens": 20000},
        rules=[{"type": "max_tokens_per_step", "limit": 10000}],
        session_state={},
    )
    results = engine.evaluate(ctx)
    assert results[0].blocked is True


def test_confirm_before_flow(aura_home: Path):
    ag = agent(
        "confirm-test",
        rules=[{"type": "confirm_before", "tools": ["gmail.send"]}],
    )
    with ag.session(export=False) as run:
        with pytest.raises(ApprovalRequired) as exc:
            run.emit("tool.call", {"tool": "gmail.send"})
        run.approve(exc.value.request_id)
        run.emit("tool.call", {"tool": "gmail.send"})
    events = run._session.spine.stream()
    assert any(e.kind == "constraint.approval_required" for e in events)
    assert any(e.kind == "tool.call" for e in events)


def test_session_export_summary(aura_home: Path):
    ag = agent("export-test")
    with ag.session() as run:
        run.emit("turn.start", {})
        run.emit("turn.end", {"tokens": 10})
    summary_path = Path(run.exports["summary"])
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert data["aura_id"] == ag.profile.aura_id
    assert data["conformance"]["passed"] is True
    assert data.get("audit_report", {}).get("verdict") == "pass"
    assert data["event_count"] >= 3


def test_conformance_detects_violation(aura_home: Path):
    ag = agent("viol-test", rules=[{"type": "deny_tools", "tools": ["bad.tool"]}])
    with pytest.raises(Exception):
        with ag.session(export=False) as run:
            run.emit("tool.call", {"tool": "bad.tool"})
    # violation recorded on spine before raise
    sessions = list((aura_home / "sessions").glob("*.jsonl"))
    assert sessions
    rows = AuditSpine.read_jsonl(sessions[-1])
    assert any(r["kind"] == "constraint.violated" for r in rows)
