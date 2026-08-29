"""JSONL session export."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from aura.core.audit_report import AuditReport, AuditReportBuilder
from aura.core.conformance import ConformanceEngine, ConformanceReport
from aura.core.errors import ExportError
from aura.core.session import Session
from aura.exporters.otel import export_otel_jsonl
from aura.core.spine import AuditSpine


def build_session_summary(
    session: Session,
    *,
    conformance: ConformanceReport | None = None,
    audit_report: AuditReport | None = None,
) -> dict[str, Any]:
    """In-memory session summary (same shape as ``.summary.json`` on disk)."""
    if conformance is None and session.spine:
        engine = ConformanceEngine()
        conformance = engine.summarize(
            session.spine,
            session.declared_rules,
            session.open_snapshot_hash,
            sequencer_spec=session.sequencer_spec or session.profile.sequencer,
        )

    if audit_report is None and session.spine and conformance:
        audit_report = AuditReportBuilder().build(
            session.spine,
            conformance,
            agent_ref=session.profile.agent_ref,
            policy_version=session.profile.policy_version,
        )

    return {
        "session_id": session.session_id,
        "aura_id": session.profile.aura_id,
        "agent_ref": session.profile.agent_ref,
        "agent_name": session.profile.name,
        "policy_version": session.profile.policy_version,
        "mode": session.mode.value,
        "snapshot_hash": session.snapshot_hash,
        "open_snapshot_hash": session.open_snapshot_hash,
        "trace_id": session.trace_id,
        "agent_ids": session.profile.id_trailer(),
        "purpose": session.profile.purpose,
        "conformance": conformance.to_dict() if conformance else None,
        "audit_report": audit_report.to_dict() if audit_report else None,
        "event_count": len(session.spine.stream()) if session.spine else 0,
        "log": str(session.log_path) if session.log_path else None,
    }


def _atomic_replace(staging_path: Path, final_path: Path) -> None:
    staging_path.replace(final_path)


def _write_staging_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_staging_otel(session_id: str, sessions_dir: Path, staging_path: Path) -> None:
    log_path = sessions_dir / f"{session_id}.jsonl"
    events = AuditSpine.read_jsonl(log_path)
    export_otel_jsonl(events, staging_path)


def export_session(
    session: Session,
    sessions_dir: Path,
    *,
    conformance: ConformanceReport | None = None,
    include_otel: bool = True,
) -> dict[str, str]:
    """Write summary JSON and OTel JSONL atomically alongside the live JSONL log."""
    summary = build_session_summary(session, conformance=conformance)
    if not session.spine:
        raise ExportError(session.session_id, "session spine missing")

    if not session.log_path or not session.log_path.is_file():
        raise ExportError(session.session_id, "JSONL audit trail missing")

    token = uuid.uuid4().hex
    summary_final = sessions_dir / f"{session.session_id}.summary.json"
    summary_staging = sessions_dir / f"{session.session_id}.summary.json.{token}.staging"
    otel_final = sessions_dir / f"{session.session_id}.otel.jsonl"
    otel_staging = sessions_dir / f"{session.session_id}.otel.jsonl.{token}.staging"
    staged: list[Path] = []

    try:
        _write_staging_json(summary_staging, summary)
        staged.append(summary_staging)
        if include_otel:
            _write_staging_otel(session.session_id, sessions_dir, otel_staging)
            staged.append(otel_staging)

        _atomic_replace(summary_staging, summary_final)
        staged.remove(summary_staging)
        if include_otel:
            _atomic_replace(otel_staging, otel_final)
            staged.remove(otel_staging)
    except Exception as exc:
        for path in staged:
            path.unlink(missing_ok=True)
        raise ExportError(session.session_id, str(exc)) from exc

    paths: dict[str, str] = {"summary": str(summary_final), "jsonl": str(session.log_path)}
    if include_otel:
        paths["otel"] = str(otel_final)
    return paths
