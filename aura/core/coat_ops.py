"""AURA-native coat ops — external escalation delivery and membrane-level skill ops (#49)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from email.message import EmailMessage
import hashlib
import hmac
import ipaddress
import json
import os
import smtplib
import socket
import time
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class CoatOpDeliveryError(RuntimeError):
    """Raised when a coat op delivery target is misconfigured or unsafe."""


class CoatOpTarget(Protocol):
    """Protocol for external coat-op delivery adapters (webhook, SMTP, custom)."""

    def deliver(self, kind: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str.split("%", 1)[0])
    except ValueError:
        return False
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _validate_http_url(url: str, *, allow_private_network: bool = False) -> str:
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CoatOpDeliveryError(f"Unsafe or invalid webhook URL: {url!r}")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise CoatOpDeliveryError(f"Missing hostname in webhook URL: {url!r}")
    if not allow_private_network:
        if host in {"localhost", "metadata.google.internal"} or host.endswith(
            (".local", ".internal")
        ):
            raise CoatOpDeliveryError(f"Blocked private/local webhook host: {host!r}")
        if _is_blocked_ip(host):
            raise CoatOpDeliveryError(f"Blocked private/metadata IP in webhook URL: {host!r}")
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                sockaddr = info[4]
                if sockaddr and _is_blocked_ip(str(sockaddr[0])):
                    raise CoatOpDeliveryError(
                        f"Webhook host {host!r} resolves to blocked private/metadata IP"
                    )
        except socket.gaierror:
            # Unresolvable hostnames fail at urlopen() or are mocked in unit tests
            pass
    return str(url).strip()


def _resolve_secret_value(raw: str | None, broker: Any = None) -> str | None:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if ":" in text and not text.startswith(("http://", "https://")):
        active_broker = broker
        if active_broker is None:
            from aura.core.secrets import default_secret_broker

            active_broker = default_secret_broker()
        try:
            resolved = active_broker.resolve(text)
            if resolved:
                return str(resolved)
        except Exception:
            pass
    return text


@dataclass
class WebhookCoatOp:
    """Deliver escalation.email / escalation.wake payloads to an HTTP(S) webhook."""

    url: str
    timeout_seconds: float = 5.0
    hmac_secret: str | None = None
    headers: dict[str, str] | None = None
    allow_private_network: bool = False
    secret_broker: Any = None

    def deliver(self, kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        target_url = _validate_http_url(
            self.url,
            allow_private_network=self.allow_private_network,
        )
        body = json.dumps({"kind": kind, "payload": dict(payload)}, sort_keys=True).encode("utf-8")
        req_headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "aura-harness-coat-ops/1.0",
        }
        if self.headers:
            req_headers.update(self.headers)
        secret = _resolve_secret_value(self.hmac_secret, self.secret_broker)
        if secret:
            sig = hmac.new(
                secret.encode("utf-8"),
                body,
                hashlib.sha256,
            ).hexdigest()
            req_headers["X-AURA-Signature"] = f"sha256={sig}"

        req = Request(target_url, data=body, headers=req_headers, method="POST")
        with urlopen(req, timeout=self.timeout_seconds) as resp:  # noqa: S310
            status_code = getattr(resp, "status", 200)
        return {"transport": "webhook", "status_code": int(status_code)}


@dataclass
class SmtpCoatOp:
    """Deliver escalation.email notifications via SMTP (stdlib smtplib)."""

    host: str
    port: int = 587
    sender: str = "aura@localhost"
    username: str | None = None
    password: str | None = None
    use_tls: bool = True
    timeout_seconds: float = 5.0
    secret_broker: Any = None

    def deliver(self, kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        recipient = str(payload.get("to") or "ops@example.com")
        msg = EmailMessage()
        msg["Subject"] = f"[AURA Escalation] {payload.get('trigger_kind', kind)}"
        msg["From"] = self.sender
        msg["To"] = recipient
        msg.set_content(json.dumps(dict(payload), indent=2, default=str))

        resolved_pw = _resolve_secret_value(self.password, self.secret_broker)
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds) as client:
            if self.use_tls:
                client.starttls()
            if self.username and resolved_pw:
                client.login(self.username, resolved_pw)
            client.send_message(msg)
        return {"transport": "smtp", "to": recipient}


class CallableCoatOp:
    """Wrap a Python callable as a coat-op delivery adapter."""

    def __init__(self, fn: Callable[[str, Mapping[str, Any]], Any]) -> None:
        self._fn = fn

    def deliver(self, kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        res = self._fn(kind, payload)
        if isinstance(res, dict):
            return dict(res)
        return {"transport": "callable", "result": res}


class CoatOpDispatcher:
    """Route escalation.email / escalation.wake to configured delivery targets."""

    def __init__(
        self,
        targets: Mapping[str, Any] | None = None,
        *,
        async_dispatch: bool = False,
        secret_broker: Any = None,
    ) -> None:
        self._async_dispatch = bool(async_dispatch)
        self._executor: ThreadPoolExecutor | None = (
            ThreadPoolExecutor(max_workers=2, thread_name_prefix="aura-coat-op")
            if self._async_dispatch
            else None
        )
        self._targets: dict[str, CoatOpTarget] = {}
        for key, raw in (targets or {}).items():
            self._targets[str(key).strip().lower()] = _coerce_target(
                raw,
                secret_broker=secret_broker,
            )

    @classmethod
    def from_env_and_profile(
        cls,
        profile_vars: Mapping[str, Any] | None = None,
        override: Any = None,
        *,
        secret_broker: Any = None,
    ) -> "CoatOpDispatcher | None":
        if isinstance(override, CoatOpDispatcher):
            return override
        targets: dict[str, Any] = {}
        if isinstance(profile_vars, Mapping) and isinstance(profile_vars.get("coat_ops"), Mapping):
            targets.update(profile_vars["coat_ops"])
        webhook_url = os.environ.get("AURA_COAT_WEBHOOK_URL", "").strip()
        if webhook_url and "webhook" not in targets:
            targets["webhook"] = {
                "type": "webhook",
                "url": webhook_url,
                "hmac_secret": os.environ.get("AURA_COAT_WEBHOOK_SECRET"),
            }
        if isinstance(override, Mapping):
            targets.update(override)
        if not targets:
            return None
        return cls(targets, secret_broker=secret_broker)

    def dispatch(self, kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Attempt delivery for ``escalation.email`` or ``escalation.wake``."""
        key = "email" if kind == "escalation.email" else "wake"
        target = self._targets.get(key) or self._targets.get("webhook") or self._targets.get("all")
        if target is None:
            return {"delivery": "stub"}
        if self._executor is not None:
            self._executor.submit(target.deliver, kind, dict(payload))
            return {"delivery": "queued"}
        try:
            meta = target.deliver(kind, payload)
            return {"delivery": "sent", **meta}
        except Exception as exc:
            return {"delivery": "failed", "delivery_error": str(exc)}


def _coerce_target(raw: Any, *, secret_broker: Any = None) -> CoatOpTarget:
    if callable(raw) and not hasattr(raw, "deliver"):
        return CallableCoatOp(raw)
    if hasattr(raw, "deliver"):
        return raw  # type: ignore[return-value]
    if isinstance(raw, Mapping):
        kind = str(raw.get("type") or "webhook").strip().lower()
        if kind == "webhook":
            return WebhookCoatOp(
                url=str(raw["url"]),
                timeout_seconds=float(raw.get("timeout_seconds", 5.0)),
                hmac_secret=raw.get("hmac_secret"),
                headers=dict(raw["headers"]) if isinstance(raw.get("headers"), Mapping) else None,
                allow_private_network=bool(raw.get("allow_private_network", False)),
                secret_broker=secret_broker,
            )
        if kind == "smtp":
            return SmtpCoatOp(
                host=str(raw["host"]),
                port=int(raw.get("port", 587)),
                sender=str(raw.get("sender", "aura@localhost")),
                username=raw.get("username"),
                password=raw.get("password"),
                use_tls=bool(raw.get("use_tls", True)),
                timeout_seconds=float(raw.get("timeout_seconds", 5.0)),
                secret_broker=secret_broker,
            )
    raise CoatOpDeliveryError(f"Unsupported coat op target: {raw!r}")


class CoatOpRunner:
    """
    Execute membrane-level skills (e.g. ``security/prompt_injection_firewall``) through
    AURA egress regardless of whether the inner body is plain Python, LangGraph, or Skillware.
    """

    def __init__(self, session: Any, *, host: Any | None = None) -> None:
        self._session = getattr(session, "_session", session)
        if host is None:
            from aura.hosts.skillware import SkillwareHost

            host = SkillwareHost(self._session)
        self._host = host

    @property
    def host(self) -> Any:
        return self._host

    def run_op(
        self,
        skill_id: str,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        op_name: str | None = None,
        register_from_registry: bool = True,
    ) -> Any:
        """Execute a membrane-level coat skill through ``SkillwareHost`` egress."""
        if register_from_registry and skill_id not in getattr(self._host, "_skills", {}):
            self._host.register_registry_skill(skill_id)
        t0 = time.perf_counter()
        result = self._host.execute(skill_id, tool, args or {})
        duration_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        self._session.emit(
            "coat.op.executed",
            {
                "membrane": "coat_op",
                "op": op_name or skill_id,
                "skill_id": skill_id,
                "tool": tool,
                "duration_ms": duration_ms,
                "status": "ok",
            },
        )
        return result

    def scan_input(
        self,
        source_text: str,
        *,
        sensitivity: str = "balanced",
        skill_id: str = "security/prompt_injection_firewall",
    ) -> dict[str, Any]:
        """Pre-ingress/pre-egress prompt-injection scan using Skillware or a registered mock."""
        res = self.run_op(
            skill_id,
            skill_id,
            {"source_text": source_text, "sensitivity": sensitivity},
            op_name="coat.scan_input",
        )
        return dict(res) if isinstance(res, Mapping) else {"result": res}
