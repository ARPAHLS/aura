"""ToolHost protocol — host-agnostic adapter contract."""

from __future__ import annotations

from typing import Any, Protocol


class SkillExecutor(Protocol):
    """Minimal skill surface for host adapters."""

    skill_id: str

    def execute(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
    ) -> Any: ...


class ToolHost(Protocol):
    """
    Any capability runtime that registers skills and routes execution through
    the membrane egress (policy + audit).
    """

    def register(self, skill: SkillExecutor) -> None: ...

    def execute(
        self,
        skill_id: str,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
        step_id: str | None = None,
    ) -> Any: ...


class AsyncSkillExecutor(Protocol):
    """Async skill surface for non-blocking host adapters (Skillware 0.6+)."""

    skill_id: str

    async def aexecute(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
    ) -> Any: ...


class AsyncToolHost(ToolHost, Protocol):
    """ToolHost extension supporting non-blocking async egress execution."""

    async def aexecute(
        self,
        skill_id: str,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
        step_id: str | None = None,
        timeout: float | None = None,
    ) -> Any: ...
