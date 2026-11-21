"""Load Skillware registry skills for AURA ToolHost adapters."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable
import warnings


class SkillwareRegistrySkill:
    """
    Wraps a Skillware BaseSkill instance for SkillwareHost.

    Skillware skills implement ``execute(params: dict)`` (and ``aexecute(params: dict)`` in 0.6+);
    AURA passes ``(tool, args)`` where ``tool`` is the audit label (typically the registry skill id
    or manifest name).
    """

    def __init__(
        self,
        skill_id: str,
        instance: Any,
        manifest: dict[str, Any],
        *,
        instructions: str = "",
        root_tier: str | None = None,
    ) -> None:
        self.skill_id = skill_id
        self._instance = instance
        self.manifest = dict(manifest)
        self.instructions = instructions
        self.root_tier = root_tier
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

    async def aexecute(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
    ) -> Any:
        params = dict(args or {})
        aexecute_fn = getattr(self._instance, "aexecute", None)
        if callable(aexecute_fn):
            try:
                sig = inspect.signature(aexecute_fn)
                params_list = list(sig.parameters.values())
                has_headers = "headers" in sig.parameters
                if not params_list:
                    return await aexecute_fn()
                first = params_list[0]
                if first.name in ("params", "parameters", "payload") or len(params_list) == 1:
                    if has_headers:
                        return await aexecute_fn(params, headers=headers)
                    return await aexecute_fn(params)
                if len(params_list) >= 2:
                    if has_headers:
                        return await aexecute_fn(tool, params, headers=headers)
                    return await aexecute_fn(tool, params)
            except (TypeError, ValueError):
                return await aexecute_fn(params)
        return await asyncio.to_thread(self.execute, tool, args, headers=headers)


def make_broker_credential_fn(session: Any) -> Callable[[str], str | None] | None:
    """
    Build a Skillware 0.6 ``credential_fn`` backed by AURA's session ``SecretBroker``.

    Resolved values are registered with AURA's spine leak-scrubbing set so live credentials
    can never appear unredacted in audit logs even if a skill echoes them.
    """
    from aura.core.capabilities import STATE_INJECTED_SECRETS, STATE_SECRET_BROKER

    broker = getattr(session, "_secret_broker", None) or (getattr(session, "state", {}) or {}).get(
        STATE_SECRET_BROKER
    )
    if broker is None:
        return None

    def _resolve(key: str) -> str | None:
        candidates = [f"env:{key}", key]
        for ref in candidates:
            try:
                value = broker.resolve(ref)
            except Exception:
                continue
            if value:
                text = str(value).strip()
                if text:
                    session_state = getattr(session, "state", None)
                    if isinstance(session_state, dict):
                        seen: set[str] = session_state.setdefault(STATE_INJECTED_SECRETS, set())
                        seen.add(text)
                    return text
        return None

    return _resolve


def _instantiate_skill_class(
    skill_class: Any,
    *,
    config: dict[str, Any] | None = None,
    credential_fn: Callable[[str], str | None] | None = None,
) -> Any:
    kwargs: dict[str, Any] = {}
    try:
        sig = inspect.signature(skill_class.__init__)
        if config is not None and "config" in sig.parameters:
            kwargs["config"] = config
        if credential_fn is not None and "credential_fn" in sig.parameters:
            kwargs["credential_fn"] = credential_fn
    except (TypeError, ValueError):
        pass
    return skill_class(**kwargs)


def load_registry_skill(
    skill_id: str,
    *,
    config: dict[str, Any] | None = None,
    credential_fn: Callable[[str], str | None] | None = None,
    check_requirements: bool = True,
) -> SkillwareRegistrySkill:
    """Load a bundled Skillware skill by registry id (e.g. optimization/prompt_rewriter)."""
    from skillware.core.loader import SkillLoader

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        try:
            sig = inspect.signature(SkillLoader.load_skill)
            if "check_requirements" in sig.parameters:
                bundle = SkillLoader.load_skill(skill_id, check_requirements=check_requirements)
            else:
                bundle = SkillLoader.load_skill(skill_id)
        except (TypeError, ValueError):
            bundle = SkillLoader.load_skill(skill_id)

    skill_class = bundle.get("class")
    if skill_class is None:
        raise RuntimeError(f"Skill class not found for {skill_id}")
    instance = _instantiate_skill_class(skill_class, config=config, credential_fn=credential_fn)
    manifest = dict(bundle.get("manifest") or {})
    if manifest.get("name") and manifest["name"] != skill_id:
        skill_id = str(manifest["name"])
    instructions = str(bundle.get("instructions") or "")
    return SkillwareRegistrySkill(skill_id, instance, manifest, instructions=instructions)


def load_registry_skills(
    skill_ids: list[str],
    *,
    config: dict[str, Any] | None = None,
    credential_fn: Callable[[str], str | None] | None = None,
    check_requirements: bool = True,
) -> list[SkillwareRegistrySkill]:
    return [
        load_registry_skill(
            sid,
            config=config,
            credential_fn=credential_fn,
            check_requirements=check_requirements,
        )
        for sid in skill_ids
    ]
