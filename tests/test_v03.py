"""AURA Harness v0.3 tests — identity, audit report, hash chain, compare."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aura import agent, configure, ApprovalRequired
from aura.agents.registry import AgentRegistry, DuplicateAgentError
from aura.core.audit_report import AuditReportBuilder
from aura.core.compare import compare_sessions
from aura.core.conformance import ConformanceEngine
from aura.core.ids import is_ulid, new_ulid, validate_agent_ref
from aura.core.spine import AuditSpine, verify_hash_chain
from aura.exporters.otel import events_to_spans


@pytest.fixture
def aura_home(tmp_path, monkeypatch):
    home = tmp_path / "aura_home"
    home.mkdir()
    monkeypatch.setenv("AURA_HOME", str(home))
    configure()
    return home


def test_new_ulid_format():
    uid = new_ulid()
    assert is_ulid(uid)


def test_validate_agent_ref():
    assert validate_agent_ref("Acme/Compliance-Bot") == "acme/compliance-bot"
    with pytest.raises(ValueError):
        validate_agent_ref("bad ref!")


def test_create_with_custom_aura_id(aura_home):
    reg = AgentRegistry()
    p = reg.create(name="x", aura_id="CUSTOM-ID-001", agent_ref="acme/x")
    assert p.aura_id == "CUSTOM-ID-001"
    assert reg.get_by_id("CUSTOM-ID-001").agent_ref == "acme/x"


def test_resolve_by_agent_ref(aura_home):
    reg = AgentRegistry()
    reg.create(name="bot", agent_ref="tenant/bot")
    assert reg.resolve("tenant/bot").name == "bot"


def test_duplicate_agent_ref(aura_home):
    reg = AgentRegistry()
    reg.create(agent_ref="acme/a")
    with pytest.raises(DuplicateAgentError):
        reg.create(agent_ref="acme/a")


def test_hash_chain_valid(aura_home, tmp_path):
    log = tmp_path / "chain.jsonl"
    spine = AuditSpine("sess", "01TEST", log_path=log)
    spine.append("turn.start", {})
    spine.append("turn.end", {})
    assert verify_hash_chain(spine) is True
    rows = AuditSpine.read_jsonl(log)
    assert rows[0]["content_hash"]
    assert rows[1]["prev_hash"] == rows[0]["content_hash"]


def test_approve_records_principal(aura_home):
    ag = agent("principal-test", rules=[{"type": "confirm_before", "tools": ["send"]}])
    with ag.session(export=False) as run:
        with pytest.raises(ApprovalRequired) as exc:
            run.emit("tool.call", {"tool": "send"})
        run.approve(exc.value.request_id, principal="alice@corp.com")
    approved = [e for e in run._session.spine.stream() if e.kind == "constraint.approved"]
    assert approved[0].payload["principal"] == "alice@corp.com"


def test_audit_report_findings_on_violation(aura_home):
    ag = agent("audit-fail", rules=[{"type": "deny_tools", "tools": ["bad.tool"]}])
    with pytest.raises(Exception):
        with ag.session(export=False) as run:
            run.emit("tool.call", {"tool": "bad.tool"})
    conf = ConformanceEngine().summarize(run._session.spine, run._session.rules)
    report = AuditReportBuilder().build(run._session.spine, conf)
    assert report.verdict == "fail"
    assert report.findings
    assert report.recommendations


def test_session_export_includes_audit_report(aura_home):
    ag = agent("audit-pass", agent_ref="demo/pass")
    with ag.session() as run:
        run.emit("turn.start", {})
        run.emit("turn.end", {"tokens": 5})
    summary = json.loads(Path(run.exports["summary"]).read_text(encoding="utf-8"))
    assert summary["agent_ref"] == "demo/pass"
    assert summary["audit_report"]["verdict"] == "pass"
    assert "otel" in run.exports


def test_otel_span_export():
    events = [{"kind": "turn.start", "event_id": "a", "session_id": "s", "aura_id": "u"}]
    spans = events_to_spans(events)
    assert spans[0]["name"] == "turn.start"


def test_compare_sessions(aura_home):
    ag = agent("cmp")
    with ag.session() as run1:
        run1.emit("turn.start", {})
    with ag.session() as run2:
        run2.emit("turn.start", {})
        run2.emit("turn.end", {})
    base = aura_home / "sessions"
    s1 = Path(run1.exports["summary"]).name.replace(".summary.json", "")
    s2 = Path(run2.exports["summary"]).name.replace(".summary.json", "")
    result = compare_sessions(base / f"{s1}.summary.json", base / f"{s2}.summary.json")
    assert result["event_count"]["delta"] == 1
