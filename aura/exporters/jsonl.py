"""JSONL session export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aura.core.audit_report import AuditReportBuilder
from aura.core.conformance import ConformanceEngine, ConformanceReport
from aura.core.session import Session
from aura.exporters.otel import export_session_otel


def export_session(
    session: Session,
    sessions_dir: Path,
    *,
    conformance: ConformanceReport | None = None,
    include_otel: bool = True,
) -> dict[str, str]:
    """Write summary JSON alongside existing JSONL log."""
    if conformance is None and session.spine:
        engine = ConformanceEngine()
        conformance = engine.summarize(
            session.spine,
            session.rules,
            session.snapshot_hash,
            sequencer_spec=session.sequencer_spec or session.profile.sequencer,
        )

    audit_report = None
    if session.spine and conformance:
        audit_report = AuditReportBuilder().build(
            session.spine,
            conformance,
            agent_ref=session.profile.agent_ref,
            policy_version=session.profile.policy_version,
        )

    summary_path = sessions_dir / f"{session.session_id}.summary.json"
    summary: dict[str, Any] = {
        "session_id": session.session_id,
        "aura_id": session.profile.aura_id,
        "agent_ref": session.profile.agent_ref,
        "agent_name": session.profile.name,
        "policy_version": session.profile.policy_version,
        "mode": session.mode.value,
        "snapshot_hash": session.snapshot_hash,
        "agent_ids": session.profile.id_trailer(),
        "purpose": session.profile.purpose,
        "conformance": conformance.to_dict() if conformance else None,
        "audit_report": audit_report.to_dict() if audit_report else None,
        "event_count": len(session.spine.stream()) if session.spine else 0,
        "log": str(session.log_path) if session.log_path else None,
    }
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    paths: dict[str, str] = {"summary": str(summary_path)}
    if session.log_path:
        paths["jsonl"] = str(session.log_path)
    if include_otel and session.spine:
        otel_path = export_session_otel(session.session_id, sessions_dir)
        paths["otel"] = str(otel_path)
    return paths
