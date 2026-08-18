"""Aura Spectrum — levels, services, budgets, output profiles."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Spectrum:
    level: str = "mid"
    services: list[str] = field(default_factory=lambda: ["monitor", "audit"])
    output: list[str] = field(default_factory=lambda: ["aura-json"])
    budgets: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> "Spectrum":
        raw = manifest.get("spectrum") or {}
        return cls(
            level=raw.get("level", "mid"),
            services=list(raw.get("services") or ["monitor", "audit"]),
            output=list(raw.get("output") or ["aura-json"]),
            budgets=dict(raw.get("budgets") or {}),
        )
