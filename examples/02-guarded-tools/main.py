"""Guarded tools — token limit, confirm-before-action, allow/deny lists."""

from aura import ApprovalRequired, agent, configure

configure()


def main() -> None:
    ag = agent(
        "guarded-demo",
        rules=[
            {"type": "max_tokens_per_step", "limit": 10000},
            {"type": "confirm_before", "tools": ["gmail.send"]},
            {"type": "allow_tools", "tools": ["search.web", "gmail.send", "gmail.draft"]},
        ],
    )

    with ag.session(mode="script") as run:
        run.emit("turn.start", {"input": "research tire companies"})
        run.emit("tool.call", {"tool": "search.web", "query": "tire manufacturers EU"})
        run.emit("tool.call", {"tool": "gmail.draft", "tokens": 500})

        # Blocked without approval
        try:
            run.emit("tool.call", {"tool": "gmail.send", "to": "ceo@example.com", "tokens": 200})
        except ApprovalRequired as exc:
            print(f"approval needed: {exc.request_id}")
            run.approve(exc.request_id)
            run.emit("tool.call", {"tool": "gmail.send", "to": "ceo@example.com", "tokens": 200})

        # Would exceed token limit
        try:
            run.emit("tool.call", {"tool": "search.web", "tokens": 15000})
        except Exception as exc:
            run.emit("constraint.blocked", {"error": str(exc)})

        run.emit("turn.end", {"output": "drafts ready", "tokens": 700})

    print(f"session: {run.session_id}")
    print(f"exports: {run.exports}")


if __name__ == "__main__":
    main()
