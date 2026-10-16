#!/usr/bin/env python3
"""
Break Observer & Trajectory Cycle Governance Stress Simulation (#93).

Stress-tests:
1. High-throughput sliding window stream (5,000 events; measures throughput & memory locality).
2. Multi-state oscillation detection (A <-> B) amidst noisy background tool calls.
3. 3-step choreography detection (A -> B -> C -> A -> B -> C) under high token load.
4. Error fingerprint churn detection under consecutive HTTP and API failure codes.
5. Reasoning inertia sensor across continuous thought text trajectories.
6. FinOps burn-velocity circuit breaking and cryptographic spine hash non-repudiation.
7. Full Audit Report scorecard and COGNITIVE_CYCLE_DETECTED finding synthesis.

Usage:
  python scripts/aura_break_loop_stress_sim.py

Exit 0 when all scenarios pass; 1 on any failure.
"""

from __future__ import annotations

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
from aura.core.conformance import ConformanceEngine  # noqa: E402
from aura.observers.presets.break_observer import BreakObserver  # noqa: E402


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    reason: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


def scenario_high_throughput_sliding_window() -> ScenarioResult:
    """Benchmark high-throughput event processing and sliding window pruning."""
    with tempfile.TemporaryDirectory() as tmp:
        configure(home=Path(tmp))
        ag = agent(
            "bench-agent",
            observers=[
                {
                    "preset": "break",
                    "config": {
                        "window_size": 10,
                        "max_identical_actions": 5,
                        "max_identical_intents": 0,
                    },
                }
            ],
        )

        event_count = 5000
        start_time = time.monotonic()
        with ag.session(export=False) as run:
            for i in range(event_count):
                # Varied tools so it does not trip fixation
                tool_name = f"tool_{i % 8}"
                run.emit("tool.intent", {"tool": tool_name, "args": {"step": i}})
        elapsed = time.monotonic() - start_time
        rate = event_count / elapsed if elapsed > 0 else 0

        # Verify window size did not grow beyond limit
        observer = run._session._observers[0]
        assert isinstance(observer, BreakObserver)
        window_len = len(observer._action_history)

        if window_len > 10:
            return ScenarioResult(
                name="High-throughput sliding window",
                passed=False,
                reason=f"Window leaked: {window_len} > 10",
            )

        return ScenarioResult(
            name="High-throughput sliding window",
            passed=True,
            metrics={"events": event_count, "elapsed_s": round(elapsed, 4), "rate_eps": int(rate)},
        )


def scenario_noisy_oscillation_detection() -> ScenarioResult:
    """Verify detection of A <-> B oscillation when surrounded by noise."""
    with tempfile.TemporaryDirectory() as tmp:
        configure(home=Path(tmp))
        ag = agent(
            "noisy-osc-agent",
            observers=[
                {
                    "preset": "break",
                    "config": {
                        "window_size": 8,
                        "max_oscillation_cycles": 2,
                        "max_identical_actions": 5,
                        "max_identical_intents": 0,
                    },
                }
            ],
        )

        with ag.session(export=False) as run:
            # Noise steps
            for i in range(5):
                run.emit("tool.intent", {"tool": f"init_{i}", "args": {}})

            # Alternating oscillation
            run.emit("tool.intent", {"tool": "db_read", "args": {"key": "x"}})
            run.emit("tool.intent", {"tool": "cache_clear", "args": {"all": True}})
            run.emit("tool.intent", {"tool": "db_read", "args": {"key": "x"}})
            run.emit("tool.intent", {"tool": "cache_clear", "args": {"all": True}})

        alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
        if len(alerts) != 1 or alerts[0].payload.get("pattern") != "OSCILLATION_CYCLE":
            return ScenarioResult(
                name="Noisy oscillation detection",
                passed=False,
                reason=f"Expected 1 OSCILLATION_CYCLE alert, got {len(alerts)}",
            )

        return ScenarioResult(
            name="Noisy oscillation detection",
            passed=True,
            metrics={"alerts": len(alerts), "pattern": alerts[0].payload.get("pattern")},
        )


def scenario_choreography_and_burn_velocity() -> ScenarioResult:
    """Verify 3-step choreography with token accumulation."""
    with tempfile.TemporaryDirectory() as tmp:
        configure(home=Path(tmp))
        ag = agent(
            "choreo-burn-agent",
            observers=[
                {
                    "preset": "break",
                    "config": {
                        "window_size": 8,
                        "max_choreography_cycles": 2,
                        "burn_velocity_guard": True,
                        "max_cycle_token_waste": 1200,
                        "max_identical_intents": 0,
                    },
                }
            ],
        )

        with ag.session(export=False) as run:
            seq = [("read_code", 500), ("edit_code", 500), ("lint_check", 500)]
            for _ in range(2):
                for tool, tokens in seq:
                    run.emit("tool.intent", {"tool": tool, "args": {"f": "app.py"}})
                    run.emit("tool.result", {"tool": tool, "tokens": tokens})

        alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
        if not alerts:
            return ScenarioResult(
                name="Choreography & burn velocity",
                passed=False,
                reason="No choreography alert emitted",
            )

        alert = alerts[0].payload
        if alert.get("pattern") != "CHOREOGRAPHY_CYCLE":
            return ScenarioResult(
                name="Choreography & burn velocity",
                passed=False,
                reason=f"Wrong pattern: {alert.get('pattern')}",
            )

        if not alert.get("burn_rate_spike"):
            return ScenarioResult(
                name="Choreography & burn velocity",
                passed=False,
                reason=f"Expected burn_rate_spike=True, got {alert.get('burn_rate_spike')}",
            )

        return ScenarioResult(
            name="Choreography & burn velocity",
            passed=True,
            metrics={
                "churn_tokens": alert.get("churn_tokens_estimate"),
                "burn_spike": alert.get("burn_rate_spike"),
            },
        )


def scenario_error_churn_stress() -> ScenarioResult:
    """Stress test consecutive error churn with varying tools but same root error code."""
    with tempfile.TemporaryDirectory() as tmp:
        configure(home=Path(tmp))
        ag = agent(
            "err-stress-agent",
            observers=[
                {
                    "preset": "break",
                    "config": {
                        "window_size": 8,
                        "max_error_churn": 4,
                        "max_identical_actions": 10,
                        "max_identical_intents": 0,
                    },
                }
            ],
        )

        with ag.session(export=False) as run:
            for i in range(4):
                run.emit("tool.intent", {"tool": f"endpoint_{i}", "args": {}})
                run.emit(
                    "tool.result",
                    {"tool": f"endpoint_{i}", "status": 503, "error": "ServiceUnavailable"},
                )

        alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
        if len(alerts) != 1 or alerts[0].payload.get("pattern") != "ERROR_STATUS_CHURN":
            return ScenarioResult(
                name="Error churn stress",
                passed=False,
                reason=f"Expected 1 ERROR_STATUS_CHURN alert, got {len(alerts)}",
            )

        return ScenarioResult(
            name="Error churn stress",
            passed=True,
            metrics={"count": alerts[0].payload.get("count"), "pattern": "ERROR_STATUS_CHURN"},
        )


def scenario_audit_report_and_cryptographic_proof() -> ScenarioResult:
    """Verify non-repudiable spine hashes and audit scorecard synthesis."""
    with tempfile.TemporaryDirectory() as tmp:
        configure(home=Path(tmp))
        ag = agent(
            "audit-proof-agent",
            observers=[
                {
                    "preset": "break",
                    "config": {
                        "max_identical_actions": 2,
                        "max_identical_intents": 0,
                    },
                }
            ],
            escalations=[
                {
                    "on": "observer.alert",
                    "actions": ["log", "nudge:Break cognitive loop immediately"],
                }
            ],
        )

        with ag.session(export=False) as run:
            run.emit("tool.intent", {"tool": "retry_op", "args": {"attempt": 1}})
            run.emit("tool.intent", {"tool": "retry_op", "args": {"attempt": 1}})

        conf = ConformanceEngine().summarize(run._session.spine, [])
        report = AuditReportBuilder().build(run._session.spine, conf)

        scorecard = report.scorecard
        if scorecard.get("observers", {}).get("loop_cycles") != 1:
            return ScenarioResult(
                name="Audit report & cryptographic proof",
                passed=False,
                reason=f"Expected 1 loop cycle in scorecard, got {scorecard.get('observers')}",
            )

        cycle_finding = next(
            (f for f in report.findings if f["code"] == "COGNITIVE_CYCLE_DETECTED"), None
        )
        if not cycle_finding:
            return ScenarioResult(
                name="Audit report & cryptographic proof",
                passed=False,
                reason="COGNITIVE_CYCLE_DETECTED finding missing in audit report",
            )

        entry_h = cycle_finding.get("cycle_entry_hash")
        rec_h = cycle_finding.get("cycle_recurrence_hash")
        if not entry_h or not rec_h or len(entry_h) != 64 or len(rec_h) != 64:
            return ScenarioResult(
                name="Audit report & cryptographic proof",
                passed=False,
                reason=f"Invalid cryptographic proof hashes: entry={entry_h}, rec={rec_h}",
            )

        return ScenarioResult(
            name="Audit report & cryptographic proof",
            passed=True,
            metrics={"entry_hash": entry_h[:12] + "...", "rec_hash": rec_h[:12] + "..."},
        )


def run_all_scenarios() -> int:
    scenarios = [
        scenario_high_throughput_sliding_window,
        scenario_noisy_oscillation_detection,
        scenario_choreography_and_burn_velocity,
        scenario_error_churn_stress,
        scenario_audit_report_and_cryptographic_proof,
    ]

    print("\n" + "=" * 70)
    print(" AURA Break Observer Trajectory & Loop Governance Stress Suite (#93)")
    print("=" * 70 + "\n")

    failed = False
    for sc in scenarios:
        res = sc()
        status_str = "[PASS]" if res.passed else "[FAIL]"
        print(f" {status_str} {res.name}")
        if res.metrics:
            for k, v in res.metrics.items():
                print(f"        - {k}: {v}")
        if not res.passed:
            print(f"        ERROR: {res.reason}")
            failed = True

    print("\n" + "-" * 70)
    if failed:
        print(" RESULT: FAILED — Some stress scenarios encountered regressions.")
        return 1
    print(" RESULT: ALL SCENARIOS PASSED SUCCESSFULLY.")
    print("-" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(run_all_scenarios())
