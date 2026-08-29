"""Session and export lifecycle errors."""


class AuraSessionError(Exception):
    """Base class for session lifecycle errors."""


class SessionNotOpenError(AuraSessionError):
    """Operation requires an open session."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id
        sid = session_id or "unknown"
        super().__init__(f"Session not open: {sid}")


class SessionClosedError(AuraSessionError):
    """Session is closed; further mutations are rejected."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id
        sid = session_id or "unknown"
        super().__init__(f"Session already closed: {sid}")


class SessionAlreadyOpenError(AuraSessionError):
    """Session open() was called more than once on the same handle."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id
        sid = session_id or "unknown"
        super().__init__(f"Session already open: {sid}")


class ExportError(Exception):
    """Atomic session export failed; summary and OTel artifacts were not committed."""

    def __init__(self, session_id: str, message: str) -> None:
        self.session_id = session_id
        super().__init__(f"Export failed for {session_id}: {message}")
