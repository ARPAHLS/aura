"""Egress schema and constitution checks at high bind (#78)."""

from __future__ import annotations

import json

import pytest

from aura import agent
from aura.core.audit_report import AuditReportBuilder
from aura.core.conformance import ConformanceEngine
from aura.core.constraints import ConstraintEngine, ConstraintContext, ConstraintViolation
from aura.core.schema_validation import (
    merge_schema_rules,
    parse_schema_refs,
    rules_from_schema_refs,
)
from aura.membrane.egress import guarded_tool_call
from tests.spectrum_helpers import spectrum_block

WRITE_SCHEMA = {
    "type": "object",
    "properties": {"amount": {"type": "number", "maximum": 50}},
    "required": ["amount"],
}

SCHEMA_REFS = {
    "sql_write": {
        "tool": "sql.append",
        "on": "call",
        "schema": WRITE_SCHEMA,
    }
}


def test_parse_schema_refs():
    refs = parse_schema_refs({"schema_refs": SCHEMA_REFS, "goal": "nickel"})
    assert "sql_write" in refs
    assert refs["sql_write"]["tool"] == "sql.append"


def test_rules_from_schema_refs():
    rules = rules_from_schema_refs(parse_schema_refs({"schema_refs": SCHEMA_REFS}))
    assert len(rules) == 1
    assert rules[0]["type"] == "schema_check"
    assert rules[0]["ref"] == "sql_write"


def test_schema_check_engine_blocks_malformed():
    engine = ConstraintEngine()
    results = engine.evaluate(
        ConstraintContext(
            event_kind="tool.call",
            payload={"tool": "sql.append", "args": {"amount": 99}},
            rules=[
                {
                    "type": "schema_check",
                    "tool": "sql.append",
                    "on": "call",
                    "schema": WRITE_SCHEMA,
                }
            ],
            session_state={"_schema_refs": SCHEMA_REFS},
        )
    )
    assert results[0].blocked is True
    assert "maximum" in results[0].message.lower() or "50" in results[0].message


def test_schema_check_engine_passes_valid():
    engine = ConstraintEngine()
    results = engine.evaluate(
        ConstraintContext(
            event_kind="tool.call",
            payload={"tool": "sql.append", "args": {"amount": 25}},
            rules=[
                {
                    "type": "schema_check",
                    "tool": "sql.append",
                    "on": "call",
                    "schema": WRITE_SCHEMA,
                }
            ],
            session_state={},
        )
    )
    assert results[0].passed is True


def test_mid_does_not_auto_wire_schema_refs(aura_home):
    ag = agent(
        "schema-mid",
        skills=["sql.append"],
        spectrum={"level": "mid"},
        variables={"schema_refs": SCHEMA_REFS},
    )
    with ag.session(export=False) as run:
        run.emit("tool.call", {"tool": "sql.append", "args": {"amount": 999}})
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "tool.call" in kinds
    assert "constraint.violated" not in kinds


def test_high_auto_wires_schema_refs_blocks(aura_home):
    ag = agent(
        "schema-high",
        skills=["sql.append"],
        spectrum=spectrum_block("high"),
        variables={"schema_refs": SCHEMA_REFS},
    )
    with ag.session(export=False) as run:
        with pytest.raises(ConstraintViolation):
            run.emit("tool.call", {"tool": "sql.append", "args": {"amount": 999}})


def test_high_auto_wires_schema_refs_passes(aura_home):
    ag = agent(
        "schema-high-ok",
        skills=["sql.append"],
        spectrum=spectrum_block("high"),
        variables={"schema_refs": SCHEMA_REFS},
    )
    with ag.session(export=False) as run:
        run.emit("tool.call", {"tool": "sql.append", "args": {"amount": 10}})
    assert any(e.kind == "tool.call" for e in run._session.spine.stream())


def test_schema_enforcement_opt_out(aura_home):
    ag = agent(
        "schema-opt-out",
        skills=["sql.append"],
        spectrum={**spectrum_block("high"), "schema_enforcement": False},
        variables={"schema_refs": SCHEMA_REFS},
    )
    with ag.session(export=False) as run:
        run.emit("tool.call", {"tool": "sql.append", "args": {"amount": 999}})
    assert "constraint.violated" not in [e.kind for e in run._session.spine.stream()]


def test_explicit_schema_rule_at_mid(aura_home):
    ag = agent(
        "schema-explicit-mid",
        skills=["sql.append"],
        spectrum={"level": "mid"},
        rules=[
            {
                "type": "schema_check",
                "tool": "sql.append",
                "on": "call",
                "schema": WRITE_SCHEMA,
            }
        ],
    )
    with ag.session(export=False) as run:
        with pytest.raises(ConstraintViolation):
            run.emit("tool.call", {"tool": "sql.append", "args": {"amount": 100}})


def test_schema_check_on_tool_result(aura_home):
    ag = agent(
        "schema-result",
        skills=["sql.append"],
        rules=[
            {
                "type": "schema_check",
                "tool": "sql.append",
                "on": "result",
                "schema": {"type": "object", "properties": {"ok": {"const": True}}},
            }
        ],
    )
    with ag.session(export=False) as run:
        with pytest.raises(ConstraintViolation):
            run.emit(
                "tool.result",
                {"tool": "sql.append", "args": {}, "result": {"ok": False}},
            )
        run.emit(
            "tool.result",
            {"tool": "sql.append", "args": {}, "result": {"ok": True}},
        )


def test_guarded_tool_call_schema_block(aura_home):
    ag = agent(
        "schema-egress",
        skills=["sql.append"],
        rules=[
            {
                "type": "schema_check",
                "tool": "sql.append",
                "on": "call",
                "schema": WRITE_SCHEMA,
            }
        ],
    )
    with ag.session(export=False) as run:
        with pytest.raises(ConstraintViolation):
            guarded_tool_call(
                run._session,
                tool="sql.append",
                args={"amount": 75},
                execute=lambda _args: {"ok": True},
            )


def test_audit_report_schema_violation_finding(aura_home):
    ag = agent(
        "schema-audit",
        skills=["sql.append"],
        rules=[
            {
                "type": "schema_check",
                "tool": "sql.append",
                "on": "call",
                "schema": WRITE_SCHEMA,
            }
        ],
    )
    with ag.session(export=False) as run:
        try:
            run.emit("tool.call", {"tool": "sql.append", "args": {"amount": 200}})
        except ConstraintViolation:
            pass
    conf = ConformanceEngine().summarize(run._session.spine, run._session.declared_rules)
    report = AuditReportBuilder().build(run._session.spine, conf)
    assert any(f["code"] == "SCHEMA_VIOLATION" for f in report.findings)


def test_conformance_schema_check(aura_home):
    ag = agent(
        "schema-conf",
        skills=["sql.append"],
        spectrum=spectrum_block("high"),
        variables={"schema_refs": SCHEMA_REFS},
    )
    with ag.session(export=False) as run:
        try:
            run.emit("tool.call", {"tool": "sql.append", "args": {"amount": 500}})
        except ConstraintViolation:
            pass
    conf = ConformanceEngine().summarize(run._session.spine, run._session.declared_rules)
    schema_check = next(c for c in conf.checks if c.get("type") == "schema")
    assert schema_check["passed"] is False
    assert schema_check["schema_violations"] >= 1


def test_merge_schema_rules_appends_at_high():
    from aura.agents.profile import AgentProfile

    profile = AgentProfile(
        aura_id="x",
        skills=["sql.append"],
        spectrum={"level": "high"},
        variables={"schema_refs": SCHEMA_REFS},
    )
    merged = merge_schema_rules(profile, [{"type": "allow_tools", "tools": ["sql.append"]}])
    assert any(r.get("type") == "schema_check" for r in merged)


def test_merged_profile_rules_includes_schema_at_high():
    from aura.agents.profile import AgentProfile
    from aura.api import merged_profile_rules

    profile = AgentProfile(
        aura_id="x",
        skills=["sql.append"],
        spectrum={"level": "high", "identity_required": False},
        variables={"schema_refs": SCHEMA_REFS},
    )
    merged = merged_profile_rules(profile)
    assert any(r.get("type") == "schema_check" for r in merged)


def test_cli_agent_show_includes_schema_block(aura_home, run_aura):
    from aura import agent

    agent(
        "schema-cli",
        agent_ref="acme/schema-cli",
        skills=["sql.append"],
        spectrum={"level": "high", "identity_required": False},
        variables={"schema_refs": SCHEMA_REFS},
    )
    show = run_aura("agent", "show", "acme/schema-cli")
    assert show.returncode == 0
    payload = json.loads(show.stdout)
    schema = payload["effective_spectrum"].get("schema") or {}
    assert schema.get("refs") == 1
    assert schema.get("active_rules", 0) >= 1
    assert schema.get("auto_enforced") is True
