"""Mock skill host — tests and examples without Skillware installed."""

from __future__ import annotations

from typing import Any, Callable


class MockSkill:
    """Minimal skill with a tool → handler map."""

    def __init__(
        self, skill_id: str, handlers: dict[str, Callable[[dict[str, Any]], Any]] | None = None
    ) -> None:
        self.skill_id = skill_id
        self._handlers = dict(handlers or {})

    def register(self, tool: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self._handlers[tool] = handler

    def execute(self, tool: str, args: dict[str, Any] | None = None) -> Any:
        if tool not in self._handlers:
            raise KeyError(f"Unknown tool: {tool}")
        return self._handlers[tool](args or {})


class MockSkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, MockSkill] = {}

    def add(self, skill: MockSkill) -> None:
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> MockSkill:
        if skill_id not in self._skills:
            raise KeyError(f"Skill not registered: {skill_id}")
        return self._skills[skill_id]
