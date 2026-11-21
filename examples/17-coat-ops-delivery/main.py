"""Example 17 — AURA-native coat ops: escalation delivery & membrane scan (#49)."""

from __future__ import annotations

import json
import uuid

from aura import CallableCoatOp, CoatOpRunner, configure, create_agent
from aura.hosts import MockSkill


def main() -> None:
    configure()
    delivered: list[dict] = []

    def _notify(kind: str, payload: dict) -> dict:
        record = {"kind": kind, "to": payload.get("to"), "trigger": payload.get("trigger_kind")}
        delivered.append(record)
        return {"transport": "webhook", "status_code": 200}

    ag = create_agent(
        name=f"coat-ops-demo-{uuid.uuid4().hex[:6]}",
        purpose="Demonstrate live escalation delivery and membrane-level coat scan",
        variables={"goal": "compliance summary only"},
        observers=[
            {
                "preset": "goal_drift",
                "config": {"forbidden_topics": ["shipyard"], "event_kinds": ["tool.call"]},
            },
        ],
        escalations=[
            {"on": "conformance.drift", "actions": ["email:ops@example.com", "wake:requeue"]},
        ],
    )

    with ag.session(
        mode="script",
        export=True,
        coat_ops={"email": CallableCoatOp(_notify), "wake": CallableCoatOp(_notify)},
    ) as run:
        # 1) Membrane-level coat scan on a plain Python body (no Skillware body required)
        coat = CoatOpRunner(run._session)
        coat.host.register(
            MockSkill(
                "security/prompt_injection_firewall",
                {
                    "security/prompt_injection_firewall": lambda a: {
                        "is_safe": "ignore" not in str(a.get("source_text", "")).lower(),
                        "risk_level": "none",
                    }
                },
            )
        )
        scan = coat.scan_input("Summarize Q3 compliance metrics.")

        # 2) Trigger drift -> fires escalation.email + escalation.wake through CallableCoatOp
        run.emit("tool.call", {"tool": "search", "args": {"query": "shipyard expansion"}})

    print(
        json.dumps(
            {
                "session_id": run.session_id,
                "coat_scan": scan,
                "delivered": delivered,
                "exports": run.exports,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
