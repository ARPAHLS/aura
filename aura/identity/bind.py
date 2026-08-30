"""Bind operator identity at session open."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from aura.config import get_config
from aura.identity.errors import IdentityRequiredError
from aura.identity.models import OperatorIdentity
from aura.identity.protocol import IdentityContext, OperatorIdentityAdapter
from aura.identity.registry import adapter_chain_from_config


@dataclass
class IdentityOptions:
    """Per-session identity resolution inputs."""

    adapter: OperatorIdentityAdapter | None = None
    operator: dict[str, Any] | None = None
    config: dict[str, Any] = field(default_factory=dict)


def _merged_identity_config(options: IdentityOptions | None) -> dict[str, Any]:
    cfg = get_config().values
    merged: dict[str, Any] = {}
    identity_cfg = cfg.get("identity")
    if isinstance(identity_cfg, dict):
        merged.update(identity_cfg)
    if options and options.config:
        merged.update(options.config)
    if options and options.operator:
        merged["operator"] = options.operator
    return merged


def _identity_from_profile_types(types: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not types:
        return {}
    for entry in types:
        if not isinstance(entry, dict):
            continue
        if entry.get("role") == "identity":
            config = entry.get("config")
            if isinstance(config, dict):
                out = dict(config)
                if entry.get("type_id"):
                    out.setdefault("type_id", entry["type_id"])
                return out
    return {}


def resolve_operator_identity(
    session: Any,
    options: IdentityOptions | None = None,
) -> OperatorIdentity | None:
    """Resolve operator without mutating session (for pre-spine validation)."""
    profile = session.profile
    merged = _merged_identity_config(options)
    merged.update(_identity_from_profile_types(getattr(profile, "types", None)))

    context = IdentityContext(
        session_id=session.session_id,
        aura_id=profile.aura_id,
        agent_ref=profile.agent_ref,
        profile_ids=dict(profile.ids or {}),
        config=merged,
        env=dict(os.environ),
    )

    if options and options.adapter is not None:
        return options.adapter.resolve(context)

    for adapter in adapter_chain_from_config(merged):
        identity = adapter.resolve(context)
        if identity is not None:
            return identity
    return None


def bind_operator_identity(
    session: Any, options: IdentityOptions | None = None
) -> OperatorIdentity | None:
    """Attach operator to session; does not emit spine events."""
    identity = resolve_operator_identity(session, options)
    required = bool(get_config().values.get("identity_required", False))
    merged = _merged_identity_config(options)
    if merged.get("required") is True:
        required = True

    if identity is None and required:
        raise IdentityRequiredError(session.session_id)

    if identity is not None:
        session._operator_identity = identity
        session._identity_ids_overlay = {"operator": identity.to_operator_dict()}
    return identity
