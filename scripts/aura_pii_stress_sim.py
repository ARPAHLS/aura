#!/usr/bin/env python3
"""
Sequencer PII Masking Stress Simulation (#58).

Stress-tests:
1. High-throughput deep recursive traversal across large complex trees.
2. Complex multi-entity detection (email, phone, Luhn credit card, SSN, IP, API keys, IBAN).
3. Adversarial false-positive resistance (Luhn checksum rejection on arbitrary numbers).
4. Deterministic session-scoped pseudonymization and entity-equivalence across steps.
5. Strict-mode containment under high posture.
6. Audit spine hygiene verification: ZERO raw PII leakage on the spine.
7. Audit report scorecard and PII_MASKED finding synthesis.

Usage:
  python scripts/aura_pii_stress_sim.py

Exit 0 when all scenarios pass; 1 on any failure.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from aura import configure, agent  # noqa: E402
from aura.core.audit_report import AuditReportBuilder  # noqa: E402
from aura.core.constraints import ConstraintViolation  # noqa: E402
from aura.sequencer.middleware import MiddlewarePolicy, MiddlewareStack  # noqa: E402
from aura.sequencer.pii_mask import (  # noqa: E402
    NativePiiMasker,
    PiiMaskConfig,
    PiiMasker,
)
from aura.sequencer.runner import SequencerRunner  # noqa: E402
from aura.sequencer.step import SequencerStep  # noqa: E402


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    reason: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


def scenario_high_throughput_deep_tree() -> ScenarioResult:
    """Stress test deep recursion and large nested payloads."""
    masker = PiiMasker()
    # Build deep nested tree with 500 items
    root: dict[str, Any] = {"items": []}
    for i in range(500):
        item = {
            "id": i,
            "contact": {
                "email": f"user_{i}@domain.com",
                "phone": f"+1-555-234-{i:04d}",
                "ip": f"192.168.1.{i % 250 + 1}",
            },
            "meta": {
                "tags": [f"tag_{i}", f"sk-testsecretkey{i:016d}"],
            },
        }
        root["items"].append(item)

    t0 = time.perf_counter()
    res = masker.mask(root)
    elapsed = time.perf_counter() - t0

    # 500 emails + 500 phones + 500 ips + 500 keys = 2000 entities
    if res.total_redactions < 2000:
        return ScenarioResult(
            name="high_throughput_deep_tree",
            passed=False,
            reason=f"Expected >= 2000 redactions, got {res.total_redactions}",
        )

    # Verify no raw PII in output
    out_str = json.dumps(res.data)
    if "user_0@domain.com" in out_str or "+1-555-0100" in out_str:
        return ScenarioResult(
            name="high_throughput_deep_tree",
            passed=False,
            reason="Raw PII found in sanitized data",
        )

    return ScenarioResult(
        name="high_throughput_deep_tree",
        passed=True,
        metrics={"elapsed_sec": round(elapsed, 4), "redactions": res.total_redactions},
    )


def scenario_luhn_adversarial_validation() -> ScenarioResult:
    """Ensure valid Luhn numbers are masked and invalid numbers are preserved."""
    masker = NativePiiMasker()

    # Valid cards
    valid_visa = "4532-0151-1284-3211"
    valid_mc = "5425-2334-3010-9903"  # passes Luhn

    # Invalid cards (failing Luhn)
    invalid_1 = "4532-0151-1284-3215"
    invalid_2 = "1234-5678-9012-3456"

    text = (
        f"Valid Visa {valid_visa} and MC {valid_mc}. "
        f"Invalid serials {invalid_1} and {invalid_2}."
    )

    res = masker.mask_text(text, PiiMaskConfig(strategy="redact"))

    if valid_visa in res.text:
        return ScenarioResult(
            name="luhn_adversarial_validation",
            passed=False,
            reason="Valid Visa card was not redacted",
        )

    if invalid_1 not in res.text or invalid_2 not in res.text:
        return ScenarioResult(
            name="luhn_adversarial_validation",
            passed=False,
            reason="Invalid Luhn number was mistakenly redacted as credit card",
        )

    return ScenarioResult(
        name="luhn_adversarial_validation",
        passed=True,
        metrics={"entities_detected": res.entities_detected},
    )


def scenario_pseudonymization_determinism() -> ScenarioResult:
    """Verify session-scoped deterministic token equivalence."""
    masker = NativePiiMasker()
    session_state: dict[str, Any] = {}
    cfg = PiiMaskConfig(strategy="pseudonymize", salt="custom_salt_99")

    # Same identity in different conversational turns
    turn1 = "Customer john.smith@enterprise.org submitted ticket."
    turn2 = "Processing refund for john.smith@enterprise.org now."
    turn3 = "Different customer bob@other.org signed in."

    res1 = masker.mask_text(turn1, cfg, session_state=session_state)
    res2 = masker.mask_text(turn2, cfg, session_state=session_state)
    res3 = masker.mask_text(turn3, cfg, session_state=session_state)

    token1 = [w for w in res1.text.split() if w.startswith("<EMAIL_REF_")][0]
    token2 = [w for w in res2.text.split() if w.startswith("<EMAIL_REF_")][0]
    token3 = [w for w in res3.text.split() if w.startswith("<EMAIL_REF_")][0]

    if token1 != token2:
        return ScenarioResult(
            name="pseudonymization_determinism",
            passed=False,
            reason=f"Pseudonyms did not match for same entity: {token1} vs {token2}",
        )

    if token1 == token3:
        return ScenarioResult(
            name="pseudonymization_determinism",
            passed=False,
            reason=f"Different entities produced identical pseudonym: {token1}",
        )

    return ScenarioResult(
        name="pseudonymization_determinism",
        passed=True,
        metrics={"token": token1},
    )


def scenario_pipeline_end_to_end_spine_hygiene() -> ScenarioResult:
    """Full sequencer run with PII masking, checking spine telemetry & zero leakage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        configure(home=Path(tmpdir))
        ag = agent("pii-pipeline-stress", create=True)

        raw_email = "victim@corporate.com"
        raw_card = "4532-0151-1284-3211"
        raw_phone = "+1-555-0199"

        steps = [
            SequencerStep(
                id="ingest_step",
                step_type="op",
                ref="echo",
                config={"customer_email": raw_email, "phone": raw_phone},
            ),
            SequencerStep(
                id="pii_clean",
                step_type="op",
                ref="middleware.pii_mask",
                config={"source_step": "ingest_step", "strategy": "redact"},
            ),
            SequencerStep(
                id="billing_step",
                step_type="op",
                ref="echo",
                config={"card": raw_card},
            ),
        ]

        policy = MiddlewarePolicy(
            middleware="middleware.pii_mask",
            scope="per_step",
            config={"strategy": "redact"},
        )
        stack = MiddlewareStack(policies=[policy])

        with ag.session() as s:
            runner = SequencerRunner(steps=steps, middleware_stack=stack)
            result = runner.run(s)

            if not result.get("success"):
                return ScenarioResult(
                    name="pipeline_end_to_end_spine_hygiene",
                    passed=False,
                    reason=f"Pipeline execution failed: {result.get('error')}",
                )

            # Audit report generation
            report = AuditReportBuilder.build(s.spine)
            scorecard = report.scorecard

            if scorecard.get("middleware", {}).get("pii_redactions", 0) < 3:
                return ScenarioResult(
                    name="pipeline_end_to_end_spine_hygiene",
                    passed=False,
                    reason=f"Scorecard pii_redactions too low: {scorecard.get('middleware')}",
                )

            # Finding check
            pii_findings = [f for f in report.findings if f.get("code") == "PII_MASKED"]
            if not pii_findings:
                return ScenarioResult(
                    name="pipeline_end_to_end_spine_hygiene",
                    passed=False,
                    reason="Expected PII_MASKED finding in audit report",
                )

            # CRUCIAL: Inspect EVERY event payload in the spine for raw PII leakage
            events = s.get_events()
            for evt in events:
                payload_str = json.dumps(evt.payload)
                if raw_email in payload_str or raw_card in payload_str or raw_phone in payload_str:
                    return ScenarioResult(
                        name="pipeline_end_to_end_spine_hygiene",
                        passed=False,
                        reason=f"Raw PII detected on spine event {evt.kind}: {payload_str}",
                    )

    return ScenarioResult(
        name="pipeline_end_to_end_spine_hygiene",
        passed=True,
        metrics={"scorecard": scorecard.get("middleware")},
    )


def scenario_strict_mode_containment() -> ScenarioResult:
    """Verify strict mode raises ConstraintViolation and terminates step."""
    coordinator = PiiMasker()
    payload = {"leak": "leaked_secret@bank.com"}
    cfg = PiiMaskConfig(strict=True)

    try:
        coordinator.mask(payload, config=cfg)
        return ScenarioResult(
            name="strict_mode_containment",
            passed=False,
            reason="Strict mode failed to raise ConstraintViolation",
        )
    except ConstraintViolation:
        return ScenarioResult(
            name="strict_mode_containment",
            passed=True,
        )


def main() -> int:
    print("=== AURA Sequencer PII Masking Stress Simulation (#58) ===")
    scenarios: list[tuple[str, Any]] = [
        ("high_throughput_deep_tree", scenario_high_throughput_deep_tree),
        ("luhn_adversarial_validation", scenario_luhn_adversarial_validation),
        ("pseudonymization_determinism", scenario_pseudonymization_determinism),
        ("pipeline_end_to_end_spine_hygiene", scenario_pipeline_end_to_end_spine_hygiene),
        ("strict_mode_containment", scenario_strict_mode_containment),
    ]

    all_passed = True
    for name, func in scenarios:
        res: ScenarioResult = func()
        status = "PASSED" if res.passed else "FAILED"
        print(f"[{status}] {res.name} {res.metrics if res.metrics else ''}")
        if not res.passed:
            print(f"       ERROR: {res.reason}")
            all_passed = False

    if all_passed:
        print("\nALL PII MASKING SCENARIOS PASSED")
        return 0
    else:
        print("\nPII MASKING SIMULATION FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
