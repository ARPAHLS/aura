"""Mock verified operator for CI and local demos."""

from __future__ import annotations

from aura.identity.models import OperatorIdentity
from aura.identity.protocol import IdentityContext


class MockIdentityAdapter:
    method = "mock"

    def __init__(
        self,
        *,
        subject: str = "mock-operator",
        email: str | None = "operator@example.com",
        verified: bool = True,
    ) -> None:
        self._subject = subject
        self._email = email
        self._verified = verified

    def resolve(self, context: IdentityContext) -> OperatorIdentity | None:
        cfg = context.config
        if cfg.get("adapter") not in (None, "mock", self.method):
            return None
        if not cfg.get("enabled", True):
            return None
        subject = str(
            cfg.get("subject") or context.env.get("AURA_MOCK_OPERATOR_SUBJECT") or self._subject
        )
        email = cfg.get("email") or context.env.get("AURA_MOCK_OPERATOR_EMAIL") or self._email
        return OperatorIdentity(
            verified=bool(cfg.get("verified", self._verified)),
            method=self.method,
            subject=subject,
            email=str(email) if email else None,
            session_ref=context.session_id,
        )
