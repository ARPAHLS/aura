"""Identity helpers — ULID generation and agent_ref validation."""

from __future__ import annotations

import os
import re
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_AGENT_REF_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*)(?:/[a-z0-9](?:[a-z0-9._-]*))?$",
    re.IGNORECASE,
)


def new_ulid() -> str:
    """Generate a time-sortable ULID (26 Crockford chars)."""
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    randomness = int.from_bytes(os.urandom(10), "big")
    value = (timestamp_ms << 80) | randomness
    chars: list[str] = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def is_ulid(value: str) -> bool:
    return len(value) == 26 and all(c in _CROCKFORD for c in value.upper())


def is_legacy_aura_id(value: str) -> bool:
    return bool(re.fullmatch(r"AURA-\d{4}", value))


def validate_agent_ref(agent_ref: str) -> str:
    normalized = agent_ref.strip().lower()
    if not _AGENT_REF_RE.fullmatch(normalized):
        raise ValueError(
            "agent_ref must look like 'tenant/slug' or 'slug' " "(lowercase letters, digits, . _ -)"
        )
    return normalized


def tenant_from_ref(agent_ref: str | None) -> str | None:
    if not agent_ref or "/" not in agent_ref:
        return None
    return agent_ref.split("/", 1)[0]
