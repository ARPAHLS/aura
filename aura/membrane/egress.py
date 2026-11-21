"""Egress — policy gate before tool/skill execution reaches the host body."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
import inspect
import time
from typing import Any, Callable, Iterator, Mapping
import uuid

from aura.core.constraints import ApprovalRequired, ConstraintViolation
from aura.core.finops import estimate_cost_usd
from aura.core.secrets import SecretNotFoundError

_active_egress: ContextVar[dict[str, Any] | None] = ContextVar(
    "aura_active_egress_span",
    default=None,
)


@contextmanager
def active_egress_context(
    *,
    span_id: str,
    skill_id: str | None = None,
    tool: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Mark the current sync/async execution frame as guarded by AURA membrane egress."""
    frame: dict[str, Any] = {
        "span_id": span_id,
        "skill_id": skill_id,
        "tool": tool,
        "dispatches": [],
    }
    token = _active_egress.set(frame)
    try:
        yield frame
    finally:
        _active_egress.reset(token)


def current_egress_span() -> dict[str, Any] | None:
    """Return the active AURA egress frame if currently inside guarded_tool_call(_async)."""
    return _active_egress.get()


def extract_provenance_hash(result: Any) -> str | None:
    """Extract cryptographic provenance report_hash from Skillware 0.6.2+ skill outputs."""
    if not isinstance(result, Mapping):
        return None
    prov = result.get("provenance")
    if isinstance(prov, Mapping):
        report_hash = prov.get("report_hash")
        if isinstance(report_hash, str) and report_hash.strip():
            return report_hash.strip()
    direct = result.get("report_hash")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    return None


def _build_egress_telemetry(
    *,
    skill_id: str | None,
    skill_version: str | None,
    duration_ms: float,
    audit_meta: Mapping[str, Any] | None,
    egress_frame: Mapping[str, Any] | None,
    result: Any = None,
) -> dict[str, Any]:
    meta = dict(audit_meta) if audit_meta else {}
    dispatches = list((egress_frame or {}).get("dispatches") or [])
    last_dispatch = dispatches[-1] if dispatches else {}

    telemetry: dict[str, Any] = {
        "latency_ms": round(duration_ms, 3),
    }
    if skill_id:
        telemetry["skill_id"] = skill_id
    if skill_version:
        telemetry["skill_version"] = skill_version

    model = meta.get("model") or last_dispatch.get("model")
    prompt_tokens = meta.get("prompt_tokens")
    if prompt_tokens is None:
        prompt_tokens = last_dispatch.get("prompt_tokens")
    completion_tokens = meta.get("completion_tokens")
    if completion_tokens is None:
        completion_tokens = last_dispatch.get("completion_tokens")

    if model is not None:
        telemetry["model"] = str(model)
    if prompt_tokens is not None:
        telemetry["prompt_tokens"] = int(prompt_tokens)
    if completion_tokens is not None:
        telemetry["completion_tokens"] = int(completion_tokens)

    cost = meta.get("estimated_cost_usd")
    if cost is None:
        cost = last_dispatch.get("estimated_cost_usd")
    if (
        cost is None
        and model is not None
        and prompt_tokens is not None
        and completion_tokens is not None
    ):
        cost = estimate_cost_usd(str(model), int(prompt_tokens), int(completion_tokens))
    if cost is not None:
        telemetry["estimated_cost_usd"] = float(cost)

    prov_hash = extract_provenance_hash(result)
    if prov_hash:
        telemetry["provenance_hash"] = prov_hash

    sw_hash = last_dispatch.get("skillware_event_hash")
    if sw_hash:
        telemetry["skillware_event_hash"] = str(sw_hash)

    return telemetry


def _invoke_execute(execute: Callable[..., Any], live_args: dict[str, Any]) -> Any:
    """Call execute(live_args) when the callable accepts an argument; else execute()."""
    try:
        signature = inspect.signature(execute)
    except (TypeError, ValueError):
        return execute()

    headers = live_args.get("headers") if isinstance(live_args.get("headers"), dict) else None
    accepts_headers = "headers" in signature.parameters

    required = [
        param
        for param in signature.parameters.values()
        if param.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and param.default is inspect.Parameter.empty
    ]
    if accepts_headers and headers is not None:
        if required:
            return execute(live_args, headers=headers)
        return execute(headers=headers)
    if required:
        return execute(live_args)
    for param in signature.parameters.values():
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            return execute(live_args)
    return execute()


def _egress_preflight(
    session: Any,
    *,
    tool: str,
    skill_id: str | None,
    args: dict[str, Any] | None,
    headers: dict[str, Any] | None,
    step_id: str | None,
    audit_meta: Mapping[str, Any] | None,
    is_async: bool = False,
) -> tuple[dict[str, Any], str, dict[str, Any], dict[str, Any]]:
    meta = dict(audit_meta) if audit_meta else {}
    span_id = str(meta.get("span_id") or uuid.uuid4().hex[:16])

    payload_base: dict[str, Any] = {"tool": tool, "skill_id": skill_id, "args": dict(args or {})}
    if headers:
        payload_base["headers"] = dict(headers)
    if step_id:
        payload_base["step_id"] = step_id
    cap_id = (args or {}).get("capability_id") or (args or {}).get("capability")
    if cap_id and "capability_id" not in payload_base:
        payload_base["capability_id"] = cap_id

    intent_payload = {**payload_base, "membrane": "egress"}
    if is_async:
        intent_payload["async"] = True
    session.emit("tool.intent", intent_payload, step_id=step_id, span_id=span_id)

    try:
        session.emit("tool.call", payload_base, step_id=step_id, span_id=span_id)
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
                "error_type": type(exc).__name__,
                "secret_ref": exc.ref,
                "capability_id": cap.id if cap else None,
            },
            step_id=step_id,
            span_id=span_id,
        )
        raise

    cap = matching_capability(session, payload_base)
    if cap is not None and cap.inject:
        injected_records = [
            {"secret_ref": target.ref, "inject_as": target.as_}
            for target in cap.inject
            if target.ref
        ]
        if injected_records:
            session.emit(
                "capability.injected",
                {
                    "capability_id": cap.id,
                    "tool": tool,
                    "skill_id": skill_id,
                    "secret_ref": cap.secret_ref,
                    "inject_as": cap.inject_as,
                    "injected": injected_records,
                },
                step_id=step_id,
                span_id=span_id,
            )

    return payload_base, span_id, meta, live_args


def _egress_emit_error(
    session: Any,
    *,
    payload_base: dict[str, Any],
    step_id: str | None,
    span_id: str,
    skill_id: str | None,
    skill_version: str | None,
    duration_ms: float,
    meta: Mapping[str, Any],
    egress_frame: Mapping[str, Any],
    error_message: str,
    error_type: str,
    timeout_seconds: float | None = None,
) -> None:
    telemetry = _build_egress_telemetry(
        skill_id=skill_id,
        skill_version=skill_version,
        duration_ms=duration_ms,
        audit_meta=meta,
        egress_frame=egress_frame,
    )
    err_payload: dict[str, Any] = {
        **payload_base,
        "error": error_message,
        "error_type": error_type,
        "duration_ms": round(duration_ms, 3),
    }
    if timeout_seconds is not None:
        err_payload["timeout_seconds"] = timeout_seconds
    session.emit("tool.error", err_payload, step_id=step_id, span_id=span_id, telemetry=telemetry)


def _egress_emit_result(
    session: Any,
    *,
    payload_base: dict[str, Any],
    step_id: str | None,
    span_id: str,
    skill_id: str | None,
    skill_version: str | None,
    duration_ms: float,
    meta: Mapping[str, Any],
    egress_frame: Mapping[str, Any],
    result: Any,
) -> None:
    telemetry = _build_egress_telemetry(
        skill_id=skill_id,
        skill_version=skill_version,
        duration_ms=duration_ms,
        audit_meta=meta,
        egress_frame=egress_frame,
        result=result,
    )
    result_payload: dict[str, Any] = {
        **payload_base,
        "result": result,
        "duration_ms": round(duration_ms, 3),
    }
    if telemetry.get("provenance_hash"):
        result_payload["provenance_hash"] = telemetry["provenance_hash"]
    if telemetry.get("skillware_event_hash"):
        result_payload["skillware_event_hash"] = telemetry["skillware_event_hash"]

    session.emit(
        "tool.result",
        result_payload,
        step_id=step_id,
        span_id=span_id,
        telemetry=telemetry,
    )


def guarded_tool_call(
    session: Any,
    *,
    tool: str,
    skill_id: str | None = None,
    args: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    execute: Callable[..., Any],
    step_id: str | None = None,
    audit_meta: Mapping[str, Any] | None = None,
    skill_version: str | None = None,
) -> Any:
    """
    Membrane egress: intent -> policy (emit tool.call) -> inject secrets -> execute -> result.

    Live credentials are added only after constraints pass, and only into the in-memory
    execute args. Spine events are redacted by ``session.emit``.
    """
    payload_base, span_id, meta, live_args = _egress_preflight(
        session,
        tool=tool,
        skill_id=skill_id,
        args=args,
        headers=headers,
        step_id=step_id,
        audit_meta=audit_meta,
        is_async=False,
    )

    t0 = time.perf_counter()
    with active_egress_context(span_id=span_id, skill_id=skill_id, tool=tool) as egress_frame:
        try:
            result = _invoke_execute(execute, live_args)
        except Exception as exc:
            _egress_emit_error(
                session,
                payload_base=payload_base,
                step_id=step_id,
                span_id=span_id,
                skill_id=skill_id,
                skill_version=skill_version,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
                meta=meta,
                egress_frame=egress_frame,
                error_message=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    _egress_emit_result(
        session,
        payload_base=payload_base,
        step_id=step_id,
        span_id=span_id,
        skill_id=skill_id,
        skill_version=skill_version,
        duration_ms=(time.perf_counter() - t0) * 1000.0,
        meta=meta,
        egress_frame=egress_frame,
        result=result,
    )
    return result


async def _invoke_execute_async(execute: Callable[..., Any], live_args: dict[str, Any]) -> Any:
    """Await an async execute callable, or offload a sync callable to a worker thread."""
    if inspect.iscoroutinefunction(execute):
        res = _invoke_execute(execute, live_args)
        return await res
    res = await asyncio.to_thread(_invoke_execute, execute, live_args)
    if inspect.isawaitable(res):
        return await res
    return res


async def guarded_tool_call_async(
    session: Any,
    *,
    tool: str,
    skill_id: str | None = None,
    args: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    execute: Callable[..., Any],
    step_id: str | None = None,
    timeout: float | None = None,
    audit_meta: Mapping[str, Any] | None = None,
    skill_version: str | None = None,
) -> Any:
    """
    Async membrane egress: intent -> policy -> inject secrets -> aexecute -> result.

    Supports both native ``async def`` executors and sync callables (offloaded via
    ``asyncio.to_thread``) with optional per-call ``timeout``.
    """
    payload_base, span_id, meta, live_args = _egress_preflight(
        session,
        tool=tool,
        skill_id=skill_id,
        args=args,
        headers=headers,
        step_id=step_id,
        audit_meta=audit_meta,
        is_async=True,
    )

    t0 = time.perf_counter()
    with active_egress_context(span_id=span_id, skill_id=skill_id, tool=tool) as egress_frame:
        try:
            coro = _invoke_execute_async(execute, live_args)
            if timeout is not None and timeout > 0:
                result = await asyncio.wait_for(coro, timeout=timeout)
            else:
                result = await coro
        except asyncio.TimeoutError as exc:
            _egress_emit_error(
                session,
                payload_base=payload_base,
                step_id=step_id,
                span_id=span_id,
                skill_id=skill_id,
                skill_version=skill_version,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
                meta=meta,
                egress_frame=egress_frame,
                error_message=f"Tool execution timed out after {timeout}s",
                error_type="TimeoutError",
                timeout_seconds=timeout,
            )
            raise exc
        except Exception as exc:
            _egress_emit_error(
                session,
                payload_base=payload_base,
                step_id=step_id,
                span_id=span_id,
                skill_id=skill_id,
                skill_version=skill_version,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
                meta=meta,
                egress_frame=egress_frame,
                error_message=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    _egress_emit_result(
        session,
        payload_base=payload_base,
        step_id=step_id,
        span_id=span_id,
        skill_id=skill_id,
        skill_version=skill_version,
        duration_ms=(time.perf_counter() - t0) * 1000.0,
        meta=meta,
        egress_frame=egress_frame,
        result=result,
    )
    return result
