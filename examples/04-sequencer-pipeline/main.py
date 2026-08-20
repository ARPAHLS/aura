"""Example 04 — Sequencer pipeline with mock skills (Skillware-compatible host)."""

from __future__ import annotations

from aura import ApprovalRequired, agent, configure
from aura.hosts.mock import MockSkill
from aura.hosts.skillware import SkillwareHost

PIPELINE = {
    "steps": [
        {
            "id": "research",
            "type": "skill",
            "ref": "research",
            "config": {"tool": "search", "args": {"query": "AURA harness membrane"}},
        },
        {"id": "draft", "type": "op", "ref": "compose", "config": {"template": "brief"}},
        {
            "id": "notify",
            "type": "skill",
            "ref": "gmail",
            "gates": ["human_confirm"],
            "config": {
                "tool": "send",
                "args": {"to": "team@example.com", "subject": "Research brief ready"},
            },
        },
    ]
}


def main() -> None:
    configure()
    ag = agent(
        "compliance-pipeline",
        purpose="Research → draft → approve → notify",
        skills=["research", "gmail"],
        sequencer=PIPELINE,
    )

    with ag.session(mode="task") as run:
        host = SkillwareHost(run._session)
        host.register(
            MockSkill(
                "research",
                {"search": lambda args: {"summary": f"Results for: {args.get('query')}"}},
            )
        )
        host.register(
            MockSkill(
                "gmail",
                {"send": lambda args: {"message_id": "mock-001", **args}},
            )
        )

        while True:
            try:
                result = run.run_sequencer(host=host)
                break
            except ApprovalRequired as exc:
                print(f"Approval required: {exc.request_id}")
                run.approve(exc.request_id)

    print("Completed steps:", result["completed"])
    print("Session:", run.session_id)
    print("Exports:", run.exports)


if __name__ == "__main__":
    main()
