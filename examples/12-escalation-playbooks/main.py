"""Example 12 — Escalation playbooks on observer / SLO / policy triggers (#47)."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from aura import ApprovalRequired, agent, configure
from aura.core.audit_report import AuditReportBuilder
from aura.core.conformance import ConformanceEngine
from aura.core.constraints import ConstraintViolation
from aura.hosts import MockSkill, SkillwareHost

ScenarioFn = Callable[[], dict[str, Any]]

SLO_CLOCK_MISS = "2026-06-01T09:20:00+00:00"


def _spine_summary(session) -> dict[str, Any]:
    kinds = [e.kind for e in session.spine.stream()]
    conf = ConformanceEngine().summarize(session.spine, session.rules)
    report = AuditReportBuilder().build(session.spine, conf)
    open_evt = next(e for e in session.spine.stream() if e.kind == "session.open")
    spectrum = (open_evt.payload or {}).get("spectrum") or {}
    return {
        "kinds": kinds,
        "escalation_fired": kinds.count("escalation.fired"),
        "audit_verdict": report.verdict,
        "finding_codes": sorted({f.get("code") for f in report.findings if f.get("code")}),
        "spectrum_escalations": spectrum.get("escalations"),
    }


def scenario_slo_miss_email() -> dict[str, Any]:
    """Schedule SLO miss → log + email stub on spine."""
    ag = agent(
        "esc-demo-slo",
        agent_ref="demo/esc-slo",
        variables={
            "schedule": "0 9 * * *",
            "schedule_grace_minutes": 15,
            "_test_clock_iso": SLO_CLOCK_MISS,
        },
        observers=[{"preset": "schedule_slo", "config": {"required_tool": "sql/append"}}],
        escalations=[
            {
                "id": "slo-ops-email",
                "on": "slo.missed",
                "after_minutes": 15,
                "actions": ["log", "email:ops@company.com"],
            }
        ],
    )
    with ag.session(mode="script") as run:
        run.emit("turn.end", {"status": "research_only_no_sql"})
    summary = _spine_summary(run._session)
    return {
        "scenario": "slo_miss_email",
        "session_id": run.session_id,
        **summary,
        "has_slo_missed": "slo.missed" in summary["kinds"],
        "has_escalation_email": "escalation.email" in summary["kinds"],
    }


def scenario_drift_nudge() -> dict[str, Any]:
    """Goal drift → membrane nudge."""
    ag = agent(
        "esc-demo-drift",
        variables={"goal": "nickel market data only"},
        observers=[
            {
                "preset": "goal_drift",
                "config": {"forbidden_topics": ["shipyard", "steel"]},
            }
        ],
        escalations=[
            {
                "on": "conformance.drift",
                "actions": ['nudge:"Re-align to declared nickel goal"'],
            }
        ],
    )
    with ag.session(mode="script") as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("research", {"search": lambda a: {"hits": 1}}))
        host.execute("research", "search", {"query": "shipyard steel futures"})
    summary = _spine_summary(run._session)
    return {
        "scenario": "drift_nudge",
        "session_id": run.session_id,
        **summary,
        "has_drift": "conformance.drift" in summary["kinds"],
        "has_nudge": "membrane.nudge" in summary["kinds"],
    }


def scenario_break_alert() -> dict[str, Any]:
    """Break preset observer.alert → escalation alert note."""
    ag = agent(
        "esc-demo-break",
        escalations=[{"on": "observer.alert", "actions": ["alert:Repeated intent threshold"]}],
        observers=[{"preset": "break", "config": {"max_identical_intents": 2}}],
    )
    with ag.session(mode="script") as run:
        for _ in range(3):
            run.emit("tool.intent", {"tool": "research", "args": {"q": "same"}})
    summary = _spine_summary(run._session)
    alert_notes = [
        e
        for e in run._session.spine.stream()
        if e.kind == "observer.note" and (e.payload or {}).get("type") == "escalation_alert"
    ]
    return {
        "scenario": "break_alert",
        "session_id": run.session_id,
        **summary,
        "escalation_alert_notes": len(alert_notes),
    }


def scenario_constraint_nudge() -> dict[str, Any]:
    """Egress deny → constraint.violated → nudge."""
    ag = agent(
        "esc-demo-violation",
        rules=[{"type": "deny_tools", "tools": ["external_api"]}],
        escalations=[
            {
                "on": "constraint.violated",
                "actions": ["log", "nudge:Policy breach — tool blocked by constitution"],
            }
        ],
    )
    with ag.session(mode="script") as run:
        try:
            run.emit("tool.call", {"tool": "external_api", "args": {"path": "/export"}})
        except ConstraintViolation:
            pass
    summary = _spine_summary(run._session)
    return {
        "scenario": "constraint_nudge",
        "session_id": run.session_id,
        **summary,
        "has_violation": "constraint.violated" in summary["kinds"],
    }


def scenario_drift_pause_approve() -> dict[str, Any]:
    """Mid spectrum + drift → pause; unblock with approve()."""
    ag = agent(
        "esc-demo-pause",
        spectrum={"level": "mid"},
        variables={"goal": "nickel only"},
        observers=[
            {
                "preset": "goal_drift",
                "config": {
                    "forbidden_topics": ["shipyard"],
                    "event_kinds": ["tool.call"],
                },
            }
        ],
        escalations=[{"on": "conformance.drift", "actions": ["pause"]}],
    )
    blocked = False
    approved = False
    with ag.session(mode="script") as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("research", {"search": lambda a: {"ok": True}}))
        host.execute("research", "search", {"query": "shipyard news"})
        try:
            host.execute("research", "search", {"query": "nickel spot"})
            blocked = False
        except ApprovalRequired:
            blocked = True
            pause_rules = [r for r in run._session.rules if r.get("type") == "escalation_pause"]
            if pause_rules:
                run.approve(pause_rules[0]["request_id"])
                host.execute("research", "search", {"query": "nickel spot"})
                approved = True
    summary = _spine_summary(run._session)
    fired = next(
        (e for e in run._session.spine.stream() if e.kind == "escalation.fired"),
        None,
    )
    pause_action = None
    if fired:
        actions = (fired.payload or {}).get("actions") or []
        pause_action = next((a for a in actions if a.get("action") == "pause"), None)
    return {
        "scenario": "drift_pause_approve",
        "session_id": run.session_id,
        **summary,
        "tool_blocked_pending_approval": blocked,
        "approved_and_resumed": approved,
        "pause_action": pause_action,
    }


def scenario_custom_handler() -> dict[str, Any]:
    """Programmatic hook — session(escalation_handler=...) without profile rules."""
    seen: list[dict[str, Any]] = []

    def handler(trigger: dict[str, Any], context: dict[str, Any]) -> None:
        seen.append(
            {
                "kind": trigger.get("kind"),
                "rule_id": context.get("rule_id"),
                "trigger_event_id": context.get("trigger_event_id"),
            }
        )

    ag = agent(
        "esc-demo-custom",
        variables={
            "schedule": "0 9 * * *",
            "_test_clock_iso": SLO_CLOCK_MISS,
        },
        observers=[{"preset": "schedule_slo", "config": {"required_tool": "sql/append"}}],
    )
    with ag.session(mode="script", escalation_handler=handler) as run:
        run.emit("turn.end", {})
    summary = _spine_summary(run._session)
    return {
        "scenario": "custom_handler",
        "session_id": run.session_id,
        **summary,
        "handler_invocations": seen,
    }


SCENARIOS: dict[str, ScenarioFn] = {
    "slo_miss_email": scenario_slo_miss_email,
    "drift_nudge": scenario_drift_nudge,
    "break_alert": scenario_break_alert,
    "constraint_nudge": scenario_constraint_nudge,
    "drift_pause_approve": scenario_drift_pause_approve,
    "custom_handler": scenario_custom_handler,
}


def main() -> None:
    configure()
    selected = os.environ.get("ESCALATION_SCENARIO", "all").strip().lower()
    if selected == "all":
        results = [fn() for fn in SCENARIOS.values()]
    elif selected in SCENARIOS:
        results = [SCENARIOS[selected]()]
    else:
        known = ", ".join(sorted(SCENARIOS))
        raise SystemExit(f"Unknown ESCALATION_SCENARIO={selected!r}. Choose: all, {known}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
