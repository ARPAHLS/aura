"""Example 10 — Tailored coat metrics snapshot (AURA-native observers).

Uses the Monitor preset to aggregate tool activity, then emits a session-local
``metrics_snapshot`` on the spine at close. Downstream schedulers or optional
third-party evaluators can read ``.summary.json`` / JSONL exports — AURA does
not depend on any external KPI skill for this pattern.

From repo root:
  pip install -e ".[dev]"
  python examples/10-observer-metrics-snapshot/main.py
"""

from __future__ import annotations

import json

from aura import agent, configure
from aura.hosts import MockSkill, SkillwareHost


def main() -> None:
    configure()
    ag = agent(
        "tailored-metrics-demo",
        purpose="Observer-driven metrics snapshot for tailored coat playbooks",
        spectrum={"level": "mid", "services": ["monitor", "audit"]},
        observers=[
            {
                "preset": "monitor",
                "id": "session-monitor",
                "config": {"max_identical_intents": 3, "log_path": ".aura/monitor-metrics.log"},
            },
        ],
    )

    with ag.session(mode="script") as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("ops", {"ping": lambda a: {"ok": True, "n": a.get("n", 0)}}))
        for n in range(3):
            host.execute("ops", "ping", {"n": n})

        tool_calls = sum(1 for e in run._session.spine.stream() if e.kind == "tool.call")
        run.emit(
            "observer.note",
            {
                "type": "metrics_snapshot",
                "source": "aura.observer.monitor",
                "tool_calls": tool_calls,
                "playbook_hint": (
                    "Optional third-party evaluators may read session export; "
                    "native SLO paths use AURA observers + egress rules (#46)."
                ),
            },
        )
        run.emit("turn.end", {"output": "metrics snapshot recorded"})

    kinds = [e.kind for e in run._session.spine.stream()]
    spectrum = ag.profile.spectrum or {}
    print(
        json.dumps(
            {
                "session_id": run.session_id,
                "metrics_snapshots": sum(
                    1
                    for e in run._session.spine.stream()
                    if e.kind == "observer.note"
                    and (e.payload or {}).get("type") == "metrics_snapshot"
                ),
                "tool_calls": kinds.count("tool.call"),
                "spectrum_level": spectrum.get("level"),
            },
            indent=2,
        )
    )
    print("session:", run.session_id)
    print("exports:", run.exports)


if __name__ == "__main__":
    main()
