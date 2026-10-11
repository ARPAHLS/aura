"""Example 15 — Sequencer PII Masking Middleware (#58).

Demonstrates:
1. Sequencer pipeline step op (`ref: middleware.pii_mask`) for sanitizing sensitive data.
2. Pseudonymization strategy preserving entity equivalence across agent reasoning.
3. Audit spine zero-leakage guarantee with scorecard metrics and PII_MASKED finding.
"""

from __future__ import annotations

from aura import agent, configure
from aura.core.audit_report import AuditReportBuilder
from aura.sequencer.runner import SequencerRunner

PIPELINE = {
    "steps": [
        {
            "id": "ingest_customer_data",
            "type": "op",
            "ref": "echo",
            "config": {
                "customer": "Alice Smith",
                "email": "alice.smith@enterprise.org",
                "phone": "+44 7911 123456",
                "card": "4532-0151-1284-3211",
            },
        },
        {
            "id": "sanitize_pii",
            "type": "op",
            "ref": "middleware.pii_mask",
            "config": {
                "source_step": "ingest_customer_data",
                "strategy": "pseudonymize",
            },
        },
    ]
}


def main() -> None:
    # Setup
    configure()
    ag = agent(
        "pii-sanitizer-agent",
        purpose="Ingest sensitive data → sanitize PII via sequencer middleware",
        sequencer=PIPELINE,
    )

    # Session execution
    with ag.session(mode="task") as run:
        print(f"Session started: {run.session_id}")

        runner = SequencerRunner(run)
        result = runner.run()

        sanitized = run.state.get("sequencer", {}).get("sanitize_pii", {})
        print("Sanitized Payload:")
        for k, v in sanitized.items():
            print(f"  {k}: {v}")

        # Audit report receipt
        report = AuditReportBuilder.build(run.spine)
        print("\nAudit Scorecard:")
        scorecard = report.scorecard.get("middleware", {})
        print(f"  applied: {scorecard.get('applied')}")
        print(f"  pii_redactions: {scorecard.get('pii_redactions')}")

        findings = [f for f in report.findings if f.get("code") == "PII_MASKED"]
        if findings:
            print(f"\nAudit Finding: {findings[0]['code']} ({findings[0]['message']})")

        run.complete_goal({"status": "completed", "steps": result.get("completed")})
        print("\nSession completed successfully.")


if __name__ == "__main__":
    main()
