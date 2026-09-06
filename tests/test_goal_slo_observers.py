"""Tests for goal drift and schedule SLO observer presets."""

from __future__ import annotations

import pytest

from aura import agent
from aura.core.audit_report import AuditReportBuilder
from aura.core.conformance import ConformanceEngine
from aura.core.goal_slo import detect_goal_drift, parse_daily_schedule
from aura.hosts import MockSkill, SkillwareHost


def test_parse_daily_schedule_cron_and_clock():
    assert parse_daily_schedule("0 9 * * *") == parse_daily_schedule("09:00")


def test_detect_goal_drift_forbidden_topic():
    reason = detect_goal_drift(
        '{"query": "shipyard steel prices"}',
        goal="nickel market data only",
        forbidden_topics=["shipyard"],
        required_keywords=["nickel"],
        require_all_keywords=False,
    )
    assert reason is not None
    assert "shipyard" in reason


def test_detect_goal_drift_derived_keyword_any_match():
    assert (
        detect_goal_drift(
            '{"query": "nickel spot price"}',
            goal="nickel market data only",
            forbidden_topics=[],
            required_keywords=["nickel", "market", "data"],
            require_all_keywords=False,
        )
        is None
    )
    reason = detect_goal_drift(
        '{"query": "copper spot price"}',
        goal="nickel market data only",
        forbidden_topics=[],
        required_keywords=["nickel", "market", "data"],
        require_all_keywords=False,
    )
    assert reason is not None


def test_goal_drift_observer_emits_conformance_drift(aura_home):
    ag = agent(
        "goal-drift",
        variables={"goal": "nickel market data only"},
        observers=[
            {
                "preset": "goal_drift",
                "id": "nickel-goal",
                "config": {"forbidden_topics": ["shipyard"]},
            }
        ],
    )
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("research", {"search": lambda a: {"ok": True}}))
        host.execute("research", "search", {"query": "shipyard expansion news"})
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "conformance.drift" in kinds


def test_schedule_slo_pass_within_window(aura_home):
    ag = agent(
        "slo-pass",
        variables={
            "schedule": "0 9 * * *",
            "schedule_grace_minutes": 15,
            "_test_clock_iso": "2026-06-01T08:58:00+00:00",
        },
        observers=[
            {
                "preset": "schedule_slo",
                "id": "daily-slo",
                "config": {"required_tool": "sql/append"},
            }
        ],
    )
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("sql", {"append": lambda a: {"rows": 1}}))
        host.execute("sql", "append", {"table": "nickel_prices"})
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "slo.missed" not in kinds


def test_schedule_slo_miss_after_deadline(aura_home):
    ag = agent(
        "slo-miss",
        variables={
            "schedule": "0 9 * * *",
            "schedule_grace_minutes": 15,
            "_test_clock_iso": "2026-06-01T09:20:00+00:00",
        },
        observers=[
            {
                "preset": "schedule_slo",
                "id": "daily-slo",
                "config": {"required_tool": "sql/append"},
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("turn.end", {"status": "no_write"})
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "slo.missed" in kinds


def test_audit_report_surfaces_goal_and_slo_findings(aura_home):
    ag = agent(
        "audit-slo",
        variables={
            "goal": "nickel market data only",
            "schedule": "0 9 * * *",
            "schedule_grace_minutes": 15,
            "_test_clock_iso": "2026-06-01T09:20:00+00:00",
        },
        observers=[
            {
                "preset": "goal_drift",
                "id": "nickel-goal",
                "config": {"forbidden_topics": ["shipyard"]},
            },
            {
                "preset": "schedule_slo",
                "id": "daily-slo",
                "config": {"required_tool": "sql/append"},
            },
        ],
    )
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("research", {"search": lambda a: {"ok": True}}))
        host.execute("research", "search", {"query": "shipyard expansion news"})
    conf = ConformanceEngine().summarize(run._session.spine, run._session.rules)
    report = AuditReportBuilder().build(run._session.spine, conf)
    codes = {f["code"] for f in report.findings}
    assert report.verdict == "fail"
    assert "GOAL_DRIFT" in codes
    assert "SCHEDULE_SLO_MISS" in codes


def test_schedule_slo_requires_schedule(aura_home):
    ag = agent(
        "slo-no-schedule",
        observers=[{"preset": "schedule_slo", "id": "daily-slo", "config": {}}],
    )
    with pytest.raises(ValueError, match="schedule"):
        with ag.session(export=False):
            pass
