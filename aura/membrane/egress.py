"""Egress — policy gate before tool/skill execution reaches the host body."""

from __future__ import annotations

from typing import Any, Callable

from aura.core.constraints import ApprovalRequired, ConstraintViolation


def guarded_tool_call(
    session: Any,
    *,
    tool: str,
    skill_id: str | None = None,
    args: dict[str, Any] | None = None,
    execute: Callable[[], Any],
    step_id: str | None = None,
) -> Any:
    """
    Membrane egress: intent → policy (emit tool.call) → execute → result event.
    """
    payload_base = {"tool": tool, "skill_id": skill_id, "args": args or {}}
    if step_id:
        payload_base["step_id"] = step_id

    session.emit(
        "tool.intent",
        {**payload_base, "membrane": "egress"},
        step_id=step_id,
    )

    try:
        session.emit("tool.call", payload_base, step_id=step_id)
    except (ApprovalRequired, ConstraintViolation):
        raise

    try:
        result = execute()
    except Exception as exc:
        session.emit(
            "tool.error",
            {**payload_base, "error": str(exc)},
            step_id=step_id,
        )
        raise

    session.emit(
        "tool.result",
        {**payload_base, "result": result},
        step_id=step_id,
    )
    return result
