"""Skillware dispatch audit bridge, bypass detection, and dual-ledger verification."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from aura.core.finops import estimate_cost_usd
from aura.core.spine import AuditSpine, verify_hash_chain
from aura.membrane.egress import (
    active_egress_context,
    current_egress_span,
    extract_provenance_hash,
)

SKILLWARE_GENESIS_HASH = "0" * 64

__all__ = [
    "DualChainVerificationResult",
    "SKILLWARE_GENESIS_HASH",
    "active_egress_context",
    "create_dispatch_audit_hook",
    "current_egress_span",
    "extract_provenance_hash",
    "verify_dual_audit_chain",
]


def create_dispatch_audit_hook(
    session: Any,
    *,
    source: str = "skillware.context",
) -> Callable[[dict[str, Any]], None]:
    """
    Create an ``on_dispatch`` callback for ``SkillContext(on_dispatch=...)``.

    Bridges every Skillware dispatch event into AURA's immutable ``AuditSpine``:
    - Correlates ``trace_id`` and ``span_id`` with the active AURA egress call.
    - Records FinOps telemetry (``duration_ms``, ``model``, token counts, ``estimated_cost_usd``).
    - Anchors Skillware's ``event_hash`` / ``prev_hash`` when dual-ledger logging is enabled.
    - Detects and flags unguarded dispatches that bypassed ``SkillwareHost.execute()``!
    """

    def _on_dispatch(event: dict[str, Any]) -> None:
        if not isinstance(event, Mapping):
            return
        real_session = getattr(session, "_session", session)
        if not getattr(real_session, "_open", False) or getattr(real_session, "_closed", False):
            return

        egress_frame = current_egress_span()
        egress_guarded = egress_frame is not None

        skill_id = str(event.get("skill_id") or "unknown")
        action = str(event.get("action") or "execute")
        status = str(event.get("status") or "ok")
        duration_ms = event.get("duration_ms")
        context_mode = event.get("context_mode")
        sw_trace_id = event.get("trace_id")
        sw_span_id = event.get("span_id")
        span_id = (
            str(egress_frame["span_id"])
            if egress_frame and egress_frame.get("span_id")
            else (str(sw_span_id) if sw_span_id else None)
        )

        model = event.get("model")
        prompt_tokens = event.get("prompt_tokens")
        completion_tokens = event.get("completion_tokens")
        cost = event.get("estimated_cost_usd")
        if cost is None and model and prompt_tokens is not None and completion_tokens is not None:
            cost = estimate_cost_usd(str(model), int(prompt_tokens), int(completion_tokens))

        payload: dict[str, Any] = {
            "source": source,
            "skill_id": skill_id,
            "action": action,
            "status": status,
            "egress_guarded": egress_guarded,
        }
        if duration_ms is not None:
            payload["duration_ms"] = float(duration_ms)
        if context_mode is not None:
            payload["context_mode"] = str(context_mode)
        if sw_trace_id is not None:
            payload["skillware_trace_id"] = str(sw_trace_id)
        if sw_span_id is not None:
            payload["skillware_span_id"] = str(sw_span_id)
        if "args" in event and isinstance(event.get("args"), Mapping):
            payload["args"] = dict(event["args"])
        if event.get("error_type"):
            payload["error_type"] = str(event["error_type"])
        if event.get("error_message"):
            payload["error_message"] = str(event["error_message"])
        if event.get("event_hash"):
            payload["skillware_event_hash"] = str(event["event_hash"])
        if event.get("prev_hash"):
            payload["skillware_prev_hash"] = str(event["prev_hash"])

        telemetry: dict[str, Any] = {"skill_id": skill_id}
        if isinstance(duration_ms, (int, float)):
            telemetry["latency_ms"] = round(float(duration_ms), 3)
        if model is not None:
            telemetry["model"] = str(model)
        if prompt_tokens is not None:
            telemetry["prompt_tokens"] = int(prompt_tokens)
        if completion_tokens is not None:
            telemetry["completion_tokens"] = int(completion_tokens)
        if cost is not None:
            telemetry["estimated_cost_usd"] = float(cost)
        if event.get("event_hash"):
            telemetry["skillware_event_hash"] = str(event["event_hash"])

        if egress_frame is not None:
            egress_frame["dispatches"].append(
                {
                    "skill_id": skill_id,
                    "action": action,
                    "status": status,
                    "duration_ms": duration_ms,
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "estimated_cost_usd": cost,
                    "skillware_event_hash": event.get("event_hash"),
                    "skillware_prev_hash": event.get("prev_hash"),
                }
            )

        try:
            real_session.emit(
                "skill.dispatch",
                payload,
                span_id=span_id,
                telemetry=telemetry,
            )
            if not egress_guarded:
                real_session.emit(
                    "skill.egress_bypass",
                    {
                        "source": source,
                        "skill_id": skill_id,
                        "action": action,
                        "status": status,
                        "reason": (
                            "Skillware SkillContext dispatch fired outside AURA membrane egress"
                        ),
                        "skillware_event_hash": event.get("event_hash"),
                    },
                    span_id=span_id,
                    telemetry=telemetry,
                )
        except Exception:
            # Never break host skill execution if audit callback encounters a closed session
            return

    return _on_dispatch


def _canonical_skillware_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _verify_skillware_jsonl(path: Path) -> tuple[bool, list[dict[str, Any]]]:
    """Verify a Skillware hash-chained JSONL log and return (valid, parsed_records)."""
    if not path.is_file():
        raise FileNotFoundError(f"Skillware audit log not found: {path}")

    records: list[dict[str, Any]] = []
    expected_prev = SKILLWARE_GENESIS_HASH
    valid = True

    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return False, records
            if not isinstance(record, dict):
                return False, records
            records.append(record)
            prev_hash = record.get("prev_hash")
            event_hash = record.get("event_hash")
            if not isinstance(prev_hash, str) or not isinstance(event_hash, str):
                valid = False
                continue
            if not hmac.compare_digest(prev_hash, expected_prev):
                valid = False
            body = {k: v for k, v in record.items() if k != "event_hash"}
            computed = hashlib.sha256(_canonical_skillware_json(body).encode("utf-8")).hexdigest()
            if not hmac.compare_digest(event_hash, computed):
                valid = False
            expected_prev = event_hash

    return valid, records


@dataclass
class DualChainVerificationResult:
    """Result of cross-verifying an AURA AuditSpine JSONL against a Skillware audit JSONL."""

    valid: bool
    aura_chain_valid: bool | None
    skillware_chain_valid: bool
    anchored_count: int = 0
    missing_in_skillware: list[str] = field(default_factory=list)
    mismatched_anchors: list[dict[str, Any]] = field(default_factory=list)
    unanchored_in_aura: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "aura_chain_valid": self.aura_chain_valid,
            "skillware_chain_valid": self.skillware_chain_valid,
            "anchored_count": self.anchored_count,
            "missing_in_skillware": list(self.missing_in_skillware),
            "mismatched_anchors": list(self.mismatched_anchors),
            "unanchored_in_aura": list(self.unanchored_in_aura),
        }


def verify_dual_audit_chain(
    aura_jsonl_path: str | Path,
    skillware_jsonl_path: str | Path,
) -> DualChainVerificationResult:
    """
    Cryptographically cross-verify an AURA spine JSONL and a Skillware audit JSONL.

    Checks:
    1. AURA's SHA-256 hash chain is intact.
    2. Skillware's SHA-256 hash chain is intact.
    3. Every ``skillware_event_hash`` anchored in AURA exists unmodified in Skillware's log
       with matching ``skill_id`` and ``prev_hash``.
    4. Flags any Skillware audit records not anchored in AURA (potential shadow executions).
    """
    aura_path = Path(aura_jsonl_path)
    sw_path = Path(skillware_jsonl_path)
    if not aura_path.is_file():
        raise FileNotFoundError(f"AURA audit log not found: {aura_path}")

    spine = AuditSpine.from_jsonl(aura_path)
    aura_valid = verify_hash_chain(spine)
    sw_valid, sw_records = _verify_skillware_jsonl(sw_path)

    sw_by_hash: dict[str, dict[str, Any]] = {}
    for rec in sw_records:
        eh = rec.get("event_hash")
        if isinstance(eh, str):
            sw_by_hash[eh] = rec

    anchored_hashes: set[str] = set()
    missing_in_sw: list[str] = []
    mismatched: list[dict[str, Any]] = []

    for evt in spine.stream():
        payload = evt.payload or {}
        telemetry = evt.telemetry or {}
        anchor = payload.get("skillware_event_hash") or telemetry.get("skillware_event_hash")
        if not isinstance(anchor, str) or not anchor:
            continue
        if anchor in anchored_hashes:
            continue
        anchored_hashes.add(anchor)

        sw_rec = sw_by_hash.get(anchor)
        if sw_rec is None:
            missing_in_sw.append(anchor)
            continue

        aura_skill = payload.get("skill_id") or telemetry.get("skill_id")
        sw_skill = sw_rec.get("skill_id")
        aura_prev = payload.get("skillware_prev_hash")
        sw_prev = sw_rec.get("prev_hash")
        if (aura_skill and sw_skill and str(aura_skill) != str(sw_skill)) or (
            aura_prev and sw_prev and not hmac.compare_digest(str(aura_prev), str(sw_prev))
        ):
            mismatched.append(
                {
                    "event_hash": anchor,
                    "aura_skill_id": aura_skill,
                    "skillware_skill_id": sw_skill,
                    "aura_prev_hash": aura_prev,
                    "skillware_prev_hash": sw_prev,
                }
            )

    unanchored_in_aura = [h for h in sw_by_hash if h not in anchored_hashes]
    overall = (
        (aura_valid is True)
        and sw_valid
        and not missing_in_sw
        and not mismatched
        and not unanchored_in_aura
    )
    return DualChainVerificationResult(
        valid=overall,
        aura_chain_valid=aura_valid,
        skillware_chain_valid=sw_valid,
        anchored_count=len(anchored_hashes),
        missing_in_skillware=missing_in_sw,
        mismatched_anchors=mismatched,
        unanchored_in_aura=unanchored_in_aura,
    )
