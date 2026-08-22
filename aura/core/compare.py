"""Compare session exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def compare_sessions(path_a: Path, path_b: Path) -> dict[str, Any]:
    """Compare two session summary JSON files."""
    a = load_summary(path_a)
    b = load_summary(path_b)

    conf_a = (a.get("conformance") or {}).get("passed")
    conf_b = (b.get("conformance") or {}).get("passed")
    audit_a = (a.get("audit_report") or {}).get("verdict")
    audit_b = (b.get("audit_report") or {}).get("verdict")
    chain_a = (a.get("audit_report") or {}).get("hash_chain_valid")
    chain_b = (b.get("audit_report") or {}).get("hash_chain_valid")
    ref_a = a.get("agent_ref")
    ref_b = b.get("agent_ref")

    return {
        "session_a": a.get("session_id"),
        "session_b": b.get("session_id"),
        "agent_ref_a": ref_a,
        "agent_ref_b": ref_b,
        "agent_ref": {"a": ref_a, "b": ref_b, "same": ref_a == ref_b},
        "conformance": {"a": conf_a, "b": conf_b, "same": conf_a == conf_b},
        "audit_verdict": {"a": audit_a, "b": audit_b, "same": audit_a == audit_b},
        "hash_chain_valid": {"a": chain_a, "b": chain_b, "same": chain_a == chain_b},
        "event_count": {
            "a": a.get("event_count"),
            "b": b.get("event_count"),
            "delta": (b.get("event_count") or 0) - (a.get("event_count") or 0),
        },
        "snapshot_hash": {
            "a": a.get("snapshot_hash"),
            "b": b.get("snapshot_hash"),
            "same_policy": a.get("snapshot_hash") == b.get("snapshot_hash"),
        },
        "policy_version": {"a": a.get("policy_version"), "b": b.get("policy_version")},
    }
