"""Optional verified operator identity adapters."""

from aura.identity.bind import IdentityOptions, bind_operator_identity, resolve_operator_identity
from aura.identity.errors import IdentityRequiredError, IdentityVerificationError
from aura.identity.models import OperatorIdentity
from aura.identity.protocol import IdentityContext, OperatorIdentityAdapter
from aura.identity.redaction import redact_agent_ids, redact_summary

__all__ = [
    "IdentityOptions",
    "IdentityContext",
    "OperatorIdentity",
    "OperatorIdentityAdapter",
    "bind_operator_identity",
    "resolve_operator_identity",
    "IdentityRequiredError",
    "IdentityVerificationError",
    "redact_agent_ids",
    "redact_summary",
]
