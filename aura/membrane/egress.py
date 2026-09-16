"""Egress — policy gate before tool/skill execution reaches the host body."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from aura.core.constraints import ApprovalRequired, ConstraintViolation
from aura.core.secrets import SecretNotFoundError


def _invoke_execute(execute: Callable[..., Any], live_args: dict[str, Any]) -> Any:
    """Call execute(live_args) when the callable accepts an argument; else execute()."""
    try:
        signature = inspect.signature(execute)
    except (TypeError, ValueError):
        return execute()
    required = [
        param
        for param in signature.parameters.values()
        if param.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and param.default is inspect.Parameter.empty
    ]
    if required:
        return execute(live_args)
    for param in signature.parameters.values():
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            return execute(live_args)
    return execute()


def guarded_tool_call(
    session: Any,
    *,
    tool: str,
    skill_id: str | None = None,
    args: dict[str, Any] | None = None,
    execute: Callable[..., Any],
    step_id: str | None = None,
) -> Any:
    """
    Membrane egress: intent → policy (emit tool.call) → inject secrets → execute → result.

    Live credentials are added only after constraints pass, and only into the in-memory
    execute args. Spine events are redacted by ``session.emit``.
    """
    payload_base = {"tool": tool, "skill_id": skill_id, "args": dict(args or {})}
    if step_id:
        payload_base["step_id"] = step_id
    cap_id = (args or {}).get("capability_id") or (args or {}).get("capability")
    if cap_id and "capability_id" not in payload_base:
        payload_base["capability_id"] = cap_id

    session.emit(
        "tool.intent",
        {**payload_base, "membrane": "egress"},
        step_id=step_id,
    )

    try:
        session.emit("tool.call", payload_base, step_id=step_id)
    except (ApprovalRequired, ConstraintViolation):
        raise

    from aura.core.capabilities import matching_capability, prepare_live_args

    constraint_results = session.state.get("_last_constraint_results") or []
    try:
        live_args = prepare_live_args(session, payload_base, constraint_results=constraint_results)
    except SecretNotFoundError as exc:
        cap = matching_capability(session, payload_base)
        session.emit(
            "tool.error",
            {
                **payload_base,
                "error": "secret_broker_unresolved",
                "secret_ref": exc.ref,
                "capability_id": cap.id if cap else None,
            },
            step_id=step_id,
        )
        raise

    cap = matching_capability(session, payload_base)
    injected = bool(cap and cap.secret_ref and cap.inject_as in live_args)
    if injected and cap is not None:
        session.emit(
            "capability.injected",
            {
                "capability_id": cap.id,
                "tool": tool,
                "skill_id": skill_id,
                "secret_ref": cap.secret_ref,
                "inject_as": cap.inject_as,
            },
            step_id=step_id,
        )

    try:
        result = _invoke_execute(execute, live_args)
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
