"""Tests for BreakObserver trajectory cycle detection, sliding window, and FinOps guards (#93)."""

from __future__ import annotations

from aura.api import agent
from aura.core.audit_report import AuditReportBuilder
from aura.core.conformance import ConformanceEngine


def test_break_observer_legacy_identical_intents_compatibility(aura_home):
    """Verify 100% backward compatibility for legacy max_identical_intents config."""
    ag = agent(
        "legacy-break",
        observers=[{"preset": "break", "config": {"max_identical_intents": 2}}],
    )
    with ag.session(export=False) as run:
        for _ in range(3):
            run.emit("tool.intent", {"tool": "search", "args": {"q": "term"}})

    kinds = [e.kind for e in run._session.spine.stream()]
    assert "observer.alert" in kinds
    alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(alerts) >= 1
    first_alert = alerts[0].payload
    assert first_alert["tool"] == "search"
    assert first_alert["threshold"] == 2
    assert "remedial_directive" in first_alert


def test_action_fixation_detection_in_sliding_window(aura_home):
    """Detect 1-cycle: same action and arguments repeated consecutively."""
    ag = agent(
        "fixation-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "window_size": 6,
                    "max_identical_actions": 3,
                    "max_identical_intents": 0,  # disable legacy global count
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        # 2 calls: should not trip
        run.emit("tool.intent", {"tool": "db_query", "args": {"sql": "SELECT 1"}})
        run.emit("tool.intent", {"tool": "db_query", "args": {"sql": "SELECT 1"}})
        assert not any(e.kind == "observer.alert" for e in run._session.spine.stream())

        # 3rd identical call: trips ACTION_FIXATION
        run.emit("tool.intent", {"tool": "db_query", "args": {"sql": "SELECT 1"}})

    alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(alerts) == 1
    alert = alerts[0].payload
    assert alert["pattern"] == "ACTION_FIXATION"
    assert alert["tool"] == "db_query"
    assert alert["count"] == 3
    assert "BREAK" in alert["remedial_directive"]


def test_state_oscillation_cycle_detection(aura_home):
    """Detect 2-cycle alternating state oscillation: A -> B -> A -> B."""
    ag = agent(
        "oscillation-agent",
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
        # A -> B -> A -> B
        run.emit("tool.intent", {"tool": "git_pull", "args": {"branch": "main"}})
        run.emit("tool.intent", {"tool": "git_stash", "args": {"pop": True}})
        run.emit("tool.intent", {"tool": "git_pull", "args": {"branch": "main"}})
        run.emit("tool.intent", {"tool": "git_stash", "args": {"pop": True}})

    alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(alerts) == 1
    alert = alerts[0].payload
    assert alert["pattern"] == "OSCILLATION_CYCLE"
    assert "git_pull" in alert["tool"] and "git_stash" in alert["tool"]
    assert alert["count"] == 2
    assert "Alternating 2-state oscillation cycle detected" in alert["remedial_directive"]


def test_choreography_cycle_detection(aura_home):
    """Detect 3-cycle execution choreography: A -> B -> C -> A -> B -> C."""
    ag = agent(
        "choreo-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "window_size": 8,
                    "max_choreography_cycles": 2,
                    "max_identical_actions": 5,
                    "max_oscillation_cycles": 5,
                    "max_identical_intents": 0,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        # Sequence: Read -> Edit -> Test -> Read -> Edit -> Test
        run.emit("tool.intent", {"tool": "file_read", "args": {"path": "main.py"}})
        run.emit("tool.intent", {"tool": "file_edit", "args": {"path": "main.py"}})
        run.emit("tool.intent", {"tool": "test_run", "args": {"cmd": "pytest"}})
        run.emit("tool.intent", {"tool": "file_read", "args": {"path": "main.py"}})
        run.emit("tool.intent", {"tool": "file_edit", "args": {"path": "main.py"}})
        run.emit("tool.intent", {"tool": "test_run", "args": {"cmd": "pytest"}})

    alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(alerts) == 1
    alert = alerts[0].payload
    assert alert["pattern"] == "CHOREOGRAPHY_CYCLE"
    assert "file_read -> file_edit -> test_run" in alert["tool"]
    assert alert["count"] == 2
    assert "Repetitive 3-step execution choreography detected" in alert["remedial_directive"]


def test_error_status_churn_detection(aura_home):
    """Detect consecutive identical error fingerprints."""
    ag = agent(
        "error-churn-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "window_size": 6,
                    "max_error_churn": 3,
                    "max_identical_actions": 10,
                    "max_identical_intents": 0,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        for i in range(3):
            run.emit("tool.intent", {"tool": "fetch_api", "args": {"url": f"https://api.test/{i}"}})
            run.emit(
                "tool.result",
                {"tool": "fetch_api", "status": 403, "error": "Forbidden - Invalid Token"},
            )

    alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(alerts) == 1
    alert = alerts[0].payload
    assert alert["pattern"] == "ERROR_STATUS_CHURN"
    assert alert["tool"] == "fetch_api"
    assert alert["count"] == 3
    assert "identical error fingerprint" in alert["remedial_directive"]


def test_reasoning_inertia_detection(aura_home):
    """Detect consecutive turns exhibiting >=85% thought text similarity."""
    ag = agent(
        "thought-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "thought_similarity_threshold": 0.85,
                    "max_thought_inertia": 3,
                    "max_identical_intents": 0,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        # Turn 1
        run.emit(
            "turn.start",
            {"thought": "I should search for the user authentication tokens in settings."},
        )
        run.emit("turn.end", {})
        # Turn 2
        run.emit(
            "turn.start",
            {"thought": "I should search for the user authentication tokens in settings config."},
        )
        run.emit("turn.end", {})
        # Turn 3: highly similar thought
        run.emit(
            "turn.start",
            {"thought": "I should search for the user authentication tokens in settings file."},
        )
        run.emit("turn.end", {})

    alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(alerts) == 1
    alert = alerts[0].payload
    assert alert["pattern"] == "REASONING_INERTIA"
    assert alert["tool"] == "host.reasoning"
    assert "Consecutive reasoning steps show >=" in alert["remedial_directive"]


def test_sliding_window_locality_avoids_false_positives(aura_home):
    """Spaced out identical tool calls across a long session do not falsely trigger."""
    ag = agent(
        "spaced-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "window_size": 4,
                    "max_identical_actions": 3,
                    "max_identical_intents": 0,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        # Call X, then intermediate Y, Z, W, then X again -> window never contains 3 consecutive X's
        for i in range(10):
            run.emit("tool.intent", {"tool": "search", "args": {"q": "aura"}})
            run.emit("tool.intent", {"tool": "step_a", "args": {"step": i}})
            run.emit("tool.intent", {"tool": "step_b", "args": {"step": i}})
            run.emit("tool.intent", {"tool": "step_c", "args": {"step": i}})

    alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(alerts) == 0


def test_burn_velocity_token_guard(aura_home):
    """FinOps token accumulator flags burn rate spikes."""
    ag = agent(
        "finops-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "burn_velocity_guard": True,
                    "max_cycle_token_waste": 800,
                    "max_identical_actions": 2,
                    "max_identical_intents": 0,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("tool.intent", {"tool": "rag_query", "args": {"q": "big context"}})
        run.emit("tool.result", {"tool": "rag_query", "tokens": 1000})

        run.emit("tool.intent", {"tool": "rag_query", "args": {"q": "big context"}})
        run.emit("tool.result", {"tool": "rag_query", "tokens": 1000})

    alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(alerts) == 1
    alert = alerts[0].payload
    assert alert.get("churn_tokens_estimate") == 1000
    assert alert.get("burn_rate_spike") is True


def test_cryptographic_spine_hash_capture(aura_home):
    """Ensure non-repudiable spine event hashes are attached to alerts."""
    ag = agent(
        "crypto-proof-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "max_identical_actions": 2,
                    "max_identical_intents": 0,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("tool.intent", {"tool": "echo", "args": {"msg": "hello"}})
        run.emit("tool.intent", {"tool": "echo", "args": {"msg": "hello"}})

    alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(alerts) == 1
    alert = alerts[0].payload
    assert "cycle_entry_hash" in alert
    assert "cycle_recurrence_hash" in alert
    assert len(alert["cycle_entry_hash"]) == 64
    assert len(alert["cycle_recurrence_hash"]) == 64


def test_escalation_playbook_trigger_on_break_alert(aura_home):
    """Verify that observer.alert triggers escalation playbooks (e.g. nudge, log)."""
    ag = agent(
        "esc-break-agent",
        observers=[
            {
                "preset": "break",
                "config": {"max_identical_actions": 2, "max_identical_intents": 0},
            }
        ],
        escalations=[
            {
                "on": "observer.alert",
                "actions": ["log", "nudge:Break loop — strategy shift required"],
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("tool.intent", {"tool": "stuck_tool", "args": {}})
        run.emit("tool.intent", {"tool": "stuck_tool", "args": {}})

    kinds = [e.kind for e in run._session.spine.stream()]
    assert "observer.alert" in kinds
    assert "escalation.fired" in kinds
    assert "membrane.nudge" in kinds


def test_break_preset_audit_report(aura_home):
    """Test preset: break audit report scorecard/findings synthesis."""
    ag = agent(
        "break-report-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "max_oscillation_cycles": 2,
                    "max_identical_actions": 5,
                    "max_identical_intents": 0,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("tool.intent", {"tool": "step_a", "args": {"id": 1}})
        run.emit("tool.intent", {"tool": "step_b", "args": {"id": 2}})
        run.emit("tool.intent", {"tool": "step_a", "args": {"id": 1}})
        run.emit("tool.intent", {"tool": "step_b", "args": {"id": 2}})

    conf = ConformanceEngine().summarize(run._session.spine, [])
    report = AuditReportBuilder().build(run._session.spine, conf)

    # Scorecard verification
    scorecard = report.scorecard
    assert "observers" in scorecard
    assert scorecard["observers"]["alerts"] == 1
    assert scorecard["observers"]["loop_cycles"] == 1

    # Findings verification
    codes = [f["code"] for f in report.findings]
    assert "COGNITIVE_CYCLE_DETECTED" in codes
    cycle_finding = next(f for f in report.findings if f["code"] == "COGNITIVE_CYCLE_DETECTED")
    assert cycle_finding["pattern"] == "OSCILLATION_CYCLE"
    assert "cycle_entry_hash" in cycle_finding
    assert "Alternating 2-state oscillation cycle detected" in cycle_finding["message"]
    assert any(
        "Alternating 2-state oscillation cycle detected" in r for r in report.recommendations
    )


def test_tier2_watchdog_mode(aura_home):
    """Test optional mode='watchdog' with pluggable watchdog_fn callback."""
    called = []

    def mock_watchdog(trajectory):
        called.append(trajectory)
        if len(trajectory) >= 2:
            return {
                "loop_detected": True,
                "remedial_directive": "Watchdog: Semantic goal stalling detected.",
            }
        return {"loop_detected": False}

    ag = agent(
        "watchdog-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "mode": "watchdog",
                    "watchdog_fn": mock_watchdog,
                    "max_identical_actions": 10,
                    "max_identical_intents": 0,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("tool.intent", {"tool": "probe_a", "args": {"target": "alpha"}})
        run.emit("tool.intent", {"tool": "probe_b", "args": {"target": "beta"}})

    assert len(called) >= 1
    alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(alerts) == 1
    alert = alerts[0].payload
    assert alert["pattern"] == "SEMANTIC_STAGNATION"
    assert "Watchdog: Semantic goal stalling detected." in alert["remedial_directive"]


def test_break_observer_action_pause(aura_home):
    """Test action='pause' appends break_pause rule and trips session state."""
    ag = agent(
        "pause-break-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "action": "pause",
                    "max_identical_actions": 2,
                    "max_identical_intents": 0,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("tool.intent", {"tool": "freeze_me", "args": {}})
        run.emit("tool.intent", {"tool": "freeze_me", "args": {}})

        assert run._session.state.get("_break_tripped") is True
        pause_rules = [r for r in run._session.rules if r.get("type") == "break_pause"]
        assert len(pause_rules) == 1
        assert pause_rules[0]["pattern"] == "ACTION_FIXATION"
        assert "BREAK:" in pause_rules[0]["remedial_directive"]


def test_break_observer_action_circuit_break(aura_home):
    """Test action='circuit_break' appends circuit_break rule and trips session state."""
    ag = agent(
        "trip-break-agent",
        observers=[
            {
                "preset": "break",
                "config": {
                    "action": "circuit_break",
                    "max_identical_actions": 2,
                    "max_identical_intents": 0,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("tool.intent", {"tool": "crash_tool", "args": {"mode": "fail"}})
        run.emit("tool.intent", {"tool": "crash_tool", "args": {"mode": "fail"}})

        assert run._session.state.get("_break_tripped") is True
        trip_rules = [r for r in run._session.rules if r.get("type") == "circuit_break"]
        assert len(trip_rules) == 1
        assert trip_rules[0]["tool"] == "crash_tool"


def test_break_observer_summary_metrics(aura_home):
    """Test BreakObserver summary() reports counts, patterns, and tripped state."""
    from aura.observers.presets.break_observer import BreakObserver

    ag = agent("summary-agent")
    with ag.session(export=False) as run:
        obs = BreakObserver(
            "test_break",
            run._session,
            {"max_identical_actions": 2, "max_identical_intents": 0},
        )
        obs.on_event({"kind": "tool.intent", "payload": {"tool": "loop_fn", "args": {}}})
        obs.on_event({"kind": "tool.intent", "payload": {"tool": "loop_fn", "args": {}}})

        s = obs.summary()
        assert s["alerts_emitted"] == 1
        assert s["cycles_detected"] == 1
        assert "ACTION_FIXATION" in s["patterns"]
        assert s["tripped"] is True
