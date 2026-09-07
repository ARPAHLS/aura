"""Identity resolution errors."""


class IdentityError(Exception):
    """Base class for identity adapter errors."""


class IdentityRequiredError(IdentityError):
    """Session requires verified operator identity but none was resolved."""

    def __init__(
        self,
        session_id: str | None = None,
        *,
        reason: str = "verified_identity_required",
        source: str | None = None,
        detail: str | None = None,
        method: str | None = None,
        subject: str | None = None,
    ) -> None:
        self.session_id = session_id or "unknown"
        self.reason = reason
        self.source = source
        self.method = method
        self.subject = subject
        message = detail or f"Verified operator identity required for session {self.session_id}"
        if source:
            message = f"{message} (policy source: {source})"
        super().__init__(message)


class IdentityVerificationError(IdentityError):
    """Token or adapter verification failed."""

    def __init__(self, message: str, *, method: str | None = None) -> None:
        self.method = method
        prefix = f"{method}: " if method else ""
        super().__init__(f"{prefix}{message}")
