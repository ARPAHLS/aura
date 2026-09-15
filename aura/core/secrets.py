"""Secret brokers — resolve credential refs at egress, never store values on profiles (#48)."""

from __future__ import annotations

import os
from typing import Any, Callable, Mapping, Protocol, runtime_checkable


class SecretBrokerError(Exception):
    """Base class for capability secret resolution failures."""


class SecretConfigError(SecretBrokerError, ValueError):
    """Profile or broker configuration tried to hold a plaintext secret."""


class SecretNotFoundError(SecretBrokerError):
    """Broker could not resolve a declared secret ref."""

    def __init__(self, ref: str) -> None:
        self.ref = ref
        super().__init__(f"Secret ref not resolved: {ref}")


@runtime_checkable
class SecretBroker(Protocol):
    """Resolve a capability secret reference to a live credential."""

    def resolve(self, ref: str) -> str: ...


def normalize_secret_ref(ref: str) -> str:
    """Trim a ref; keep provider prefix (``env:NAME``, ``vault:path``, …)."""
    text = str(ref).strip()
    if not text:
        raise SecretConfigError("secret ref must be a non-empty string")
    return text


def env_key_from_ref(ref: str) -> str:
    """Map ``env:NAME`` / ``NAME`` to an environment variable name."""
    text = normalize_secret_ref(ref)
    if text.lower().startswith("env:"):
        return text.split(":", 1)[1].strip()
    if ":" in text:
        return text
    return text


class EnvSecretBroker:
    """Resolve ``env:VAR`` (or bare ``VAR``) from process environment."""

    def __init__(self, *, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ

    def resolve(self, ref: str) -> str:
        key = env_key_from_ref(ref)
        source = self._environ if self._environ is not None else os.environ
        value = source.get(key)
        if value is None or value == "":
            raise SecretNotFoundError(ref)
        return str(value)


class MapSecretBroker:
    """In-memory map for tests and host-local vault shims. Never persist on a profile."""

    def __init__(self, mapping: Mapping[str, str]) -> None:
        self._mapping = {str(key): str(value) for key, value in mapping.items()}

    def resolve(self, ref: str) -> str:
        text = normalize_secret_ref(ref)
        if text in self._mapping:
            return self._mapping[text]
        key = env_key_from_ref(text)
        if key in self._mapping:
            return self._mapping[key]
        alt = f"env:{key}"
        if alt in self._mapping:
            return self._mapping[alt]
        raise SecretNotFoundError(ref)


class CallableSecretBroker:
    """Wrap a host callback (Vault, KMS, or test double)."""

    def __init__(self, resolver: Callable[[str], str | None]) -> None:
        self._resolver = resolver

    def resolve(self, ref: str) -> str:
        text = normalize_secret_ref(ref)
        value = self._resolver(text)
        if value is None or value == "":
            raise SecretNotFoundError(ref)
        return str(value)


class ChainSecretBroker:
    """Try brokers in order; first successful resolve wins."""

    def __init__(self, brokers: list[SecretBroker]) -> None:
        if not brokers:
            raise SecretConfigError("ChainSecretBroker requires at least one broker")
        self._brokers = list(brokers)

    def resolve(self, ref: str) -> str:
        last: SecretNotFoundError | None = None
        for broker in self._brokers:
            try:
                return broker.resolve(ref)
            except SecretNotFoundError as exc:
                last = exc
                continue
        if last is not None:
            raise last
        raise SecretNotFoundError(ref)


def broker_kind(broker: SecretBroker | None) -> str:
    if broker is None:
        return "none"
    return type(broker).__name__


def default_secret_broker(profile: Any | None = None) -> SecretBroker:
    """
    Env broker by default. Profile ``types`` with ``role: auth`` may select ``env``.

    Map/callable brokers cannot be declared in profile JSON (they would embed values).
    Bind those at ``session(secret_broker=...)``.
    """
    types = list(getattr(profile, "types", None) or []) if profile is not None else []
    for entry in types:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "").strip().lower()
        if role != "auth":
            continue
        config = entry.get("config") if isinstance(entry.get("config"), dict) else {}
        provider = str(config.get("provider") or config.get("broker") or "env").strip().lower()
        if provider in {"env", "environment"}:
            return EnvSecretBroker()
        raise SecretConfigError(
            "profile types role=auth cannot bind a map or callable broker; "
            "pass secret_broker= on agent.session() instead"
        )
    return EnvSecretBroker()
