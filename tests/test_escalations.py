"""Escalation playbooks on observer / SLO triggers (#47)."""

from __future__ import annotations

import pytest

from aura import ApprovalRequired, agent
from aura.core.escalations import parse_action, parse_escalation_rules
from aura.core.spectrum_enforcement import effective_spectrum
from aura.hosts import MockSkill, SkillwareHost
from tests.spectrum_helpers import spectrum_block


def test_parse_action_variants():
    assert parse_action("pause") == ("pause", None)
    assert parse_action("email:ops@corp.com") == ("email", "ops@corp.com")
    assert parse_action('nudge:"Re-align to nickel goal"') == ("nudge", '"Re-align to nickel goal"')


def test_parse_escalation_rules_defaults():
    rules = parse_escalation_rules([{"on": "slo.missed"}])
    assert len(rules) == 1
    assert rules[0].actions == ["log"]


def test_slo_missed_fires_escalation_email(aura_home):
    ag = agent(
        "esc-slo",
        variables={
            "schedule": "0 9 * * *",
            "schedule_grace_minutes": 15,
            "_test_clock_iso": "2026-06-01T09:20:00+00:00",
        },
        observers=[{"preset": "schedule_slo", "config": {"required_tool": "sql/append"}}],
        escalations=[
            {
                "on": "slo.missed",
                "actions": ["log", "email:ops@company.com"],
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("turn.end", {"status": "no_write"})
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "slo.missed" in kinds
    assert "escalation.fired" in kinds
    assert "escalation.email" in kinds
    fired = next(e for e in run._session.spine.stream() if e.kind == "escalation.fired")
    actions = (fired.payload or {}).get("actions") or []
    assert any(item.get("action") == "email" for item in actions)


def test_drift_triggers_nudge(aura_home):
    ag = agent(
        "esc-drift",
        variables={"goal": "nickel market data only"},
        observers=[
            {
                "preset": "goal_drift",
                "config": {"forbidden_topics": ["shipyard"]},
            }
        ],
        escalations=[
            {
                "on": "conformance.drift",
                "actions": ["nudge:Re-align to nickel goal"],
            }
        ],
    )
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("research", {"search": lambda a: {"ok": True}}))
        host.execute("research", "search", {"query": "shipyard expansion"})
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "conformance.drift" in kinds
    assert "escalation.fired" in kinds
    assert "membrane.nudge" in kinds


def test_pause_requires_mid_and_blocks_tool_call(aura_home):
    ag = agent(
        "esc-pause",
        spectrum=spectrum_block("mid"),
        variables={"goal": "nickel only"},
        observers=[
            {
                "preset": "goal_drift",
                "config": {"forbidden_topics": ["shipyard"], "event_kinds": ["tool.call"]},
            }
        ],
        escalations=[{"on": "conformance.drift", "actions": ["pause"]}],
    )
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("research", {"search": lambda a: {"ok": True}}))
        host.execute("research", "search", {"query": "shipyard news"})
        with pytest.raises(ApprovalRequired):
            host.execute("research", "search", {"query": "nickel spot"})
        pause_rules = [r for r in run._session.rules if r.get("type") == "escalation_pause"]
        assert pause_rules
        run.approve(pause_rules[0]["request_id"])
        host.execute("research", "search", {"query": "nickel spot"})


def test_pause_skipped_on_low_spectrum(aura_home):
    ag = agent(
        "esc-pause-low",
        spectrum={"level": "low"},
        variables={"goal": "nickel only"},
        observers=[
            {
                "preset": "goal_drift",
                "config": {"forbidden_topics": ["shipyard"], "event_kinds": ["tool.call"]},
            }
        ],
        escalations=[{"on": "conformance.drift", "actions": ["pause"]}],
    )
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("research", {"search": lambda a: {"ok": True}}))
        host.execute("research", "search", {"query": "shipyard news"})
    fired = next(e for e in run._session.spine.stream() if e.kind == "escalation.fired")
    actions = (fired.payload or {}).get("actions") or []
    assert actions[0].get("status") == "skipped"


def test_custom_handler(aura_home):
    seen: list[dict] = []

    def handler(trigger: dict, context: dict) -> None:
        seen.append({"kind": trigger.get("kind"), "context": context})

    ag = agent(
        "esc-custom",
        variables={
            "schedule": "0 9 * * *",
            "_test_clock_iso": "2026-06-01T09:20:00+00:00",
        },
        observers=[{"preset": "schedule_slo", "config": {"required_tool": "sql/append"}}],
    )
    with ag.session(export=False, escalation_handler=handler) as run:
        run.emit("turn.end", {})
    assert seen
    assert seen[0]["kind"] == "slo.missed"


def test_session_open_lists_escalations(aura_home):
    ag = agent(
        "esc-open",
        escalations=[{"on": "observer.alert", "actions": ["log"]}],
    )
    with ag.session(export=False) as run:
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
        spectrum = (open_evt.payload or {}).get("spectrum") or {}
    assert spectrum.get("escalations", {}).get("rule_count") == 1


def test_no_escalations_without_profile_block(aura_home):
    ag = agent("esc-none")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
        spectrum = (open_evt.payload or {}).get("spectrum") or {}
    assert "escalations" not in spectrum
    assert getattr(run._session, "_escalation_engine", None) is None


def test_observer_alert_triggers_playbook(aura_home):
    ag = agent(
        "esc-break",
        escalations=[{"on": "observer.alert", "actions": ["alert"]}],
        observers=[{"preset": "break", "config": {"max_identical_intents": 2}}],
    )
    with ag.session(export=False) as run:
        for _ in range(3):
            run.emit("tool.intent", {"tool": "research", "args": {"q": "same"}})
    assert "escalation.fired" in [e.kind for e in run._session.spine.stream()]


def test_effective_spectrum_mid_allows_destructive(aura_home):
    ag = agent("spec-mid", spectrum={"level": "mid"})
    assert effective_spectrum(ag.profile).level == "mid"


def test_constraint_violated_triggers_playbook(aura_home):
    from aura.core.constraints import ConstraintViolation

    ag = agent(
        "esc-violation",
        rules=[{"type": "deny_tools", "tools": ["blocked_tool"]}],
        escalations=[
            {
                "on": "constraint.violated",
                "actions": ["log", "nudge:Policy breach — review rules"],
            }
        ],
    )
    with ag.session(export=False) as run:
        with pytest.raises(ConstraintViolation):
            run.emit("tool.call", {"tool": "blocked_tool"})
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "constraint.violated" in kinds
    assert "escalation.fired" in kinds
    assert "membrane.nudge" in kinds


def test_audit_report_surfaces_escalation_fired(aura_home):
    from aura.core.audit_report import AuditReportBuilder
    from aura.core.conformance import ConformanceEngine

    ag = agent(
        "esc-audit",
        variables={
            "schedule": "0 9 * * *",
            "_test_clock_iso": "2026-06-01T09:20:00+00:00",
        },
        observers=[{"preset": "schedule_slo", "config": {"required_tool": "sql/append"}}],
        escalations=[{"on": "slo.missed", "actions": ["log"]}],
    )
    with ag.session(export=False) as run:
        run.emit("turn.end", {})
    conf = ConformanceEngine().summarize(run._session.spine, [])
    report = AuditReportBuilder().build(run._session.spine, conf)
    codes = [finding["code"] for finding in report.findings]
    assert "ESCALATION_FIRED" in codes
    assert "SCHEDULE_SLO_MISS" in codes
