"""Constraint engine — modular rules on events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import uuid

RuleHandler = Callable[["ConstraintContext"], "ConstraintResult | None"]


class ConstraintViolation(Exception):
    def __init__(self, message: str, rule: dict[str, Any], event: dict[str, Any]) -> None:
        super().__init__(message)
        self.rule = rule
        self.event = event


class ApprovalRequired(Exception):
    """Raised when a rule needs human approval before proceeding."""

    def __init__(self, request_id: str, message: str, rule: dict[str, Any]) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.rule = rule


@dataclass
class ConstraintContext:
    event_kind: str
    payload: dict[str, Any]
    rules: list[dict[str, Any]]
    session_state: dict[str, Any]
    approved_requests: set[str] = field(default_factory=set)


@dataclass
class ConstraintResult:
    passed: bool
    rule: dict[str, Any]
    message: str
    request_id: str | None = None
    blocked: bool = False


class ConstraintEngine:
    """Evaluate declarative rules against emitted events."""

    def __init__(self) -> None:
        self._custom: list[RuleHandler] = []

    def register(self, handler: RuleHandler) -> None:
        self._custom.append(handler)

    def evaluate(self, ctx: ConstraintContext) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        for rule in ctx.rules:
            rtype = rule.get("type") or rule.get("kind")
            handler = _BUILTIN.get(rtype)
            if handler:
                result = handler(ctx, rule)
                if result:
                    results.append(result)
                    if result.blocked:
                        return results
        for handler in self._custom:
            result = handler(ctx)
            if result:
                results.append(result)
                if result.blocked:
                    return results
        return results

    def check_emit(self, ctx: ConstraintContext) -> list[ConstraintResult]:
        """Run constraints; raise on block or approval required."""
        results = self.evaluate(ctx)
        for result in results:
            if result.request_id and result.request_id not in ctx.approved_requests:
                raise ApprovalRequired(result.request_id, result.message, result.rule)
            if result.blocked:
                raise ConstraintViolation(result.message, result.rule, ctx.payload)
        return results


def _tool_name(payload: dict[str, Any]) -> str | None:
    return payload.get("tool") or payload.get("name") or payload.get("tool_name")


def _token_count(payload: dict[str, Any]) -> int:
    for key in ("tokens", "token_count", "total_tokens"):
        if key in payload:
            return int(payload[key])
    return 0


def _rule_max_tokens(ctx: ConstraintContext, rule: dict[str, Any]) -> ConstraintResult | None:
    if ctx.event_kind not in ("tool.call", "model.call", "step.end", "turn.end"):
        return None
    limit = int(rule.get("limit", rule.get("max", 0)))
    if limit <= 0:
        return None
    count = _token_count(ctx.payload)
    if count > limit:
        return ConstraintResult(
            passed=False,
            rule=rule,
            message=f"Token limit exceeded: {count} > {limit}",
            blocked=True,
        )
    return ConstraintResult(passed=True, rule=rule, message="within token limit")


def _rule_confirm_before(ctx: ConstraintContext, rule: dict[str, Any]) -> ConstraintResult | None:
    if ctx.event_kind not in ("tool.call", "action.request"):
        return None
    tools = rule.get("tools") or rule.get("actions") or []
    tool = _tool_name(ctx.payload)
    if tool not in tools:
        return None
    req_key = f"confirm:{tool}:{ctx.payload.get('request_id', '')}"
    pending: dict[str, str] = ctx.session_state.setdefault("_pending_approvals", {})
    request_id = pending.get(req_key)
    if request_id and request_id in ctx.approved_requests:
        return ConstraintResult(passed=True, rule=rule, message=f"approved: {tool}")
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:10]}"
        pending[req_key] = request_id
    return ConstraintResult(
        passed=False,
        rule=rule,
        message=f"Approval required before: {tool}",
        request_id=request_id,
        blocked=False,
    )


def _rule_allow_tools(ctx: ConstraintContext, rule: dict[str, Any]) -> ConstraintResult | None:
    if ctx.event_kind not in ("tool.call", "action.request"):
        return None
    allowed = rule.get("tools") or rule.get("allow") or []
    if not allowed:
        return None
    tool = _tool_name(ctx.payload)
    if tool not in allowed:
        return ConstraintResult(
            passed=False,
            rule=rule,
            message=f"Tool not allowed: {tool}",
            blocked=True,
        )
    return ConstraintResult(passed=True, rule=rule, message="tool allowed")


def _rule_deny_tools(ctx: ConstraintContext, rule: dict[str, Any]) -> ConstraintResult | None:
    if ctx.event_kind not in ("tool.call", "action.request"):
        return None
    denied = rule.get("tools") or rule.get("deny") or []
    tool = _tool_name(ctx.payload)
    if tool in denied:
        return ConstraintResult(
            passed=False,
            rule=rule,
            message=f"Tool denied: {tool}",
            blocked=True,
        )
    return None


_BUILTIN: dict[str, Any] = {
    "max_tokens_per_step": _rule_max_tokens,
    "confirm_before": _rule_confirm_before,
    "allow_tools": _rule_allow_tools,
    "deny_tools": _rule_deny_tools,
}
