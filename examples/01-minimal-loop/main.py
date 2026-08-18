"""Minimal loop — auto agent ID, audit only."""

from aura import agent, configure

configure()


def main() -> None:
    ag = agent("minimal-demo")
    with ag.session(mode="script") as run:
        run.emit("turn.start", {"input": "hello"})
        run.emit("turn.end", {"output": "done", "tokens": 42})
    print(f"session: {run.session_id}")
    print(f"exports: {run.exports}")


if __name__ == "__main__":
    main()
