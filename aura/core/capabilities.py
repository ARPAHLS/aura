"""Named capabilities — scope checks and last-moment secret inject (#48)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aura.core.constraints import ConstraintContext, ConstraintResult
from aura.core.payload_redaction import strip_secret_like_keys
from aura.core.secrets import (
    SecretBroker,
    SecretConfigError,
    SecretNotFoundError,
    default_secret_broker,
    normalize_secret_ref,
)

STATE_CAPABILITIES = "_capabilities"
STATE_SPECTRUM_LEVEL = "_spectrum_level"
STATE_SECRET_BROKER = "_secret_broker"
STATE_INJECTED_SECRETS = "_injected_secret_values"

FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "value",
        "token",
        "plaintext",
        "secret",
        "password",
        "api_key",
        "authorization",
        "key",
        "card_number",
        "pan",
    }
)

_WILDCARD = "*"
_MISSING = object()


class CapabilityConfigError(SecretConfigError):
    """Invalid ``profile.capabilities[]`` declaration."""


@dataclass(frozen=True)
class Capability:
    """One named intent the agent may request. Secret is a ref only."""

    id: str
    tool: str | None = None
    skill_id: str | None = None
    allowed: dict[str, Any] = field(default_factory=dict)
    secret_ref: str | None = None
    inject_as: str = "token"
    strict_args: bool = False
    description: str | None = None

    def public_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id}
        if self.tool:
            data["tool"] = self.tool
        if self.skill_id:
            data["skill_id"] = self.skill_id
        if self.allowed:
            data["allowed"] = dict(self.allowed)
        if self.secret_ref:
            data["secret"] = {"ref": self.secret_ref}
        if self.inject_as and self.inject_as != "token":
            data["inject_as"] = self.inject_as
        if self.strict_args:
            data["strict_args"] = True
        if self.description:
            data["description"] = self.description
        return data


def _looks_like_secret_value(value: Any) -> bool:
    """True for values that look like live credentials, not ordinary scope labels."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    lower = text.lower()
    if lower.startswith(("env:", "vault:", "kms:", "file:")):
        return False
    prefixes = (
        "sk-",
        "pk-",
        "tok_",
        "token-",
        "ghp_",
        "xox",
        "akia",
        "bearer ",
        "basic ",
    )
    return any(lower.startswith(prefix) for prefix in prefixes)


def _secret_ref_from_block(raw: Any, *, strict: bool, cap_id: str) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return normalize_secret_ref(raw)
    if not isinstance(raw, dict):
        raise CapabilityConfigError(f"capability {cap_id!r} secret must be a ref string or object")
    leaked = [key for key in raw if str(key).lower() in FORBIDDEN_SECRET_KEYS]
    if leaked:
        message = (
            f"capability {cap_id!r} secret must be a ref only "
            f"(forbidden keys: {', '.join(sorted(leaked))})"
        )
        if strict:
            raise CapabilityConfigError(message)
        return None
    if "ref" in raw and raw["ref"]:
        return normalize_secret_ref(str(raw["ref"]))
    provider = str(raw.get("provider") or raw.get("source") or "").strip().lower()
    key = raw.get("env") or raw.get("name") or raw.get("id")
    if provider in {"env", "environment"} and key:
        return normalize_secret_ref(f"env:{key}")
    if key and not provider:
        return normalize_secret_ref(f"env:{key}")
    if raw.get("env"):
        return normalize_secret_ref(f"env:{raw['env']}")
    if strict and raw:
        raise CapabilityConfigError(f"capability {cap_id!r} secret object needs ref or env key")
    return None


def secret_like_allowed_value(key: str, value: Any) -> bool:
    from aura.core.payload_redaction import secret_like_key

    if secret_like_key(key):
        return True
    return _looks_like_secret_value(value)


def parse_capability(raw: Any, *, strict: bool = True) -> Capability | None:
    if not isinstance(raw, dict):
        if strict:
            raise CapabilityConfigError("each capability must be an object")
        return None
    cap_id = str(raw.get("id") or raw.get("capability_id") or "").strip()
    if not cap_id:
        if strict:
            raise CapabilityConfigError("capability requires a non-empty id")
        return None
    tool = raw.get("tool") or raw.get("name")
    skill_id = raw.get("skill_id") or raw.get("skill")
    allowed_raw = raw.get("allowed") if isinstance(raw.get("allowed"), dict) else {}
    if raw.get("scope") and not allowed_raw:
        scope = raw.get("scope")
        allowed_raw = dict(scope) if isinstance(scope, dict) else {}
    secret_block = raw.get("secret") if isinstance(raw.get("secret"), dict) else {}
    inject_as = (
        str(
            raw.get("inject_as")
            or secret_block.get("as")
            or secret_block.get("inject_as")
            or "token"
        ).strip()
        or "token"
    )
    secret_ref = _secret_ref_from_block(raw.get("secret"), strict=strict, cap_id=cap_id)
    if secret_ref is None and isinstance(raw.get("secret_ref"), str):
        secret_ref = normalize_secret_ref(raw["secret_ref"])
    description = raw.get("description")
    strict_args = bool(raw.get("strict_args") or raw.get("strict"))
    for key, value in allowed_raw.items():
        if secret_like_allowed_value(str(key), value) and strict:
            raise CapabilityConfigError(
                f"capability {cap_id!r} allowed.{key} looks like a plaintext secret; "
                "store labels only (e.g. card: Y) and put credentials in secret.ref"
            )
    return Capability(
        id=cap_id,
        tool=str(tool).strip() if tool else None,
        skill_id=str(skill_id).strip() if skill_id else None,
        allowed=dict(allowed_raw),
        secret_ref=secret_ref,
        inject_as=inject_as,
        strict_args=strict_args,
        description=str(description) if description else None,
    )


def parse_capabilities(raw: Any, *, strict: bool = True) -> list[Capability]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise CapabilityConfigError("capabilities must be a JSON array")
    parsed: list[Capability] = []
    seen: set[str] = set()
    for entry in raw:
        cap = parse_capability(entry, strict=strict)
        if cap is None:
            continue
        if cap.id in seen:
            if strict:
                raise CapabilityConfigError(f"duplicate capability id: {cap.id}")
            continue
        seen.add(cap.id)
        parsed.append(cap)
    return parsed


def capabilities_to_public(caps: list[Capability] | None) -> list[dict[str, Any]]:
    return [cap.public_dict() for cap in caps or []]


def normalize_capabilities_for_store(raw: Any) -> list[dict[str, Any]]:
    """Parse strictly and persist refs-only capability objects."""
    return capabilities_to_public(parse_capabilities(raw, strict=True))


def capabilities_summary(caps: list[Capability] | None) -> dict[str, Any]:
    items = list(caps or [])
    gated = gated_tool_ids(items)
    return {
        "count": len(items),
        "ids": [cap.id for cap in items],
        "gated_tools": sorted(gated) if gated is not None else ["*"],
        "secret_refs": [cap.secret_ref for cap in items if cap.secret_ref],
    }


def gated_tool_ids(caps: list[Capability]) -> set[str] | None:
    """
    Tool/skill ids that require a capability_id.

    ``None`` means every ``tool.call`` is gated (a capability has no tool/skill).
    Empty set means nothing is gated (no capabilities).
    """
    if not caps:
        return set()
    named: set[str] = set()
    unscoped = False
    for cap in caps:
        if cap.tool:
            named.add(cap.tool)
        if cap.skill_id:
            named.add(cap.skill_id)
        if not cap.tool and not cap.skill_id:
            unscoped = True
    if unscoped:
        return None
    return named


def capability_enforcement_rules(profile: Any) -> list[dict[str, Any]]:
    """Inject ``capability_scope`` when the profile declares capabilities."""
    caps = parse_capabilities(getattr(profile, "capabilities", None) or [], strict=False)
    if not caps:
        return []
    from aura.core.spectrum_enforcement import effective_spectrum

    level = effective_spectrum(profile).level.lower()
    return [
        {
            "type": "capability_scope",
            "source": "profile.capabilities",
            "level": level,
            "audit_only": level == "low",
        }
    ]


def merge_capability_rules(
    profile: Any, rules: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    merged = list(rules or [])
    if any((item.get("type") or item.get("kind")) == "capability_scope" for item in merged):
        return merged
    merged.extend(capability_enforcement_rules(profile))
    return merged


def attach_capability_state(session: Any, broker: SecretBroker | None) -> dict[str, Any]:
    """Stash parsed capabilities, spectrum level, and broker on session.state."""
    caps = parse_capabilities(getattr(session.profile, "capabilities", None) or [], strict=False)
    from aura.core.spectrum_enforcement import effective_spectrum

    level = effective_spectrum(session.profile).level.lower()
    resolved = broker
    if resolved is None and caps:
        resolved = default_secret_broker(session.profile)
    session.state[STATE_CAPABILITIES] = caps
    session.state[STATE_SPECTRUM_LEVEL] = level
    session.state[STATE_SECRET_BROKER] = resolved
    session.state.setdefault(STATE_INJECTED_SECRETS, set())
    object.__setattr__(session, "_secret_broker", resolved)
    summary = capabilities_summary(caps)
    summary["broker"] = type(resolved).__name__ if resolved is not None else "none"
    summary["audit_only"] = level == "low"
    return summary


def _tool_name(payload: dict[str, Any]) -> str | None:
    tool = payload.get("tool") or payload.get("name") or payload.get("tool_name")
    return str(tool) if tool else None


def _capability_id_from_payload(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (resolved_id, conflict_message)."""
    top = None
    for key in ("capability_id", "capability"):
        value = payload.get(key)
        if value:
            top = str(value).strip()
            break
    nested = None
    args = payload.get("args")
    if isinstance(args, dict):
        for key in ("capability_id", "capability"):
            value = args.get(key)
            if value:
                nested = str(value).strip()
                break
    if top and nested and top != nested:
        return None, f"conflicting capability_id {top!r} vs args {nested!r}"
    cap_id = top or nested
    return (cap_id or None), None


def _lookup_path(data: dict[str, Any], path: str) -> Any:
    if path in data:
        return data[path]
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _values_equal(expected: Any, actual: Any) -> bool:
    if expected == _WILDCARD:
        return actual is not _MISSING and actual is not None
    if isinstance(expected, list):
        return any(_values_equal(item, actual) for item in expected)
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, value in expected.items():
            if not _values_equal(value, _lookup_path(actual, str(key))):
                return False
        return True
    if actual is _MISSING:
        return False
    if expected == actual:
        return True
    return str(expected) == str(actual)


def _is_gated(tool: str | None, skill_id: Any, gated: set[str] | None) -> bool:
    if gated is None:
        return True
    if tool and tool in gated:
        return True
    if skill_id and str(skill_id) in gated:
        return True
    return False


def lookup_capability(caps: list[Capability], cap_id: str) -> Capability | None:
    for cap in caps:
        if cap.id == cap_id:
            return cap
    return None


def evaluate_capability_scope(
    ctx: ConstraintContext, rule: dict[str, Any]
) -> ConstraintResult | None:
    """Builtin ``capability_scope`` — named intent + allowed subset on tool.call."""
    if ctx.event_kind not in ("tool.call", "action.request"):
        return None
    caps: list[Capability] = list(ctx.session_state.get(STATE_CAPABILITIES) or [])
    if not caps:
        return None
    payload = ctx.payload or {}
    tool = _tool_name(payload)
    skill_id = payload.get("skill_id")
    gated = gated_tool_ids(caps)
    cap_id, conflict = _capability_id_from_payload(payload)
    claimed = bool(cap_id) or bool(conflict)
    gated_call = _is_gated(tool, skill_id, gated)

    if not gated_call and not claimed:
        return None

    level = str(rule.get("level") or ctx.session_state.get(STATE_SPECTRUM_LEVEL) or "mid").lower()
    audit_only = bool(rule.get("audit_only")) or level == "low"

    def _fail(message: str) -> ConstraintResult:
        return ConstraintResult(
            passed=False,
            rule=rule,
            message=message,
            blocked=True,
            audit_only=audit_only,
        )

    if conflict:
        return _fail(conflict)
    if not cap_id:
        return _fail(f"Capability id required for gated tool: {tool or skill_id or 'unknown'}")
    cap = lookup_capability(caps, cap_id)
    if cap is None:
        return _fail(f"Unknown capability: {cap_id}")
    if cap.tool and tool and cap.tool != tool:
        return _fail(f"Capability {cap_id} is bound to tool {cap.tool}, not {tool}")
    if cap.skill_id and skill_id and str(cap.skill_id) != str(skill_id):
        return _fail(f"Capability {cap_id} is bound to skill {cap.skill_id}, not {skill_id}")

    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    search_space = dict(payload)
    if isinstance(args, dict):
        search_space = {**payload, **args}

    for key, expected in cap.allowed.items():
        actual = _lookup_path(search_space, str(key))
        if actual is _MISSING and isinstance(args, dict):
            actual = _lookup_path(args, str(key))
        if not _values_equal(expected, actual):
            return _fail(
                f"Capability {cap_id} scope mismatch: {key}={actual!r} (allowed {expected!r})"
            )

    if cap.strict_args:
        reserved = {
            "tool",
            "skill_id",
            "name",
            "tool_name",
            "capability",
            "capability_id",
            "args",
            "step_id",
            "tokens",
            "token_count",
            "request_id",
            cap.inject_as,
        }
        extra = [
            key
            for key in args.keys()
            if key not in cap.allowed and key not in reserved and "." not in str(key)
        ]
        if extra:
            return _fail(
                f"Capability {cap_id} rejects extra args: {', '.join(sorted(map(str, extra)))}"
            )

    return ConstraintResult(
        passed=True,
        rule=rule,
        message=f"capability allowed: {cap_id}",
    )


def last_capability_result(results: list[ConstraintResult] | None) -> ConstraintResult | None:
    for result in reversed(results or []):
        rtype = (result.rule or {}).get("type") or (result.rule or {}).get("kind")
        if rtype == "capability_scope":
            return result
    return None


def matching_capability(session: Any, payload: dict[str, Any]) -> Capability | None:
    caps: list[Capability] = list(session.state.get(STATE_CAPABILITIES) or [])
    cap_id, conflict = _capability_id_from_payload(payload)
    if conflict or not cap_id:
        return None
    return lookup_capability(caps, cap_id)


def prepare_live_args(
    session: Any,
    payload: dict[str, Any],
    *,
    constraint_results: list[ConstraintResult] | None = None,
) -> dict[str, Any]:
    """
    Copy args for host execute: strip agent-supplied secrets, inject broker token
    only when capability_scope passed.
    """
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    live = strip_secret_like_keys(dict(args))
    cap = matching_capability(session, payload)
    scope = last_capability_result(constraint_results)
    allowed = cap is not None and scope is not None and scope.passed
    if not allowed or cap is None or not cap.secret_ref:
        return live
    broker: SecretBroker | None = getattr(session, "_secret_broker", None) or session.state.get(
        STATE_SECRET_BROKER
    )
    if broker is None:
        raise SecretNotFoundError(cap.secret_ref)
    value = broker.resolve(cap.secret_ref)
    live[cap.inject_as] = value
    injected: set[str] = session.state.setdefault(STATE_INJECTED_SECRETS, set())
    injected.add(value)
    return live


def injected_secret_values(session: Any) -> set[str]:
    raw = session.state.get(STATE_INJECTED_SECRETS) or set()
    return {str(item) for item in raw if item}
