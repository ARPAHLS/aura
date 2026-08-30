"""Auth0 OIDC adapter — issuer derived from tenant domain."""

from __future__ import annotations

import os

from aura.identity.adapters.oidc import OidcIdentityAdapter
from aura.identity.models import OperatorIdentity
from aura.identity.protocol import IdentityContext


class Auth0IdentityAdapter:
    method = "auth0"

    def __init__(self) -> None:
        self._oidc = OidcIdentityAdapter()

    def resolve(self, context: IdentityContext) -> OperatorIdentity | None:
        cfg = dict(context.config)
        adapter_name = str(cfg.get("adapter") or cfg.get("method") or "")
        if adapter_name not in ("", "auth0"):
            return None

        domain = cfg.get("domain") or context.env.get("AURA_AUTH0_DOMAIN")
        if domain and not cfg.get("issuer"):
            host = str(domain).rstrip("/")
            if not host.startswith("http"):
                host = f"https://{host}"
            cfg["issuer"] = host if host.endswith("/") else f"{host}/"
        if not cfg.get("audience"):
            cfg["audience"] = cfg.get("client_id") or context.env.get("AURA_AUTH0_AUDIENCE")
        if not cfg.get("token"):
            cfg["token"] = context.env.get("AURA_AUTH0_TOKEN") or os.environ.get("AURA_OIDC_TOKEN")

        merged = IdentityContext(
            session_id=context.session_id,
            aura_id=context.aura_id,
            agent_ref=context.agent_ref,
            profile_ids=context.profile_ids,
            config={**cfg, "adapter": "oidc", "method": "oidc"},
            env=context.env,
        )
        identity = self._oidc.resolve(merged)
        if identity is not None:
            identity.method = self.method
        return identity
