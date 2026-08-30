"""OIDC / JWT bearer operator identity."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from aura.identity.errors import IdentityVerificationError
from aura.identity.models import OperatorIdentity
from aura.identity.protocol import IdentityContext


def _decode_jwt_unverified(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        raise IdentityVerificationError("malformed JWT", method="oidc")
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    import base64

    raw = base64.urlsafe_b64decode(payload + padding)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise IdentityVerificationError("JWT payload must be an object", method="oidc")
    return data


def _verify_jwt(token: str, *, issuer: str, audience: str | None) -> dict[str, Any]:
    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError as exc:  # pragma: no cover - optional extra
        raise IdentityVerificationError(
            "pyjwt required for OIDC verification (pip install 'aura-harness[identity]')",
            method="oidc",
        ) from exc

    jwks_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        with urllib.request.urlopen(jwks_url, timeout=10) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise IdentityVerificationError(
            f"failed to load OIDC metadata: {exc}", method="oidc"
        ) from exc

    jwks_uri = meta.get("jwks_uri")
    if not jwks_uri:
        raise IdentityVerificationError("OIDC metadata missing jwks_uri", method="oidc")

    client = PyJWKClient(jwks_uri)
    signing_key = client.get_signing_key_from_jwt(token)
    options = {"verify_aud": audience is not None}
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256", "PS256"],
        issuer=issuer,
        audience=audience,
        options=options,
    )


class OidcIdentityAdapter:
    method = "oidc"

    def resolve(self, context: IdentityContext) -> OperatorIdentity | None:
        cfg = context.config
        adapter_name = str(cfg.get("adapter") or cfg.get("method") or "")
        if adapter_name not in ("", "oidc", "jwt"):
            return None

        token = (
            cfg.get("token")
            or context.env.get("AURA_OIDC_TOKEN")
            or context.env.get("AURA_IDENTITY_TOKEN")
        )
        if not token:
            return None

        issuer = cfg.get("issuer") or context.env.get("AURA_OIDC_ISSUER")
        audience = cfg.get("audience") or context.env.get("AURA_OIDC_AUDIENCE")
        verify = bool(cfg.get("verify_signature", True))

        if verify:
            if not issuer:
                raise IdentityVerificationError(
                    "issuer required for OIDC verification", method="oidc"
                )
            claims = _verify_jwt(
                str(token), issuer=str(issuer), audience=str(audience) if audience else None
            )
        else:
            claims = _decode_jwt_unverified(str(token))

        subject = claims.get("sub")
        if not subject:
            raise IdentityVerificationError("JWT missing sub claim", method="oidc")

        return OperatorIdentity(
            verified=verify,
            method=self.method,
            subject=str(subject),
            email=claims.get("email"),
            name=claims.get("name") or claims.get("preferred_username"),
            session_ref=context.session_id,
            issuer=str(issuer or claims.get("iss") or ""),
            claims={k: claims[k] for k in ("sub", "iss", "aud", "email") if k in claims},
        )
