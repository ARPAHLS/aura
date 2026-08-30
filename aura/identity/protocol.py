"""Operator identity adapter protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from aura.identity.models import OperatorIdentity


@dataclass
class IdentityContext:
    """Inputs available when resolving operator identity at session open."""

    session_id: str
    aura_id: str
    agent_ref: str | None
    profile_ids: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)


class OperatorIdentityAdapter(Protocol):
    """Pluggable backend — Auth0, OIDC, manual, mock, corporate SSO."""

    method: str

    def resolve(self, context: IdentityContext) -> OperatorIdentity | None:
        """Return operator identity or None when this adapter does not apply."""
