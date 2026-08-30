"""Redact operator PII for export surfaces."""

from __future__ import annotations

import copy
from typing import Any

from aura.config import get_config

DEFAULT_REDACT_FIELDS = frozenset({"email", "name", "phone"})


def identity_export_settings() -> tuple[bool, frozenset[str]]:
    cfg = get_config().values
    export_pii = bool(cfg.get("identity_export_pii", False))
    raw = cfg.get("identity_redact_fields")
    if isinstance(raw, list):
        fields = frozenset(str(x) for x in raw)
    else:
        fields = DEFAULT_REDACT_FIELDS
    return export_pii, fields


def redact_operator_dict(
    operator: dict[str, Any], *, export_pii: bool, fields: frozenset[str]
) -> dict[str, Any]:
    if export_pii or not operator:
        return dict(operator)
    redacted = dict(operator)
    for key in fields:
        if key in redacted:
            redacted[key] = None
    if "subject" in redacted and "subject_hash" not in redacted:
        from aura.identity.models import hash_subject

        redacted["subject_hash"] = hash_subject(str(redacted["subject"]))
    return redacted


def redact_agent_ids(agent_ids: dict[str, Any] | None) -> dict[str, Any]:
    if not agent_ids:
        return {}
    export_pii, fields = identity_export_settings()
    if export_pii:
        return dict(agent_ids)
    out = copy.deepcopy(agent_ids)
    ids = out.get("ids")
    if isinstance(ids, dict) and isinstance(ids.get("operator"), dict):
        ids["operator"] = redact_operator_dict(
            ids["operator"], export_pii=export_pii, fields=fields
        )
    return out


def redact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    export_pii, fields = identity_export_settings()
    if export_pii:
        return summary
    out = copy.deepcopy(summary)
    agent_ids = out.get("agent_ids")
    if isinstance(agent_ids, dict):
        out["agent_ids"] = redact_agent_ids(agent_ids)
    identity = out.get("identity")
    if isinstance(identity, dict) and isinstance(identity.get("operator"), dict):
        identity["operator"] = redact_operator_dict(
            identity["operator"], export_pii=export_pii, fields=fields
        )
    return out
