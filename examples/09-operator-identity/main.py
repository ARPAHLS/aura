"""Example: optional verified operator identity on session open."""

from aura import agent, configure
from aura.identity.adapters.mock import MockIdentityAdapter


def main() -> None:
    configure()

    # Enterprise path: pass a verified adapter (mock stands in for Auth0/OIDC in CI).
    adapter = MockIdentityAdapter(subject="operator@example.com", verified=True)

    ag = agent(
        "identity-demo",
        agent_ref="demo/identity",
        ids={"external": {"ticket": "INC-1001"}},
    )

    with ag.session(identity_adapter=adapter, export=False) as run:
        run.emit("turn.start", {"note": "session with operator trailer"})
        run.emit("turn.end", {"tokens": 1})

    print("session_id:", run.session_id)
    print("operator:", run.summary["identity"])
    print("agent_ids:", run.summary["agent_ids"]["ids"])


if __name__ == "__main__":
    main()
