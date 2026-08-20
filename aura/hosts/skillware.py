"""Skillware host — wrap Skillware execute() through the membrane egress."""

from __future__ import annotations

from typing import Any, Protocol

from aura.membrane.egress import guarded_tool_call


class SkillExecutor(Protocol):
    skill_id: str

    def execute(self, tool: str, args: dict[str, Any] | None = None) -> Any: ...


class SkillwareHost:
    """
    Host adapter for Skillware skills.
    All tool execution passes through AURA egress (policy + audit).
    """

    def __init__(self, session: Any) -> None:
        self.session = session
        self._skills: dict[str, SkillExecutor] = {}

    def register(self, skill: SkillExecutor) -> None:
        self._skills[skill.skill_id] = skill

    def register_by_id(self, skill_id: str, skill: Any) -> None:
        """Wrap a raw Skillware skill instance."""
        wrapped = _wrap_skillware_instance(skill_id, skill)
        self._skills[skill_id] = wrapped

    def execute(
        self,
        skill_id: str,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        step_id: str | None = None,
    ) -> Any:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(f"Skill not registered: {skill_id}")

        def run() -> Any:
            return skill.execute(tool, args)

        return guarded_tool_call(
            self.session,
            tool=tool,
            skill_id=skill_id,
            args=args,
            execute=run,
            step_id=step_id,
        )

    @classmethod
    def from_skillware(cls, session: Any, skills: list[Any]) -> "SkillwareHost":
        """Build host from installed Skillware skill instances."""
        host = cls(session)
        for skill in skills:
            skill_id = getattr(skill, "skill_id", None) or getattr(skill, "id", type(skill).__name__)
            host.register_by_id(str(skill_id), skill)
        return host


def _wrap_skillware_instance(skill_id: str, skill: Any) -> SkillExecutor:
    class _Wrapped:
        def __init__(self) -> None:
            self.skill_id = skill_id
            self._skill = skill

        def execute(self, tool: str, args: dict[str, Any] | None = None) -> Any:
            payload = dict(args or {})
            if hasattr(self._skill, "execute"):
                return self._skill.execute(tool, **payload)
            if hasattr(self._skill, "run"):
                return self._skill.run(tool, **payload)
            raise AttributeError(f"Skill {skill_id} has no execute/run method")

    return _Wrapped()


def skillware_available() -> bool:
    try:
        import skillware  # noqa: F401

        return True
    except ImportError:
        return False
