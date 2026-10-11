"""PII masking engine for sequencer step boundaries and pipeline ops (#58).

Two-tier architecture:
- Tier 1: Zero-dependency stdlib regex + algorithmic validation (Luhn, RFC format).
- Tier 2: Pluggable PiiMaskerProvider for contextual NER models (Skillware, micro-f1-mask, etc.).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence

# -----------------------------------------------------------------------------
# Regex Patterns & Algorithmic Validators
# -----------------------------------------------------------------------------

# RFC 5322-compatible email pattern
_RE_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)

# Phone numbers (E.164, international, UK/EU with trunk prefix, US/CAN 10-digit and 7-digit)
_RE_PHONE = re.compile(
    r"(?<!\w)\+[1-9]\d{0,3}[-.\s]?(?:\(?0\)?[-.\s]?)?(?:[0-9]{1,5}[-.\s]?){1,4}[0-9]{2,5}\b"
    r"|(?<![-+\w])(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    r"|(?<![-+\w])0[1-9]\d{1,4}[-.\s](?:[0-9]{1,4}[-.\s]?){1,3}[0-9]{2,4}\b"
    r"|(?<![-+\w])[2-9]\d{2}[-.\s]\d{4}\b"
)

# US Social Security Number: ddd-dd-dddd (not starting with 000, 666, 9xx)
_RE_SSN = re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")

# Potential Credit Card numbers: 13 to 19 digits (optional spaces or dashes)
_RE_CREDIT_CARD_CANDIDATE = re.compile(r"\b(?:\d{4}[ -]?){3}\d{1,7}\b|\b\d{13,19}\b")

# IPv4 Address (0-255 in each octet)
_RE_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\b"
)

# IPv6 Address
_RE_IPV6 = re.compile(
    r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b"
    r"|\b(?:[A-Fa-f0-9]{1,4}:){1,7}:[A-Fa-f0-9]{1,4}\b"
    r"|\b::(?:[A-Fa-f0-9]{1,4}:){0,6}[A-Fa-f0-9]{1,4}\b",
    re.IGNORECASE,
)

# API Keys, Tokens, and high-entropy secrets
_RE_API_KEY = re.compile(
    r"\b(?:sk|pk|ghp|gho|glpat|xoxb|xoxp|live|test)[-_][A-Za-z0-9_-]{16,}\b"
    r"|\bAKIA[0-9A-Z]{16}\b"
    r"|\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"  # JWT
    r"|\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"  # UUID
)

# IBAN (International Bank Account Number)
_RE_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Za-z0-9]{11,30}\b")


def is_luhn_valid(number_str: str) -> bool:
    """Validate credit card number using Luhn checksum algorithm."""
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


# -----------------------------------------------------------------------------
# Configuration and Protocols
# -----------------------------------------------------------------------------

SUPPORTED_ENTITIES = frozenset(
    {"email", "phone", "credit_card", "ssn", "ip_address", "key", "iban"}
)

SUPPORTED_STRATEGIES = frozenset({"redact", "mask", "pseudonymize", "tokenize"})


@dataclass
class PiiMaskConfig:
    strategy: str = "redact"  # redact | mask | pseudonymize | tokenize
    entities: Sequence[str] = ("all",)
    target: str = "all"  # "all" or specific dot-path like "args"
    targets: Sequence[str] | None = None
    allowlist: Sequence[str] = field(default_factory=tuple)
    salt: str | None = None
    on_error: str = "fallback"  # fallback | fail | pass
    strict: bool = False
    provider: str | None = None

    def is_entity_enabled(self, entity: str) -> bool:
        if "all" in self.entities:
            return True
        normalized_targets = {e.lower() for e in self.entities}
        ent_lower = entity.lower()
        if ent_lower in normalized_targets:
            return True
        aliases = {
            "key": {"key", "api_key", "jwt"},
            "api_key": {"key", "api_key", "jwt"},
            "credit_card": {"credit_card", "card"},
            "ip_address": {"ip", "ip_address"},
        }
        if ent_lower in aliases:
            return bool(aliases[ent_lower] & normalized_targets)
        return False


@dataclass
class PiiMaskResult:
    data: Any = None
    entities_detected: dict[str, int] = field(default_factory=dict)
    total_redactions: int = 0
    fields_modified: list[str] = field(default_factory=list)

    def __init__(
        self,
        data: Any = None,
        entities_detected: dict[str, int] | None = None,
        total_redactions: int = 0,
        fields_modified: list[str] | None = None,
        *,
        text: str | None = None,
        redacted_count: int | None = None,
        entity_counts: dict[str, int] | None = None,
        modified_fields: list[str] | None = None,
    ) -> None:
        self.data = text if text is not None else data
        self.entities_detected = dict(
            entity_counts if entity_counts is not None else (entities_detected or {})
        )
        self.total_redactions = redacted_count if redacted_count is not None else total_redactions
        self.fields_modified = list(
            modified_fields if modified_fields is not None else (fields_modified or [])
        )

    def __iter__(self):
        yield self.data
        yield self.entities_detected

    @property
    def text(self) -> str:
        return str(self.data)

    @property
    def entity_counts(self) -> dict[str, int]:
        res = dict(self.entities_detected)
        for k, v in list(self.entities_detected.items()):
            res[k.upper()] = v
            res[k.lower()] = v
        return res

    @property
    def redacted_count(self) -> int:
        return self.total_redactions

    @property
    def modified_fields(self) -> list[str]:
        return self.fields_modified


class PiiMaskerProvider(Protocol):
    """Pluggable provider for contextual NER models (Tier 2)."""

    def mask_text(
        self,
        text: str,
        config: PiiMaskConfig,
        session_state: dict[str, Any] | None = None,
    ) -> Any: ...


# -----------------------------------------------------------------------------
# Native Rule Engine (Tier 1)
# -----------------------------------------------------------------------------


class NativePiiMasker:
    """Built-in regex + checksum PII masking engine (Tier 1)."""

    def __init__(self) -> None:
        pass

    def mask_text(
        self,
        text: str,
        config: PiiMaskConfig,
        session_state: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, int]]:
        if not text:
            return text, {}

        entities_detected: dict[str, int] = {}
        out = text
        strategy = config.strategy.lower()
        if strategy == "tokenize":
            strategy = "pseudonymize"

        # Helper to check allowlist
        def _is_allowlisted(raw_match: str) -> bool:
            for item in config.allowlist:
                if item and (item == raw_match or item in raw_match):
                    return True
            return False

        # Helper to format replacement based on strategy
        def _replace_entity(raw: str, entity_type: str) -> str:
            if _is_allowlisted(raw):
                return raw

            entities_detected[entity_type] = entities_detected.get(entity_type, 0) + 1

            if strategy == "redact":
                tag = entity_type.upper()
                if tag == "KEY":
                    tag = "API_KEY"
                return f"[{tag}]"

            if strategy == "mask":
                return self._partial_mask(raw, entity_type)

            if strategy == "pseudonymize":
                return self._pseudonymize(raw, entity_type, session_state, config.salt)

            return f"[{entity_type.upper()}]"

        # 1. API Keys & JWTs (run first to avoid matching parts as emails/ips)
        if config.is_entity_enabled("key"):

            def _repl_key(m: re.Match) -> str:
                return _replace_entity(m.group(0), "key")

            out = _RE_API_KEY.sub(_repl_key, out)

        # 2. Emails
        if config.is_entity_enabled("email"):

            def _repl_email(m: re.Match) -> str:
                return _replace_entity(m.group(0), "email")

            out = _RE_EMAIL.sub(_repl_email, out)

        # 3. Credit Cards (with Luhn check verification)
        if config.is_entity_enabled("credit_card"):

            def _repl_card(m: re.Match) -> str:
                raw_candidate = m.group(0)
                # Verify with Luhn
                if is_luhn_valid(raw_candidate):
                    return _replace_entity(raw_candidate, "credit_card")
                return raw_candidate

            out = _RE_CREDIT_CARD_CANDIDATE.sub(_repl_card, out)

        # 4. Social Security Numbers
        if config.is_entity_enabled("ssn"):

            def _repl_ssn(m: re.Match) -> str:
                return _replace_entity(m.group(0), "ssn")

            out = _RE_SSN.sub(_repl_ssn, out)

        # 5. IP Addresses
        if config.is_entity_enabled("ip_address"):

            def _repl_ipv4(m: re.Match) -> str:
                return _replace_entity(m.group(0), "ip_address")

            def _repl_ipv6(m: re.Match) -> str:
                return _replace_entity(m.group(0), "ip_address")

            out = _RE_IPV4.sub(_repl_ipv4, out)
            out = _RE_IPV6.sub(_repl_ipv6, out)

        # 6. IBAN
        if config.is_entity_enabled("iban"):

            def _repl_iban(m: re.Match) -> str:
                return _replace_entity(m.group(0), "iban")

            out = _RE_IBAN.sub(_repl_iban, out)

        # 7. Phone Numbers
        if config.is_entity_enabled("phone"):

            def _repl_phone(m: re.Match) -> str:
                raw_candidate = m.group(0)
                # Avoid matching simple short dates or numbers without enough digits
                digits = [c for c in raw_candidate if c.isdigit()]
                if len(digits) < 7 or len(digits) > 15:
                    return raw_candidate
                return _replace_entity(raw_candidate, "phone")

            out = _RE_PHONE.sub(_repl_phone, out)

        return PiiMaskResult(
            data=out,
            entities_detected=entities_detected,
            total_redactions=sum(entities_detected.values()),
            fields_modified=["text"] if entities_detected else [],
        )

    def _partial_mask(self, raw: str, entity_type: str) -> str:
        """Partial obfuscation retaining operational shape."""
        if entity_type == "email":
            parts = raw.split("@", 1)
            if len(parts) == 2:
                name, domain = parts
                if len(name) <= 2:
                    masked_name = name[0] + "*"
                else:
                    masked_name = name[0] + "***" + name[-1]
                return f"{masked_name}@{domain}"
            return raw[0] + "***"

        if entity_type == "credit_card":
            digits = "".join([c for c in raw if c.isdigit()])
            last4 = digits[-4:] if len(digits) >= 4 else digits
            return f"****-****-****-{last4}"

        if entity_type == "ssn":
            digits = "".join([c for c in raw if c.isdigit()])
            last4 = digits[-4:] if len(digits) >= 4 else digits
            return f"***-**-{last4}"

        if entity_type == "phone":
            digits = "".join([c for c in raw if c.isdigit()])
            last4 = digits[-4:] if len(digits) >= 4 else digits
            trimmed = raw.strip()
            if trimmed.startswith("+"):
                prefix = trimmed[:3]
                return f"{prefix}***-***-{last4}"
            return f"***-***-{last4}"

        if entity_type == "ip_address":
            if "." in raw:
                parts = raw.split(".")
                return f"{parts[0]}.{parts[1]}.*.*"
            return "*:*:*:*:*"

        if entity_type == "key":
            prefix = raw[:3] if len(raw) >= 3 else ""
            suffix = raw[-4:] if len(raw) >= 8 else ""
            return f"{prefix}****{suffix}"

        # Generic default mask
        if len(raw) <= 4:
            return "****"
        return raw[:2] + "****" + raw[-2:]

    def _pseudonymize(
        self,
        raw: str,
        entity_type: str,
        session_state: dict[str, Any] | None,
        salt: str | None,
    ) -> str:
        """Deterministic session-scoped pseudonym token (e.g. <EMAIL_REF_a1b2>)."""
        key = (entity_type, raw)
        store: dict[tuple[str, str], str]
        if session_state is not None:
            store = session_state.setdefault("_pii_pseudonyms", {})
        else:
            store = getattr(self, "_fallback_pseudonyms", None)
            if store is None:
                store = {}
                self._fallback_pseudonyms = store

        if key in store:
            return store[key]

        salt_bytes = (salt or "aura_pii_salt").encode("utf-8")
        h = hashlib.sha256(salt_bytes + raw.encode("utf-8")).hexdigest()[:6]
        token = f"<{entity_type.upper()}_REF_{h}>"
        store[key] = token
        return token


# -----------------------------------------------------------------------------
# Provider Registry
# -----------------------------------------------------------------------------


class CallablePiiMasker:
    """Wraps a callable into a PiiMaskerProvider."""

    def __init__(self, fn: Callable[..., Any]) -> None:
        self.fn = fn

    def mask_text(
        self,
        text: str,
        config: PiiMaskConfig,
        session_state: dict[str, Any] | None = None,
    ) -> Any:
        return self.fn(text, config, session_state)


_PROVIDERS: dict[str, PiiMaskerProvider] = {"native": NativePiiMasker()}


def register_pii_provider(
    name: str,
    provider: PiiMaskerProvider | Callable[..., Any],
) -> None:
    norm = name.lower().replace("-", "_")
    if callable(provider) and not hasattr(provider, "mask_text"):
        prov_obj: PiiMaskerProvider = CallablePiiMasker(provider)
    elif isinstance(provider, type):
        prov_obj = provider()
    else:
        prov_obj = provider  # type: ignore[assignment]
    _PROVIDERS[norm] = prov_obj
    _PROVIDERS[name.lower()] = prov_obj


def get_pii_provider(name: str | None = None) -> PiiMaskerProvider:
    if not name:
        return _PROVIDERS["native"]
    norm = name.lower().replace("-", "_")
    return _PROVIDERS.get(norm, _PROVIDERS.get(name.lower(), _PROVIDERS["native"]))


# -----------------------------------------------------------------------------
# Deep Traversal & Masking Coordinator
# -----------------------------------------------------------------------------


class PiiMasker:
    """Coordinates PII masking across arbitrary nested data structures."""

    def __init__(
        self,
        provider: PiiMaskerProvider | Callable[..., Any] | None = None,
    ) -> None:
        if callable(provider) and not hasattr(provider, "mask_text"):
            self.provider: PiiMaskerProvider = CallablePiiMasker(provider)
        else:
            self.provider = provider or get_pii_provider("native")

    def mask(
        self,
        data: Any,
        config: PiiMaskConfig | dict[str, Any] | None = None,
        *,
        session_state: dict[str, Any] | None = None,
    ) -> PiiMaskResult:
        if isinstance(config, dict):
            cfg = PiiMaskConfig(
                strategy=str(config.get("strategy", "redact")),
                entities=tuple(config.get("entities") or ("all",)),
                target=str(config.get("target", "all")),
                targets=tuple(config.get("targets")) if config.get("targets") else None,
                allowlist=tuple(config.get("allowlist") or config.get("whitelist") or ()),
                salt=config.get("salt"),
                on_error=str(config.get("on_error", "fallback")),
                strict=bool(config.get("strict", False)),
                provider=config.get("provider"),
            )
        elif isinstance(config, PiiMaskConfig):
            cfg = config
        else:
            cfg = PiiMaskConfig()

        provider = get_pii_provider(cfg.provider) if cfg.provider else self.provider
        entities_detected: dict[str, int] = {}
        fields_modified: list[str] = []

        masked_data = self._traverse(
            data,
            cfg,
            session_state,
            current_path="",
            entities_acc=entities_detected,
            modified_acc=fields_modified,
            provider=provider,
        )

        total_redactions = sum(entities_detected.values())
        if cfg.strict and total_redactions > 0:
            from aura.core.constraints import ConstraintViolation

            raise ConstraintViolation(
                f"Strict PII policy violated: detected {total_redactions} "
                f"PII occurrence(s): {entities_detected}"
            )

        return PiiMaskResult(
            data=masked_data,
            entities_detected=entities_detected,
            total_redactions=total_redactions,
            fields_modified=fields_modified,
        )

    def _traverse(
        self,
        value: Any,
        cfg: PiiMaskConfig,
        session_state: dict[str, Any] | None,
        current_path: str,
        entities_acc: dict[str, int],
        modified_acc: list[str],
        provider: PiiMaskerProvider,
    ) -> Any:
        # Check target path filter
        active_targets = (
            list(cfg.targets) if cfg.targets else ([cfg.target] if cfg.target != "all" else [])
        )
        if active_targets and current_path:
            matched = False
            for t in active_targets:
                if current_path == t or current_path.startswith(t + "."):
                    matched = True
                    break
                if t.startswith(current_path + "."):
                    matched = True
                    break
            if not matched:
                return value

        if isinstance(value, str):
            try:
                if hasattr(provider, "mask_text"):
                    res = provider.mask_text(value, cfg, session_state)
                elif callable(provider):
                    res = provider(value, cfg, session_state)
                else:
                    res = str(value)
            except Exception:
                if cfg.on_error == "fail":
                    raise
                elif cfg.on_error == "pass":
                    return value
                else:  # fallback
                    res = NativePiiMasker().mask_text(value, cfg, session_state)

            if isinstance(res, tuple):
                masked_text, detected = res[0], res[1] if len(res) > 1 else {}
            elif isinstance(res, dict):
                masked_text = res.get("text", res.get("data", str(res)))
                detected = res.get("entities_detected", res.get("entities", {}))
            elif hasattr(res, "data") and hasattr(res, "entities_detected"):
                masked_text, detected = res.data, res.entities_detected
            elif hasattr(res, "text") and hasattr(res, "entity_counts"):
                masked_text, detected = res.text, res.entity_counts
            else:
                masked_text, detected = str(res), {}

            if detected:
                for k, v in detected.items():
                    entities_acc[k] = entities_acc.get(k, 0) + v
                if current_path:
                    modified_acc.append(current_path)
            return masked_text

        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for k, v in value.items():
                child_path = f"{current_path}.{k}" if current_path else str(k)
                out[k] = self._traverse(
                    v, cfg, session_state, child_path, entities_acc, modified_acc, provider=provider
                )
            return out

        if isinstance(value, list):
            return [
                self._traverse(
                    item,
                    cfg,
                    session_state,
                    f"{current_path}[{i}]",
                    entities_acc,
                    modified_acc,
                    provider=provider,
                )
                for i, item in enumerate(value)
            ]

        if isinstance(value, tuple):
            return tuple(
                self._traverse(
                    item,
                    cfg,
                    session_state,
                    f"{current_path}[{i}]",
                    entities_acc,
                    modified_acc,
                    provider=provider,
                )
                for i, item in enumerate(value)
            )

        return value


__all__ = [
    "NativePiiMasker",
    "CallablePiiMasker",
    "PiiMasker",
    "PiiMaskConfig",
    "PiiMaskResult",
    "PiiMaskerProvider",
    "is_luhn_valid",
    "get_pii_provider",
    "register_pii_provider",
]
