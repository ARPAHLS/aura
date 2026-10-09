"""Load Skillware registry skills for AURA ToolHost adapters."""

from __future__ import annotations

import inspect
from typing import Any


class SkillwareRegistrySkill:
    """
    Wraps a Skillware BaseSkill instance for SkillwareHost.

    Skillware skills implement ``execute(params: dict)``; AURA passes ``(tool, args)``
    where ``tool`` is the audit label (typically the registry skill id or manifest name).
    """

    def __init__(
        self,
        skill_id: str,
        instance: Any,
        manifest: dict[str, Any],
        *,
        instructions: str = "",
    ) -> None:
        self.skill_id = skill_id
        self._instance = instance
        self.manifest = dict(manifest)
        self.instructions = instructions
        if "guardrails" not in self.manifest and manifest.get("constitution"):
            self.manifest.setdefault(
                "constitution",
                manifest.get("constitution"),
            )

    def execute(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
    ) -> Any:
        params = dict(args or {})
        execute_fn = self._instance.execute
        try:
            sig = inspect.signature(execute_fn)
            params_list = list(sig.parameters.values())
        except (TypeError, ValueError):
            return execute_fn(params)

        if not params_list:
            return execute_fn()

        has_headers = "headers" in sig.parameters

        first = params_list[0]
        if first.name in ("params", "parameters", "payload") or len(params_list) == 1:
            if has_headers:
                return execute_fn(params, headers=headers)
            return execute_fn(params)

        # MockSkill-style: execute(tool, args)
        if len(params_list) >= 2:
            if has_headers:
                return execute_fn(tool, params, headers=headers)
            return execute_fn(tool, params)
        if has_headers:
            return execute_fn(params, headers=headers)
        return execute_fn(params)


def load_registry_skill(skill_id: str) -> SkillwareRegistrySkill:
    """Load a bundled Skillware skill by registry id (e.g. optimization/prompt_rewriter)."""
    from skillware.core.loader import SkillLoader

    bundle = SkillLoader.load_skill(skill_id)
    skill_class = bundle.get("class")
    if skill_class is None:
        raise RuntimeError(f"Skill class not found for {skill_id}")
    instance = skill_class()
    manifest = dict(bundle.get("manifest") or {})
    if manifest.get("name") and manifest["name"] != skill_id:
        skill_id = str(manifest["name"])
    instructions = str(bundle.get("instructions") or "")
    return SkillwareRegistrySkill(skill_id, instance, manifest, instructions=instructions)


def load_registry_skills(skill_ids: list[str]) -> list[SkillwareRegistrySkill]:
    return [load_registry_skill(sid) for sid in skill_ids]
