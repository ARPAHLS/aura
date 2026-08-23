"""Minimal loop — auto agent ID, audit only."""

from aura import agent, configure

# Setup
configure()


def main() -> None:
    ag = agent("minimal-demo")

    # Session
    with ag.session(mode="script") as run:
        # Emit
        run.emit("turn.start", {"input": "hello"})
        run.emit("turn.end", {"output": "done", "tokens": 42})

    # Close / expected export
    print(f"session: {run.session_id}")
    print(f"exports: {run.exports}")


if __name__ == "__main__":
    main()
