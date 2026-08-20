"""Ingress — session context before the host cavity runs."""

from __future__ import annotations

from typing import Any

from aura.agents.profile import AgentProfile


def build_ingress_context(profile: AgentProfile, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize agent profile into run context for the host cavity."""
    ctx: dict[str, Any] = {
        "aura_id": profile.aura_id,
        "name": profile.name,
        "purpose": profile.purpose,
        "ids": dict(profile.ids),
        "variables": dict(profile.variables),
        "skills": list(profile.skills),
    }
    if overrides:
        ctx.update(overrides)
    return ctx


def ingress_event_payload(profile: AgentProfile, mode: str, snapshot_hash: str | None) -> dict[str, Any]:
    return {
        "membrane": "ingress",
        "mode": mode,
        "snapshot_hash": snapshot_hash,
        "context": build_ingress_context(profile),
        "skills": profile.skills,
        "observers": [o.get("id") for o in profile.observers if isinstance(o, dict)],
    }
