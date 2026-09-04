"""Aura Spectrum — levels, services, budgets, output profiles."""

from dataclasses import dataclass, field
from typing import Any

COAT_BY_LEVEL: dict[str, str] = {
    "low": "loose",
    "mid": "tight",
    "high": "tight",
    "full": "tailored",
}


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
            level=str(raw.get("level", "mid")),
            services=list(raw.get("services") or ["monitor", "audit"]),
            output=list(raw.get("output") or ["aura-json"]),
            budgets=dict(raw.get("budgets") or {}),
        )

    @classmethod
    def from_profile(cls, profile: dict[str, Any]) -> "Spectrum":
        return cls.from_manifest(profile)

    def coat(self) -> str:
        """Map spectrum level to loose / tight / tailored coat metaphor."""
        return COAT_BY_LEVEL.get(self.level.lower(), "tight")

    def planes(self) -> dict[str, bool]:
        """Three planes: audit (always), enforce, escalate — docs + #27 preview."""
        level = self.level.lower()
        return {
            "audit": True,
            "enforce": level in {"mid", "high", "full"},
            "escalate": level in {"high", "full"} or "break" in self.services,
        }

    def summary(self) -> dict[str, Any]:
        planes = self.planes()
        return {
            "level": self.level,
            "coat": self.coat(),
            "services": list(self.services),
            "planes": planes,
        }
