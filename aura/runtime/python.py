"""Python runtime attach helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import runpy
import sys

from aura.api import AgentHandle


def run_script(
    agent: AgentHandle,
    script_path: str | Path,
    *,
    mode: str | None = None,
    argv: list[str] | None = None,
) -> dict[str, Any]:
    """Run a Python script under an AURA session."""
    path = Path(script_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(script_path)

    session_mode = mode or agent.profile.default_mode
    with agent.session(mode=session_mode) as run:
        run.emit("runtime.attach", {"runtime": "python", "script": str(path)})
        old_argv = sys.argv[:]
        try:
            if argv is not None:
                sys.argv = [str(path), *argv]
            else:
                sys.argv = [str(path)]
            runpy.run_path(str(path), run_name="__main__")
        finally:
            sys.argv = old_argv
        run.emit("runtime.detach", {"script": str(path)})
    return {"session_id": run.session_id, "exports": run.exports}


def aura_wrapped(
    agent: AgentHandle, mode: str | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to run a callable inside an AURA session."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            session_mode = mode or agent.profile.default_mode
            with agent.session(mode=session_mode) as run:
                run.emit("runtime.attach", {"runtime": "python", "callable": fn.__name__})
                result = fn(*args, **kwargs)
                run.emit("runtime.detach", {"callable": fn.__name__})
                return result

        return wrapper

    return decorator
