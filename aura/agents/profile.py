"""Agent profile and ID trailer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentProfile:
    """Persistent agent record."""

    aura_id: str
    name: str | None = None
    ids: dict[str, Any] = field(default_factory=dict)
    purpose: str | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    rules: list[dict[str, Any]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    sequencer: dict[str, Any] | None = None
    observers: list[dict[str, Any]] = field(default_factory=list)
    default_mode: str = "script"
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "aura_id": self.aura_id,
            "name": self.name,
            "ids": self.ids,
            "purpose": self.purpose,
            "variables": self.variables,
            "rules": self.rules,
            "skills": self.skills,
            "sequencer": self.sequencer,
            "observers": self.observers,
            "default_mode": self.default_mode,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentProfile:
        return cls(
            aura_id=data["aura_id"],
            name=data.get("name"),
            ids=dict(data.get("ids") or {}),
            purpose=data.get("purpose"),
            variables=dict(data.get("variables") or {}),
            rules=list(data.get("rules") or []),
            skills=list(data.get("skills") or []),
            sequencer=data.get("sequencer"),
            observers=list(data.get("observers") or []),
            default_mode=data.get("default_mode", "script"),
            archived=bool(data.get("archived", False)),
        )

    def id_trailer(self) -> dict[str, Any]:
        """Nested ID fields for audit events."""
        trailer: dict[str, Any] = {"aura_id": self.aura_id}
        if self.name:
            trailer["name"] = self.name
        if self.ids:
            trailer["ids"] = self.ids
        return trailer
