"""Example 07 — Monitor, Break, and Limit observer presets on a ToolHost session."""

from __future__ import annotations

import json

from aura import agent, configure
from aura.hosts import MockSkill, SkillwareHost


def demo_explicit_observers() -> dict[str, object]:
    ag = agent(
        "observer-presets-demo",
        purpose="After-call analytics and circuit-breaker alerts on the audit spine",
        observers=[
            {"preset": "monitor", "id": "loop-monitor", "config": {"max_identical_intents": 2}},
            {"preset": "break", "id": "loop-break", "config": {"max_identical_intents": 3}},
        ],
    )

    with ag.session(mode="script") as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("ops", {"ping": lambda a: {"ok": True}}))
        for _ in range(4):
            host.execute("ops", "ping", {"n": 1})
        run.emit("turn.end", {"output": "explicit observer preset demo complete"})

    kinds = [e.kind for e in run._session.spine.stream()]
    return {
        "mode": "explicit_observers",
        "session_id": run.session_id,
        "observer_notes": kinds.count("observer.note"),
        "observer_alerts": kinds.count("observer.alert"),
        "tool_calls": kinds.count("tool.call"),
    }


def demo_spectrum_services() -> dict[str, object]:
    ag = agent(
        "observer-services-demo",
        purpose="Wire limit preset via spectrum.services[]",
        spectrum={
            "level": "mid",
            "services": ["limit"],
            "service_config": {
                "limit": {"max_tool_calls_per_minute": 2, "max_tokens_per_step": 100}
            },
        },
    )

    with ag.session(mode="script") as run:
        run.emit("tool.call", {"tool": "research", "tokens": 50})
        run.emit("tool.call", {"tool": "research", "tokens": 50})
        run.emit("tool.call", {"tool": "research", "tokens": 50})
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
        activation = ((open_evt.payload or {}).get("spectrum") or {}).get(
            "services_activation"
        ) or {}
        kinds = [e.kind for e in run._session.spine.stream()]
        limit_notes = sum(
            1
            for e in run._session.spine.stream()
            if e.kind == "observer.note"
            and (e.payload or {}).get("type", "").startswith(("rate_limit_", "token_budget_"))
        )
        limit_alerts = sum(
            1
            for e in run._session.spine.stream()
            if e.kind == "observer.alert"
            and (e.payload or {}).get("type", "").startswith(("rate_limit_", "token_budget_"))
        )

    return {
        "mode": "spectrum_services",
        "session_id": run.session_id,
        "services_activation": activation,
        "limit_notes": limit_notes,
        "limit_alerts": limit_alerts,
        "tool_calls": kinds.count("tool.call"),
    }


def main() -> None:
    configure()
    results = [demo_explicit_observers(), demo_spectrum_services()]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
