"""Identity adapter registry."""

from __future__ import annotations

from typing import Any

from aura.identity.adapters.auth0 import Auth0IdentityAdapter
from aura.identity.adapters.manual import ManualIdentityAdapter
from aura.identity.adapters.mock import MockIdentityAdapter
from aura.identity.adapters.oidc import OidcIdentityAdapter
from aura.identity.protocol import OperatorIdentityAdapter

_BUILTIN_ADAPTERS: dict[str, OperatorIdentityAdapter] = {
    "manual": ManualIdentityAdapter(),
    "mock": MockIdentityAdapter(),
    "oidc": OidcIdentityAdapter(),
    "jwt": OidcIdentityAdapter(),
    "auth0": Auth0IdentityAdapter(),
}


def get_builtin_adapter(name: str) -> OperatorIdentityAdapter | None:
    return _BUILTIN_ADAPTERS.get(name)


def _append_unique(chain: list[OperatorIdentityAdapter], adapter: OperatorIdentityAdapter) -> None:
    if not any(existing.method == adapter.method for existing in chain):
        chain.append(adapter)


def adapter_chain_from_config(config: dict[str, Any] | None) -> list[OperatorIdentityAdapter]:
    if not config:
        return [ManualIdentityAdapter()]

    chain: list[OperatorIdentityAdapter] = []
    explicit = config.get("adapter") or config.get("method")
    if explicit:
        built = get_builtin_adapter(str(explicit))
        if built:
            _append_unique(chain, built)

    for entry in config.get("adapters") or []:
        if isinstance(entry, str):
            built = get_builtin_adapter(entry)
            if built:
                _append_unique(chain, built)
        elif isinstance(entry, dict):
            name = entry.get("adapter") or entry.get("method")
            if name:
                built = get_builtin_adapter(str(name))
                if built:
                    _append_unique(chain, built)

    if not chain:
        if config.get("token") or config.get("issuer") or config.get("domain"):
            for name in ("auth0", "oidc"):
                built = get_builtin_adapter(name)
                if built:
                    _append_unique(chain, built)
        elif config.get("enabled") is True or config.get("subject"):
            _append_unique(chain, MockIdentityAdapter())

    _append_unique(chain, ManualIdentityAdapter())
    return chain
