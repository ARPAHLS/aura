"""Conformance — declared vs observed on session close."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aura.core.spine import AuditSpine


@dataclass
class ConformanceReport:
    passed: bool
    violations: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    declared_rules: list[dict[str, Any]] = field(default_factory=list)
    event_count: int = 0
    snapshot_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": self.violations,
            "checks": self.checks,
            "declared_rules": self.declared_rules,
            "event_count": self.event_count,
            "snapshot_hash": self.snapshot_hash,
        }


class ConformanceEngine:
    """Compare declared rules and observed spine events."""

    def summarize(
        self,
        spine: AuditSpine,
        declared_rules: list[dict[str, Any]],
        snapshot_hash: str | None = None,
        sequencer_spec: dict[str, Any] | None = None,
    ) -> ConformanceReport:
        events = spine.stream()
        violations = [
            e.to_dict()
            for e in events
            if e.kind in ("constraint.violated", "session.error")
        ]
        approval_pending = any(e.kind == "constraint.approval_required" for e in events)
        unapproved = approval_pending and not any(
            e.kind == "constraint.approved" for e in events
        )

        checks: list[dict[str, Any]] = []
        for rule in declared_rules:
            rtype = rule.get("type") or rule.get("kind")
            checks.append({"rule": rule, "type": rtype, "declared": True})

        passed = not violations and not unapproved
        seq_check = self._check_sequencer(spine, sequencer_spec)
        if seq_check:
            checks.append(seq_check)
            if not seq_check.get("passed", True):
                passed = False
                for item in seq_check.get("violations", []):
                    violations.append(item)

        return ConformanceReport(
            passed=passed,
            violations=violations,
            checks=checks,
            declared_rules=declared_rules,
            event_count=len(events),
            snapshot_hash=snapshot_hash,
        )

    def _check_sequencer(
        self,
        spine: AuditSpine,
        sequencer_spec: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not sequencer_spec or not sequencer_spec.get("steps"):
            return None
        declared = [s["id"] for s in sequencer_spec["steps"]]
        started = [e.step_id for e in spine.stream() if e.kind == "sequencer.step.start" and e.step_id]
        ended_ok = [
            e.step_id
            for e in spine.stream()
            if e.kind == "sequencer.step.end" and e.step_id and e.payload.get("status") == "ok"
        ]
        missing = [sid for sid in declared if sid not in ended_ok]
        order_ok = started == declared[: len(started)] if started else True
        passed = not missing and order_ok and len(ended_ok) == len(declared)
        result: dict[str, Any] = {
            "type": "sequencer",
            "declared_steps": declared,
            "completed_steps": ended_ok,
            "passed": passed,
        }
        if not passed:
            result["violations"] = [
                {
                    "kind": "sequencer.conformance",
                    "message": "Sequencer did not complete declared step order",
                    "missing": missing,
                    "order_ok": order_ok,
                }
            ]
        return result
