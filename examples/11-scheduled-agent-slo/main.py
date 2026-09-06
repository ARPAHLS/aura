"""Example 11 — Goal drift and schedule SLO observers (nickel cron north star)."""

from __future__ import annotations

import json
import os

from aura import agent, configure
from aura.core.audit_report import AuditReportBuilder
from aura.core.conformance import ConformanceEngine
from aura.hosts import MockSkill, SkillwareHost


def main() -> None:
    scenario = os.environ.get("SLO_SCENARIO", "pass").strip().lower()
    configure()

    if scenario == "miss":
        clock_iso = "2026-06-01T09:20:00+00:00"
    else:
        clock_iso = "2026-06-01T08:58:00+00:00"
    clock_iso = os.environ.get("SLO_CLOCK_ISO", clock_iso)

    ag = agent(
        "nickel-research",
        agent_ref="demo/nickel-research",
        purpose="Daily nickel market research → SQL append by 09:00",
        variables={
            "goal": "nickel market data only",
            "schedule": "0 9 * * *",
            "schedule_grace_minutes": 15,
            "_test_clock_iso": clock_iso,
        },
        observers=[
            {
                "preset": "goal_drift",
                "id": "nickel-goal",
                "config": {"forbidden_topics": ["shipyard", "steel"]},
            },
            {
                "preset": "schedule_slo",
                "id": "nickel-slo",
                "config": {"required_tool": "sql/append"},
            },
        ],
    )

    with ag.session(mode="script") as run:
        host = SkillwareHost(run._session)
        host.register(
            MockSkill(
                "research",
                {"search": lambda args: {"topic": args.get("query"), "hits": 3}},
            )
        )
        host.register(
            MockSkill("sql", {"append": lambda args: {"rows": len(args.get("rows") or [])}})
        )

        query = "shipyard steel futures" if scenario == "drift" else "nickel spot price asia"
        host.execute("research", "search", {"query": query})
        if scenario != "miss":
            host.execute(
                "sql",
                "append",
                {"table": "nickel_prices", "rows": [{"price": 18250, "region": "asia"}]},
            )
        run.emit("turn.end", {"scenario": scenario})

    conf = ConformanceEngine().summarize(run._session.spine, run._session.rules)
    report = AuditReportBuilder().build(run._session.spine, conf)
    kinds = [e.kind for e in run._session.spine.stream()]
    payload = {
        "session_id": run.session_id,
        "scenario": scenario,
        "conformance_drift": kinds.count("conformance.drift"),
        "slo_missed": kinds.count("slo.missed"),
        "audit_verdict": report.verdict,
        "finding_codes": [f.get("code") for f in report.findings],
    }
    print(json.dumps(payload, indent=2))
    print("exports:", run.exports)


if __name__ == "__main__":
    main()
