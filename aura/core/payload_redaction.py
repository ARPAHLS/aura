"""Redact credential-like fields from spine and export payloads (#48)."""

from __future__ import annotations

from typing import Any

REDACTED = "[redacted]"

# Usage counters — not credentials.
_KEEP_KEYS = frozenset({"tokens", "token_count", "total_tokens", "max_tokens"})

_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
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

_SECRET_SUFFIXES = ("_token", "_secret", "_password", "_api_key", "_private_key")

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


def _scrub_string(text: str, secret_values: set[str]) -> str:
    out = text
    for value in sorted(secret_values, key=len, reverse=True):
        if len(value) >= _MIN_SCRUB_LEN and value in out:
            out = out.replace(value, REDACTED)
    return out


def redact_payload(
    payload: Any,
    *,
    secret_values: set[str] | None = None,
) -> Any:
    """Deep-copy payload replacing secret keys and known live secret substrings."""
    secrets = {str(item) for item in (secret_values or set()) if item}
    return _redact(payload, secrets)


def _redact(value: Any, secrets: set[str]) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, inner in value.items():
            if secret_like_key(str(key)):
                out[key] = REDACTED
            else:
                out[key] = _redact(inner, secrets)
        return out
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item, secrets) for item in value)
    if isinstance(value, str) and secrets:
        return _scrub_string(value, secrets)
    return value
