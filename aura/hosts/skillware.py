"""Skillware host — wrap Skillware execute() through the membrane egress."""

from __future__ import annotations

from typing import Any

from aura.hosts.bind import record_skill_bind
from aura.hosts.manifest import manifest_snapshot_hash, merge_manifest_into_rules
from aura.hosts.protocol import SkillExecutor
from aura.hosts.skillware_adapter import SkillwareRegistrySkill, load_registry_skill
from aura.membrane.egress import guarded_tool_call


class SkillwareHost:
    """
    Reference ToolHost adapter for Skillware skills.
    All tool execution passes through AURA egress (policy + audit).
    """

    def __init__(self, session: Any) -> None:
        self.session = session
        self._skills: dict[str, SkillExecutor] = {}

    def register(self, skill: SkillExecutor) -> None:
        self._skills[skill.skill_id] = skill
        manifest = getattr(skill, "manifest", None)
        if isinstance(manifest, dict) and manifest:
            self._bind_manifest(skill.skill_id, manifest)

    def register_registry_skill(self, skill_id: str) -> SkillwareRegistrySkill:
        """Load a Skillware registry skill and register it on this host."""
        skill = load_registry_skill(skill_id)
        self.register(skill)
        return skill

    def register_by_id(
        self, skill_id: str, skill: Any, *, manifest: dict[str, Any] | None = None
    ) -> None:
        """Wrap a Skillware BaseSkill or mock skill instance."""
        wrapped = _wrap_skillware_instance(skill_id, skill)
        skill_manifest = manifest or getattr(skill, "manifest", None)
        if isinstance(skill_manifest, dict):
            wrapped.manifest = skill_manifest  # type: ignore[attr-defined]
        self.register(wrapped)

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

        def run(live_args: dict[str, Any]) -> Any:
            return skill.execute(tool, live_args)

        audit_tool = tool or skill_id
        return guarded_tool_call(
            self.session,
            tool=audit_tool,
            skill_id=skill_id,
            args=args,
            execute=run,
            step_id=step_id,
        )

    @classmethod
    def from_skillware(cls, session: Any, skills: list[Any]) -> "SkillwareHost":
        """Build host from Skillware BaseSkill instances or SkillwareRegistrySkill adapters."""
        host = cls(session)
        for skill in skills:
            if isinstance(skill, SkillwareRegistrySkill):
                host.register(skill)
                continue
            skill_id = getattr(skill, "skill_id", None) or getattr(
                skill, "id", type(skill).__name__
            )
            manifest = getattr(skill, "manifest", None)
            host.register_by_id(
                str(skill_id),
                skill,
                manifest=manifest if isinstance(manifest, dict) else None,
            )
        return host

    @classmethod
    def from_registry(cls, session: Any, skill_ids: list[str]) -> "SkillwareHost":
        """Load and register Skillware registry skills by id."""
        host = cls(session)
        for skill_id in skill_ids:
            host.register_registry_skill(skill_id)
        return host

    def _bind_manifest(self, skill_id: str, manifest: dict[str, Any]) -> None:
        session = self.session
        session.rules = merge_manifest_into_rules(session.rules, skill_id, manifest)
        snapshot = manifest_snapshot_hash(skill_id, manifest)
        session.snapshot_hash = _recompute_snapshot_hash(session)
        record_skill_bind(
            session,
            skill_id=skill_id,
            manifest_snapshot_hash=snapshot,
            host_kind="skillware",
        )


def _wrap_skillware_instance(skill_id: str, skill: Any) -> SkillExecutor:
    class _Wrapped:
        def __init__(self) -> None:
            self.skill_id = skill_id
            self._skill = skill
            self.manifest: dict[str, Any] = {}

        def execute(self, tool: str, args: dict[str, Any] | None = None) -> Any:
            adapter = SkillwareRegistrySkill(
                self.skill_id,
                self._skill,
                self.manifest,
            )
            return adapter.execute(tool, args)

    return _Wrapped()


def _recompute_snapshot_hash(session: Any) -> str:
    from aura.core.session import _snapshot_hash

    return _snapshot_hash(session.profile, session.rules)


def skillware_available() -> bool:
    try:
        import skillware  # noqa: F401

        return True
    except ImportError:
        return False
