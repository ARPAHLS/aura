"""Spectrum-derived enforcement rules merged at session open."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aura.core.spectrum import Spectrum

if TYPE_CHECKING:
    from aura.agents.profile import AgentProfile


def effective_spectrum(profile: AgentProfile) -> Spectrum:
    """Resolve spectrum for a profile (defaults to mid when unset)."""
    if profile.spectrum:
        return Spectrum.from_profile({"spectrum": profile.spectrum})
    return Spectrum.from_manifest({})


def allowed_tool_ids(profile: AgentProfile) -> list[str]:
    """Tool and skill ids declared on the profile for high/full bind."""
    tools: list[str] = list(profile.skills or [])
    sequencer = profile.sequencer or {}
    for step in sequencer.get("steps") or []:
        if not isinstance(step, dict):
            continue
        ref = step.get("ref")
        if ref:
            tools.append(str(ref))
        config = step.get("config") or {}
        if isinstance(config, dict):
            tool = config.get("tool")
            if tool:
                tools.append(str(tool))
    seen: set[str] = set()
    ordered: list[str] = []
    for item in tools:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def enforcement_rules(profile: AgentProfile) -> list[dict[str, Any]]:
    """
    Rules injected from spectrum.level (explicit profile rules always apply too).

    low  — audit only (no auto bind)
    mid  — explicit profile rules only
    high — allow_tools from declared skills / sequencer refs
    full — high + tool.call must carry step_id (sequencer bind)
    """
    spectrum = effective_spectrum(profile)
    level = spectrum.level.lower()
    rules: list[dict[str, Any]] = []

    if level in {"high", "full"}:
        allowed = allowed_tool_ids(profile)
        if allowed:
            rules.append(
                {
                    "type": "allow_tools",
                    "tools": allowed,
                    "source": "spectrum",
                    "level": level,
                }
            )

    if level == "full":
        rules.append(
            {
                "type": "sequencer_required",
                "source": "spectrum",
                "level": level,
            }
        )

    return rules


def merge_rules_with_spectrum(
    profile: AgentProfile,
    session_rules: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Profile rules + spectrum enforcement + optional session overrides."""
    merged = list(profile.rules or [])
    merged.extend(enforcement_rules(profile))
    if session_rules:
        merged.extend(session_rules)
    return merged
