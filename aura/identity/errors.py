"""Identity resolution errors."""


class IdentityError(Exception):
    """Base class for identity adapter errors."""


class IdentityRequiredError(IdentityError):
    """Session requires verified operator identity but none was resolved."""

    def __init__(self, session_id: str | None = None) -> None:
        sid = session_id or "unknown"
        super().__init__(f"Verified operator identity required for session {sid}")


class IdentityVerificationError(IdentityError):
    """Token or adapter verification failed."""

    def __init__(self, message: str, *, method: str | None = None) -> None:
        self.method = method
        prefix = f"{method}: " if method else ""
        super().__init__(f"{prefix}{message}")
