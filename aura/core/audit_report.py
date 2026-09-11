"""Structured audit report with findings and recommendations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aura.core.conformance import ConformanceReport
from aura.core.spine import AuditSpine, verify_hash_chain


@dataclass
class AuditReport:
    verdict: str  # pass | fail | warn
    scorecard: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    hash_chain_valid: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "scorecard": self.scorecard,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "hash_chain_valid": self.hash_chain_valid,
        }


class AuditReportBuilder:
    """Rule-based narrative report from spine + conformance."""

    def build(
        self,
        spine: AuditSpine,
        conformance: ConformanceReport,
        *,
        agent_ref: str | None = None,
        policy_version: str | None = None,
    ) -> AuditReport:
        events = spine.stream()
        tool_calls = [e for e in events if e.kind == "tool.call"]
        tool_denied = [e for e in events if e.kind == "constraint.violated"]
        approvals = [e for e in events if e.kind == "constraint.approved"]
        pending = [e for e in events if e.kind == "constraint.approval_required"]
        seq_starts = [e for e in events if e.kind == "sequencer.step.start"]
        seq_errors = [
            e
            for e in events
            if e.kind == "sequencer.step.end" and e.payload.get("status") == "error"
        ]

        scorecard = {
            "policy": {
                "declared_rules": len(conformance.declared_rules),
                "violations": len(tool_denied),
                "pending_approvals": len(pending),
                "approvals_granted": len(approvals),
            },
            "tools": {
                "calls": len(tool_calls),
                "denied": sum(
                    1
                    for e in tool_denied
                    if (e.payload.get("rule") or {}).get("type") in ("deny_tools", "allow_tools")
                ),
            },
            "sequencer": {
                "steps_started": len(seq_starts),
                "step_errors": len(seq_errors),
            },
            "goal_slo": {
                "goal_drifts": sum(1 for e in events if e.kind == "conformance.drift"),
                "schedule_misses": sum(1 for e in events if e.kind == "slo.missed"),
            },
            "events": conformance.event_count,
        }

        findings: list[dict[str, Any]] = []
        recommendations: list[str] = []

        for event in tool_denied:
            rule = event.payload.get("rule") or {}
            rtype = rule.get("type", "unknown")
            findings.append(
                {
                    "severity": "high",
                    "code": "POLICY_VIOLATION",
                    "message": event.payload.get("message", "Policy violation"),
                    "rule_type": rtype,
                    "event_id": event.event_id,
                }
            )
            if rtype == "deny_tools":
                tool = (event.payload.get("event") or {}).get("tool", "unknown")
                recommendations.append(
                    f"Tool '{tool}' was denied — remove it from the pipeline or "
                    "update constitution allow/deny rules."
                )
            elif rtype == "max_tokens_per_step":
                recommendations.append(
                    "Token budget exceeded — raise the limit or emit fewer tokens per step."
                )

        if pending and not approvals:
            findings.append(
                {
                    "severity": "high",
                    "code": "APPROVAL_PENDING",
                    "message": "Session closed with unapproved actions",
                    "count": len(pending),
                }
            )
            recommendations.append(
                "Call approve(request_id, principal=...) before retrying blocked actions."
            )

        seq_check = next((c for c in conformance.checks if c.get("type") == "sequencer"), None)
        if seq_check and not seq_check.get("passed", True):
            missing = (seq_check.get("violations") or [{}])[0].get("missing", [])
            findings.append(
                {
                    "severity": "high",
                    "code": "SEQUENCER_INCOMPLETE",
                    "message": "Declared sequencer steps were not all completed",
                    "missing_steps": missing,
                }
            )
            recommendations.append(
                "Re-run with run.run_sequencer() until all declared steps complete, "
                "or simplify the sequencer spec."
            )

        for event in events:
            if event.kind == "conformance.drift":
                payload = event.payload or {}
                findings.append(
                    {
                        "severity": "high",
                        "code": "GOAL_DRIFT",
                        "message": payload.get(
                            "reason", "Observed behavior drifted from declared goal"
                        ),
                        "tool": payload.get("tool"),
                        "goal": payload.get("goal"),
                        "event_id": event.event_id,
                    }
                )
                recommendations.append(
                    "Align tool intents with profile goal variables or tighten egress allowlists."
                )
            elif event.kind == "slo.missed":
                payload = event.payload or {}
                findings.append(
                    {
                        "severity": "high",
                        "code": "SCHEDULE_SLO_MISS",
                        "message": payload.get("reason", "Schedule SLO was not met"),
                        "required_tool": payload.get("required_tool"),
                        "deadline": payload.get("deadline"),
                        "event_id": event.event_id,
                    }
                )
                recommendations.append(
                    "Complete required work within the schedule window or adjust "
                    "profile schedule/grace."
                )

        for event in seq_errors:
            findings.append(
                {
                    "severity": "medium",
                    "code": "STEP_FAILED",
                    "message": event.payload.get("error", "Step failed"),
                    "step_id": event.step_id,
                    "event_id": event.event_id,
                }
            )

        for event in events:
            if event.kind == "escalation.fired":
                payload = event.payload or {}
                findings.append(
                    {
                        "severity": "medium",
                        "code": "ESCALATION_FIRED",
                        "message": (
                            f"Escalation playbook fired for {payload.get('trigger_kind', 'event')}"
                        ),
                        "actions": payload.get("actions"),
                        "event_id": event.event_id,
                    }
                )

        open_evt = next((e for e in events if e.kind == "session.open"), None)
        spectrum = (open_evt.payload or {}).get("spectrum") if open_evt else None
        if isinstance(spectrum, dict) and spectrum.get("verified_identity_required"):
            bound = [e for e in events if e.kind == "identity.bound"]
            source = spectrum.get("verified_identity_required_source", "unknown")
            if not bound:
                findings.append(
                    {
                        "severity": "high",
                        "code": "VERIFIED_IDENTITY_REQUIRED",
                        "message": (
                            "Session policy required verified operator identity but "
                            "identity.bound was never emitted"
                        ),
                        "policy_source": source,
                    }
                )
                recommendations.append(
                    "Configure an identity adapter (OIDC, Auth0, mock) or pass a verified "
                    "operator at session open when spectrum.identity_required is true."
                )
            else:
                for evt in bound:
                    payload = evt.payload or {}
                    operator = payload.get("operator") or {}
                    if not operator.get("verified", False):
                        findings.append(
                            {
                                "severity": "high",
                                "code": "VERIFIED_IDENTITY_REQUIRED",
                                "message": (
                                    "Session policy required verified operator identity but "
                                    f"bound operator via {operator.get('method', 'unknown')} "
                                    "is not verified"
                                ),
                                "policy_source": source,
                                "method": operator.get("method"),
                                "event_id": evt.event_id,
                            }
                        )
                        recommendations.append(
                            "Use a third-party IdP adapter that sets verified=true, or "
                            "opt out with spectrum.identity_required: false when manual "
                            "labels are acceptable."
                        )

        chain_ok = verify_hash_chain(spine)
        if chain_ok is False:
            findings.append(
                {
                    "severity": "critical",
                    "code": "HASH_CHAIN_BROKEN",
                    "message": "Audit log hash chain verification failed",
                }
            )
            recommendations.append(
                "Treat this session log as tampered or corrupted; re-run the session."
            )

        if conformance.passed and not findings:
            verdict = "pass"
        elif conformance.passed and findings:
            verdict = "warn"
        else:
            verdict = "fail"

        if verdict == "pass" and agent_ref and policy_version:
            recommendations.append(
                f"Agent '{agent_ref}' at policy v{policy_version} passed — "
                "archive the session export for compliance records."
            )

        return AuditReport(
            verdict=verdict,
            scorecard=scorecard,
            findings=findings,
            recommendations=list(dict.fromkeys(recommendations)),
            hash_chain_valid=chain_ok,
        )
