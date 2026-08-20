"""Agent registry — monotonic AURA-000n, aliases, no identity service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aura.agents.profile import AgentProfile
from aura.config import get_config

RESERVED_FIRST = "AURA-0001"


class DuplicateAgentError(ValueError):
    pass


class AgentNotFoundError(KeyError):
    pass


class AgentRegistry:
    """Local address book + monotonic counter."""

    def __init__(self, base_dir: Path | None = None) -> None:
        cfg = get_config()
        self.base_dir = base_dir or cfg.registry_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = cfg.state_file()
        self._state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if self._state_path.is_file():
            with self._state_path.open(encoding="utf-8") as f:
                return json.load(f)
        return {"counter": 0, "aliases": {}}

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with self._state_path.open("w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2)

    def _next_aura_id(self) -> str:
        self._state["counter"] = int(self._state.get("counter", 0)) + 1
        aura_id = f"AURA-{self._state['counter']:04d}"
        self._save_state()
        return aura_id

    def _agent_path(self, aura_id: str) -> Path:
        return self.base_dir / f"{aura_id}.json"

    def _register_alias(self, name: str, aura_id: str) -> None:
        aliases: dict[str, str] = self._state.setdefault("aliases", {})
        existing = aliases.get(name)
        if existing and existing != aura_id:
            raise DuplicateAgentError(f"Agent name already in use: {name}")
        aliases[name] = aura_id
        self._save_state()

    def create(
        self,
        name: str | None = None,
        *,
        purpose: str | None = None,
        variables: dict[str, Any] | None = None,
        rules: list[dict[str, Any]] | None = None,
        skills: list[str] | None = None,
        sequencer: dict[str, Any] | None = None,
        observers: list[dict[str, Any]] | None = None,
        ids: dict[str, Any] | None = None,
        default_mode: str = "script",
    ) -> AgentProfile:
        if name:
            aliases: dict[str, str] = self._state.get("aliases", {})
            if name in aliases and not self.get_by_id(aliases[name]).archived:
                raise DuplicateAgentError(f"Agent name already in use: {name}")

        aura_id = self._next_aura_id()
        if self._state["counter"] == 1 and aura_id != RESERVED_FIRST:
            pass  # first assigned is AURA-0001 by counter logic

        profile = AgentProfile(
            aura_id=aura_id,
            name=name,
            ids=ids or {},
            purpose=purpose,
            variables=variables or {},
            rules=rules or [],
            skills=skills or [],
            sequencer=sequencer,
            observers=observers or [],
            default_mode=default_mode,
        )
        self.save(profile)
        if name:
            self._register_alias(name, aura_id)
        return profile

    def save(self, profile: AgentProfile) -> None:
        path = self._agent_path(profile.aura_id)
        with path.open("w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2)

    def get_by_id(self, aura_id: str) -> AgentProfile:
        path = self._agent_path(aura_id)
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

    def get_or_create(self, name: str, **kwargs: Any) -> AgentProfile:
        try:
            return self.get_by_name(name)
        except AgentNotFoundError:
            return self.create(name=name, **kwargs)

    def list_agents(self, include_archived: bool = False) -> list[AgentProfile]:
        profiles: list[AgentProfile] = []
        for path in sorted(self.base_dir.glob("AURA-*.json")):
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
            self._save_state()
        return profile
