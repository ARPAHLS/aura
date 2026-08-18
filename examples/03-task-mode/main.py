"""Task mode — run until goal complete."""

from aura import agent, configure

configure()


def main() -> None:
    ag = agent(
        "task-demo",
        purpose="Research tire companies and draft outreach emails",
        default_mode="task",
    )

    with ag.session(mode="task") as run:
        run.emit("task.start", {"goal": ag.profile.purpose})
        run.emit("step.complete", {"step": "research", "findings": 12})
        run.emit("step.complete", {"step": "draft_emails", "count": 5})
        run.complete_goal({"status": "emails_drafted", "awaiting_approval": True})

    print(f"session: {run.session_id}")
    print(f"exports: {run.exports}")


if __name__ == "__main__":
    main()
