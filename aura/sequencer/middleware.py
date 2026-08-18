"""Middleware stack — ordered operations per step or model request."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MiddlewarePolicy:
    scope: str = "per_step"
    order: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> "MiddlewarePolicy | None":
        raw = manifest.get("middleware")
        if not raw:
            return None
        return cls(scope=raw.get("scope", "per_step"), order=list(raw.get("order") or []))


class MiddlewareStack:
    def __init__(self, policy: MiddlewarePolicy) -> None:
        self.policy = policy

    def run_inbound(self, ctx: dict[str, Any]) -> dict[str, Any]:
        for entry in self.policy.order:
            ctx = self._invoke(entry["op"], ctx, entry.get("config") or {})
        return ctx

    def _invoke(self, op_id: str, ctx: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        return ctx
