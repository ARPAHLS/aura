"""Verified identity requirement checks at session bind."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aura.core.spectrum_identity import VerifiedIdentityPolicy, resolve_verified_identity_required
from aura.identity.errors import IdentityRequiredError
from aura.identity.models import OperatorIdentity

if TYPE_CHECKING:
    from aura.identity.bind import IdentityOptions


def enforce_verified_identity_policy(
    session: Any,
    identity: OperatorIdentity | None,
    *,
    identity_options: IdentityOptions | None,
) -> VerifiedIdentityPolicy:
    """
    Apply verified identity policy; raise IdentityRequiredError when blocked.

    Stores ``session._verified_identity_policy`` for audit / session.open summary.
    """
    profile = session.profile
    policy = resolve_verified_identity_required(profile, identity_options=identity_options)
    session._verified_identity_policy = policy

    if not policy.required:
        return policy

    session_id = getattr(session, "session_id", None)
    if identity is None:
        raise IdentityRequiredError(
            session_id,
            reason="no_verified_operator",
            source=policy.source,
            detail=(
                "Verified operator identity is required for this session but no operator "
                "was resolved. Configure an identity adapter (OIDC, Auth0, mock) or pass "
                "identity_adapter= / session operator with verified=true."
            ),
        )

    if not identity.verified:
        raise IdentityRequiredError(
            session_id,
            reason="operator_not_verified",
            source=policy.source,
            detail=(
                f"Operator '{identity.subject}' was resolved via {identity.method} but is not "
                "verified. This session requires verified identity from your IdP / adapter."
            ),
            method=identity.method,
            subject=identity.subject,
        )

    return policy
