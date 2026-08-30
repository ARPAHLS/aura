"""Manual operator identity from profile ids or session override."""

from __future__ import annotations

from typing import Any

from aura.identity.models import OperatorIdentity
from aura.identity.protocol import IdentityContext


def operator_from_mapping(
    data: dict[str, Any], *, default_method: str = "manual"
) -> OperatorIdentity | None:
    if not data:
        return None
    subject = data.get("subject") or data.get("id") or data.get("email")
    if not subject:
        return None
    verified = bool(data.get("verified", False))
    method = str(data.get("method") or default_method)
    return OperatorIdentity(
        verified=verified,
        method=method,
        subject=str(subject),
        email=data.get("email"),
        name=data.get("name"),
        session_ref=data.get("session_ref"),
        issuer=data.get("issuer"),
    )


class ManualIdentityAdapter:
    method = "manual"

    def resolve(self, context: IdentityContext) -> OperatorIdentity | None:
        override = context.config.get("operator")
        if isinstance(override, dict):
            return operator_from_mapping(override)
        profile_ids = context.profile_ids or {}
        operator = profile_ids.get("operator")
        if isinstance(operator, dict):
            return operator_from_mapping(operator)
        return None
