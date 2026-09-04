"""Spectrum enforcement — level-driven egress bind (#27)."""

from __future__ import annotations

import json

import pytest

from aura import agent
from aura.core.constraints import ConstraintViolation
from aura.core.spectrum_enforcement import enforcement_rules, merge_rules_with_spectrum


def test_enforcement_rules_by_level():
    from aura.agents.profile import AgentProfile

    base = AgentProfile(aura_id="test", skills=["research", "gmail"])
    base.spectrum = {"level": "low"}
    assert enforcement_rules(base) == []

    base.spectrum = {"level": "mid"}
    assert enforcement_rules(base) == []

    base.spectrum = {"level": "high"}
    rules = enforcement_rules(base)
    assert len(rules) == 1
    assert rules[0]["type"] == "allow_tools"
    assert "research" in rules[0]["tools"]

    base.spectrum = {"level": "full"}
    rules = enforcement_rules(base)
    assert any(r["type"] == "sequencer_required" for r in rules)


def test_spectrum_low_allows_off_scope_tool(aura_home):
    ag = agent("audit-only", skills=["research"], spectrum={"level": "low"})
    with ag.session(export=False) as run:
        run.emit("tool.call", {"tool": "off_scope_tool", "tokens": 1})
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "constraint.violated" not in kinds


def test_spectrum_high_denies_off_scope_tool(aura_home):
    ag = agent("high-bind", skills=["research"], spectrum={"level": "high"})
    with ag.session(export=False) as run:
        with pytest.raises(ConstraintViolation):
            run.emit("tool.call", {"tool": "off_scope_tool"})


def test_spectrum_high_allows_declared_skill(aura_home):
    ag = agent("high-bind-ok", skills=["research"], spectrum={"level": "high"})
    with ag.session(export=False) as run:
        run.emit("tool.call", {"tool": "research"})
    assert any(e.kind == "tool.call" for e in run._session.spine.stream())


def test_spectrum_full_requires_sequencer_step(aura_home):
    ag = agent("full-bind", skills=["research"], spectrum={"level": "full"})
    with ag.session(export=False) as run:
        with pytest.raises(ConstraintViolation):
            run.emit("tool.call", {"tool": "research"})
        run.emit("tool.call", {"tool": "research", "step_id": "scan_input"})
        tool_calls = [e for e in run._session.spine.stream() if e.kind == "tool.call"]
    assert len(tool_calls) == 1
    assert tool_calls[0].payload.get("step_id") == "scan_input"


def test_explicit_rules_still_apply_at_low(aura_home):
    ag = agent(
        "low-with-rules",
        skills=["research"],
        spectrum={"level": "low"},
        rules=[{"type": "deny_tools", "tools": ["blocked_tool"]}],
    )
    with ag.session(export=False) as run:
        with pytest.raises(ConstraintViolation):
            run.emit("tool.call", {"tool": "blocked_tool"})


def test_session_open_includes_spectrum(aura_home):
    ag = agent("spec-open", skills=["research"], spectrum={"level": "high"})
    with ag.session(export=False) as run:
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
        spectrum = (open_evt.payload or {}).get("spectrum") or {}
    assert spectrum.get("level") == "high"
    assert spectrum.get("enforcement_rule_count", 0) >= 1


def test_merge_rules_with_spectrum():
    from aura.agents.profile import AgentProfile

    profile = AgentProfile(aura_id="x", skills=["a"], spectrum={"level": "high"})
    merged = merge_rules_with_spectrum(profile, [{"type": "deny_tools", "tools": ["x"]}])
    types = [r["type"] for r in merged]
    assert "allow_tools" in types
    assert "deny_tools" in types


def test_cli_agent_set_spectrum(run_aura):
    create = run_aura("agent", "create", "spec-bot", "--ref", "acme/spec")
    assert create.returncode == 0

    updated = run_aura(
        "agent",
        "set",
        "acme/spec",
        "--skill",
        "research",
        "--spectrum-level",
        "high",
        "--spectrum-service",
        "monitor",
        "--spectrum-service",
        "audit",
    )
    assert updated.returncode == 0
    profile = json.loads(updated.stdout)
    assert profile["spectrum"]["level"] == "high"
    assert profile["spectrum"]["services"] == ["monitor", "audit"]

    show = run_aura("agent", "show", "acme/spec")
    assert show.returncode == 0
    payload = json.loads(show.stdout)
    assert payload["effective_spectrum"]["level"] == "high"
    rules = payload["effective_spectrum"]["enforcement_rules"]
    assert any(r.get("type") == "allow_tools" for r in rules)
