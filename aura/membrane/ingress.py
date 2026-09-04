"""Ingress — session context before the host cavity runs."""

from __future__ import annotations

from typing import Any

from aura.agents.profile import AgentProfile
from aura.core.spectrum import Spectrum


def build_ingress_context(
    profile: AgentProfile,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize agent profile into run context for the host cavity."""
    ctx: dict[str, Any] = {
        "aura_id": profile.aura_id,
        "agent_ref": profile.agent_ref,
        "name": profile.name,
        "purpose": profile.purpose,
        "policy_version": profile.policy_version,
        "ids": dict(profile.ids),
        "variables": dict(profile.variables),
        "skills": list(profile.skills),
    }
    if overrides:
        ctx.update(overrides)
    return ctx


def ingress_event_payload(
    profile: AgentProfile,
    mode: str,
    snapshot_hash: str | None,
) -> dict[str, Any]:
    payload = {
        "membrane": "ingress",
        "mode": mode,
        "snapshot_hash": snapshot_hash,
        "context": build_ingress_context(profile),
        "skills": profile.skills,
        "observers": [o.get("id") for o in profile.observers if isinstance(o, dict)],
        "agent_ref": profile.agent_ref,
        "policy_version": profile.policy_version,
    }
    if profile.spectrum:
        payload["spectrum"] = Spectrum.from_profile({"spectrum": profile.spectrum}).summary()
    return payload


def skill_registered_payload(
    profile: AgentProfile,
    *,
    skill_id: str,
    manifest_snapshot_hash: str,
    rule_count: int,
    session_snapshot_hash: str | None = None,
    bound_skill_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Normalized bind-time context when a host registers a skill."""
    return {
        "membrane": "ingress",
        "bind": "skill",
        "skill_id": skill_id,
        "manifest_snapshot_hash": manifest_snapshot_hash,
        "session_snapshot_hash": session_snapshot_hash,
        "bound_skill_ids": list(bound_skill_ids or []),
        "policy_version": profile.policy_version,
        "agent_ref": profile.agent_ref,
        "constitution_rule_count": rule_count,
        "context": build_ingress_context(profile),
    }
