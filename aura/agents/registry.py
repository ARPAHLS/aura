"""Agent registry — ULID ids, agent_ref, aliases, no identity service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aura.agents.profile import AgentProfile
from aura.config import get_config
from aura.core.ids import is_legacy_aura_id, new_ulid, tenant_from_ref, validate_agent_ref


class DuplicateAgentError(ValueError):
    pass


class AgentNotFoundError(KeyError):
    pass


class AgentRegistry:
    """Local address book with ULID internal ids and stable agent_ref."""

    def __init__(self, base_dir: Path | None = None) -> None:
        cfg = get_config()
        self.base_dir = base_dir or cfg.registry_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = cfg.state_file()
        self._state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if self._state_path.is_file():
            with self._state_path.open(encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"aliases": {}, "refs": {}}
        data.setdefault("aliases", {})
        data.setdefault("refs", {})
        return data

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with self._state_path.open("w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2)

    def _agent_path(self, aura_id: str) -> Path:
        safe = aura_id.replace("/", "_")
        return self.base_dir / f"{safe}.json"

    def _register_alias(self, name: str, aura_id: str) -> None:
        aliases: dict[str, str] = self._state.setdefault("aliases", {})
        existing = aliases.get(name)
        if existing and existing != aura_id:
            raise DuplicateAgentError(f"Agent name already in use: {name}")
        aliases[name] = aura_id
        self._save_state()

    def _register_ref(self, agent_ref: str, aura_id: str) -> None:
        refs: dict[str, str] = self._state.setdefault("refs", {})
        existing = refs.get(agent_ref)
        if existing and existing != aura_id:
            raise DuplicateAgentError(f"agent_ref already in use: {agent_ref}")
        refs[agent_ref] = aura_id
        self._save_state()

    def create(
        self,
        name: str | None = None,
        *,
        agent_ref: str | None = None,
        aura_id: str | None = None,
        purpose: str | None = None,
        policy_version: str = "1",
        variables: dict[str, Any] | None = None,
        rules: list[dict[str, Any]] | None = None,
        skills: list[str] | None = None,
        sequencer: dict[str, Any] | None = None,
        observers: list[dict[str, Any]] | None = None,
        ids: dict[str, Any] | None = None,
        default_mode: str = "script",
    ) -> AgentProfile:
        merged_ids = dict(ids or {})
        ref = validate_agent_ref(agent_ref) if agent_ref else None
        if not ref and name and "/" in name:
            ref = validate_agent_ref(name)

        if name:
            aliases: dict[str, str] = self._state.get("aliases", {})
            if name in aliases and not self.get_by_id(aliases[name]).archived:
                raise DuplicateAgentError(f"Agent name already in use: {name}")
        if ref:
            refs: dict[str, str] = self._state.get("refs", {})
            if ref in refs and not self.get_by_id(refs[ref]).archived:
                raise DuplicateAgentError(f"agent_ref already in use: {ref}")

        if aura_id:
            if self._agent_path(aura_id).is_file():
                raise DuplicateAgentError(f"aura_id already exists: {aura_id}")
            assigned_id = aura_id
        else:
            assigned_id = new_ulid()

        tenant = tenant_from_ref(ref)
        if tenant and "tenant" not in merged_ids:
            merged_ids["tenant"] = tenant

        profile = AgentProfile(
            aura_id=assigned_id,
            agent_ref=ref,
            name=name,
            ids=merged_ids,
            purpose=purpose,
            policy_version=str(policy_version),
            variables=variables or {},
            rules=rules or [],
            skills=skills or [],
            sequencer=sequencer,
            observers=observers or [],
            default_mode=default_mode,
        )
        self.save(profile)
        if name:
            self._register_alias(name, assigned_id)
        if ref:
            self._register_ref(ref, assigned_id)
        return profile

    def save(self, profile: AgentProfile) -> None:
        path = self._agent_path(profile.aura_id)
        with path.open("w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2)

    def profile_path(self, aura_id: str) -> Path:
        return self._agent_path(aura_id)

    def update_profile(self, key: str, **updates: Any) -> AgentProfile:
        """Apply partial updates to an existing agent profile."""
        profile = self.resolve(key)
        aura_id = profile.aura_id

        if "name" in updates and updates["name"] is not None:
            new_name = updates["name"]
            if new_name != profile.name:
                self._register_alias(new_name, aura_id)
                profile.name = new_name

        if "agent_ref" in updates:
            new_ref_raw = updates["agent_ref"]
            new_ref = validate_agent_ref(new_ref_raw) if new_ref_raw else None
            old_ref = profile.agent_ref
            refs: dict[str, str] = self._state.setdefault("refs", {})
            if old_ref and refs.get(old_ref) == aura_id and old_ref != new_ref:
                del refs[old_ref]
                self._save_state()
            if new_ref:
                self._register_ref(new_ref, aura_id)
            profile.agent_ref = new_ref
            tenant = tenant_from_ref(new_ref)
            if tenant:
                profile.ids.setdefault("tenant", tenant)

        if "purpose" in updates and updates["purpose"] is not None:
            profile.purpose = updates["purpose"]
        if "policy_version" in updates and updates["policy_version"] is not None:
            profile.policy_version = str(updates["policy_version"])
        if "default_mode" in updates and updates["default_mode"] is not None:
            profile.default_mode = updates["default_mode"]
        if updates.get("skills") is not None:
            profile.skills = list(updates["skills"])
        if updates.get("variables") is not None:
            profile.variables.update(dict(updates["variables"]))
        if updates.get("ids") is not None:
            profile.ids.update(dict(updates["ids"]))
        if updates.get("rules") is not None:
            profile.rules = list(updates["rules"])

        self.save(profile)
        return profile

    def get_by_id(self, aura_id: str) -> AgentProfile:
        path = self._agent_path(aura_id)
        if not path.is_file() and is_legacy_aura_id(aura_id):
            path = self.base_dir / f"{aura_id}.json"
        if not path.is_file():
            raise AgentNotFoundError(aura_id)
        with path.open(encoding="utf-8") as f:
            return AgentProfile.from_dict(json.load(f))

    def get_by_name(self, name: str) -> AgentProfile:
        aliases: dict[str, str] = self._state.get("aliases", {})
        aura_id = aliases.get(name)
        if not aura_id:
            raise AgentNotFoundError(name)
        return self.get_by_id(aura_id)

    def get_by_ref(self, agent_ref: str) -> AgentProfile:
        ref = validate_agent_ref(agent_ref)
        refs: dict[str, str] = self._state.get("refs", {})
        aura_id = refs.get(ref)
        if not aura_id:
            raise AgentNotFoundError(agent_ref)
        return self.get_by_id(aura_id)

    def resolve(self, key: str) -> AgentProfile:
        """Lookup by agent_ref, name alias, or aura_id."""
        try:
            return self.get_by_ref(key)
        except AgentNotFoundError:
            pass
        try:
            return self.get_by_name(key)
        except AgentNotFoundError:
            pass
        return self.get_by_id(key)

    def get_or_create(self, name: str, **kwargs: Any) -> AgentProfile:
        try:
            return self.resolve(name)
        except AgentNotFoundError:
            return self.create(name=name, **kwargs)

    def list_agents(self, include_archived: bool = False) -> list[AgentProfile]:
        profiles: list[AgentProfile] = []
        for path in sorted(self.base_dir.glob("*.json")):
            with path.open(encoding="utf-8") as f:
                profile = AgentProfile.from_dict(json.load(f))
            if profile.archived and not include_archived:
                continue
            profiles.append(profile)
        return profiles

    def archive(self, aura_id: str) -> AgentProfile:
        profile = self.get_by_id(aura_id)
        profile.archived = True
        self.save(profile)
        aliases: dict[str, str] = self._state.get("aliases", {})
        if profile.name and aliases.get(profile.name) == aura_id:
            del aliases[profile.name]
        refs: dict[str, str] = self._state.get("refs", {})
        if profile.agent_ref and refs.get(profile.agent_ref) == aura_id:
            del refs[profile.agent_ref]
        self._save_state()
        return profile
