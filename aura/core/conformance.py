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
        return ConformanceReport(
            passed=passed,
            violations=violations,
            checks=checks,
            declared_rules=declared_rules,
            event_count=len(events),
            snapshot_hash=snapshot_hash,
        )
