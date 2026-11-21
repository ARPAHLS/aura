"""Redact credential-like fields from spine and export payloads (#48)."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[redacted]"
_MAX_REDACT_DEPTH = 32

# Usage counters — not credentials.
_KEEP_KEYS = frozenset(
    {
        "tokens",
        "token_count",
        "total_tokens",
        "max_tokens",
        "prompt_tokens",
        "completion_tokens",
        "tokens_saved",
        "new_tokens",
        "current_token_count",
        "max_allowed_tokens",
    }
)

_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_key",
        "secret_key",
        "password",
        "passwd",
        "secret",
        "secret_value",
        "private_key",
        "authorization",
        "access_token",
        "refresh_token",
        "client_secret",
        "card_number",
        "cvv",
        "pan",
        "pin",
        "credential",
        "credentials",
        "bearer",
        "auth_token",
        "api_token",
        "session_token",
        "id_token",
        "token",
    }
)

_SECRET_SUFFIXES = (
    "_token",
    "_secret",
    "_password",
    "_api_key",
    "_private_key",
    "_access_key",
    "_secret_key",
)

# Raw credential patterns scrubbed even inside free-form text fields and error messages.
# Aligned with Skillware's audit.py _SECRET_VALUE_PATTERNS plus GitLab/Slack prefixes.
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"glpat-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"xox[bp]-[A-Za-z0-9\-]{16,}"),
    re.compile(
        r"(?i)\bbearer\s+"
        r"(?=[A-Za-z0-9\-._~+/=]*(?:[0-9_\-+~=/]|\.[A-Za-z0-9]))"
        r"[A-Za-z0-9\-._~+/]{11,}[A-Za-z0-9\-_~+/=]"
    ),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
)

# Do not treat these as inject/secret channels even if named "token".
_MIN_SCRUB_LEN = 8


def secret_like_key(key: str) -> bool:
    """True when a mapping key should never appear with a live value on the spine."""
    raw = str(key)
    lowered = raw.lower().replace("-", "_")
    if lowered in _KEEP_KEYS:
        return False
    if lowered in _SECRET_KEYS:
        return True
    return any(lowered.endswith(suffix) for suffix in _SECRET_SUFFIXES)


def strip_secret_like_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Drop credential-like keys from a live args dict (agent-supplied tokens are ignored)."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if secret_like_key(str(key)):
            continue
        if isinstance(value, dict):
            out[key] = strip_secret_like_keys(value)
        else:
            out[key] = value
    return out


def redact_secret_patterns(text: str) -> str:
    """Scrub raw credential patterns (API keys, Bearer tokens, PEM keys) from a string."""
    out = text
    for pattern in _SECRET_VALUE_PATTERNS:
        out = pattern.sub(REDACTED, out)
    return out


def _scrub_string(text: str, secret_values: set[str]) -> str:
    out = redact_secret_patterns(text)
    for value in sorted(secret_values, key=len, reverse=True):
        if len(value) >= _MIN_SCRUB_LEN and value in out:
            out = out.replace(value, REDACTED)
    return out


def redact_payload(
    payload: Any,
    *,
    secret_values: set[str] | None = None,
) -> Any:
    """Deep-copy payload replacing secret keys, credential patterns, and known live secrets."""
    secrets = {str(item) for item in (secret_values or set()) if item}
    return _redact(payload, secrets, _depth=0)


def _redact(value: Any, secrets: set[str], *, _depth: int = 0) -> Any:
    if _depth > _MAX_REDACT_DEPTH:
        return REDACTED
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, inner in value.items():
            if secret_like_key(str(key)):
                out[key] = REDACTED
            else:
                out[key] = _redact(inner, secrets, _depth=_depth + 1)
        return out
    if isinstance(value, list):
        return [_redact(item, secrets, _depth=_depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item, secrets, _depth=_depth + 1) for item in value)
    if isinstance(value, str):
        return _scrub_string(value, secrets)
    return value
