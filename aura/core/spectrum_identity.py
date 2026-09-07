"""Spectrum-aware verified operator identity policy (#73)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aura.config import get_config
from aura.core.spectrum_enforcement import effective_spectrum

if TYPE_CHECKING:
    from aura.agents.profile import AgentProfile
    from aura.identity.bind import IdentityOptions

LEVEL_DEFAULT_VERIFIED_IDENTITY: dict[str, bool] = {
    "low": False,
    "mid": False,
    "high": True,
    "full": True,
}


@dataclass(frozen=True)
class VerifiedIdentityPolicy:
    """Whether the session must bind a third-party verified operator."""

    required: bool
    source: str


def _session_override(options: IdentityOptions | None) -> bool | None:
    if options is None:
        return None
    config = options.config or {}
    for key in ("require_verified", "verified_required", "required"):
        if key in config:
            return bool(config[key])
    return None


def resolve_verified_identity_required(
    profile: AgentProfile,
    *,
    identity_options: IdentityOptions | None = None,
) -> VerifiedIdentityPolicy:
    """
    Resolve whether verified operator identity is mandatory for session open.

    Precedence (most specific wins):
      1. Session ``IdentityOptions.config`` (`require_verified` / `required`)
      2. Profile ``spectrum.identity_required`` when ``spectrum`` block present
      3. Global ``identity_required`` config
      4. Level default when ``spectrum`` block present (high/full → true)
      5. Otherwise false

    Lite ``agent_ref`` / ``aura_id`` always exist; this policy applies only to
    **verified** operator identity from adapters / IdP — not manual audit labels.
    """
    override = _session_override(identity_options)
    if override is not None:
        return VerifiedIdentityPolicy(required=override, source="session_override")

    spectrum_raw = profile.spectrum if isinstance(profile.spectrum, dict) else None
    if spectrum_raw is not None and "identity_required" in spectrum_raw:
        required = bool(spectrum_raw.get("identity_required"))
        return VerifiedIdentityPolicy(required=required, source="profile.spectrum")

    global_required = bool(get_config().values.get("identity_required", False))
    if global_required:
        return VerifiedIdentityPolicy(required=True, source="global_config")

    if spectrum_raw is not None:
        level = effective_spectrum(profile).level.lower()
        if level in LEVEL_DEFAULT_VERIFIED_IDENTITY:
            required = LEVEL_DEFAULT_VERIFIED_IDENTITY[level]
            return VerifiedIdentityPolicy(required=required, source=f"level_default:{level}")

    return VerifiedIdentityPolicy(required=False, source="none")


def identity_policy_summary(profile: AgentProfile) -> dict[str, Any]:
    policy = resolve_verified_identity_required(profile)
    return {
        "verified_identity_required": policy.required,
        "verified_identity_required_source": policy.source,
    }
