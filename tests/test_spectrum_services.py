"""Spectrum services[] runtime activation at session open (#77)."""

from __future__ import annotations

import json

from aura import agent
from aura.core.spectrum_services import (
    attach_spectrum_services,
    merge_spectrum_update,
    resolve_services_to_wire,
)
from aura.observers.presets.limit import LimitObserver
from aura.observers.presets.monitor import MonitorObserver


def test_no_spectrum_block_skips_wiring(aura_home):
    ag = agent("plain", skills=["research"])
    with ag.session(export=False) as run:
        assert run._session._observers == []
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
        activation = (open_evt.payload or {}).get("spectrum", {}).get("services_activation") or {}
    assert activation.get("note") == "no spectrum block — service wiring skipped"
    assert activation.get("activated") == []


def test_level_high_defaults_monitor(aura_home):
    ag = agent("high-default", skills=["research"], spectrum={"level": "high"})
    with ag.session(export=False) as run:
        monitors = [o for o in run._session._observers if isinstance(o, MonitorObserver)]
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
        activation = (open_evt.payload or {}).get("spectrum", {}).get("services_activation") or {}
    assert len(monitors) == 1
    assert monitors[0].observer_id == "spectrum-monitor"
    assert activation["activated"] == ["monitor"]


def test_level_full_defaults_monitor_and_break(aura_home):
    ag = agent("full-default", skills=["research"], spectrum={"level": "full"})
    with ag.session(export=False) as run:
        ids = {getattr(o, "observer_id", "") for o in run._session._observers}
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
        activation = (open_evt.payload or {}).get("spectrum", {}).get("services_activation") or {}
    assert "spectrum-monitor" in ids
    assert "spectrum-break" in ids
    assert set(activation["activated"]) == {"monitor", "break"}


def test_level_low_wires_nothing_extra(aura_home):
    ag = agent("low-only", skills=["research"], spectrum={"level": "low"})
    with ag.session(export=False) as run:
        assert run._session._observers == []
        activation = resolve_services_to_wire(run._session.profile)
    assert activation == []


def test_explicit_services_list(aura_home):
    ag = agent(
        "explicit-svc",
        skills=["research"],
        spectrum={"level": "low", "services": ["limit", "audit", "goal_drift"]},
    )
    with ag.session(export=False) as run:
        ids = {getattr(o, "observer_id", "") for o in run._session._observers}
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
        activation = (open_evt.payload or {}).get("spectrum", {}).get("services_activation") or {}
    assert "spectrum-limit" in ids
    assert "spectrum-goal_drift" in ids
    assert "spectrum-monitor" not in ids
    assert set(activation["activated"]) == {"limit", "goal_drift"}
    assert activation["audit"] == "declared_implicit"


def test_explicit_observer_wins_over_service(aura_home):
    ag = agent(
        "dup-monitor",
        skills=["research"],
        spectrum={"level": "high", "services": ["monitor"]},
        observers=[{"preset": "monitor", "id": "profile-monitor"}],
    )
    with ag.session(export=False) as run:
        monitors = [o for o in run._session._observers if isinstance(o, MonitorObserver)]
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
        activation = (open_evt.payload or {}).get("spectrum", {}).get("services_activation") or {}
    assert len(monitors) == 1
    assert monitors[0].observer_id == "profile-monitor"
    assert activation["skipped_explicit"] == ["monitor"]
    assert activation["activated"] == []


def test_unknown_service_emits_note_not_alert(aura_home):
    ag = agent(
        "unknown-svc",
        skills=["research"],
        spectrum={"level": "mid", "services": ["not_a_real_service"]},
    )
    with ag.session(export=False) as run:
        kinds = [e.kind for e in run._session.spine.stream()]
        notes = [
            e
            for e in run._session.spine.stream()
            if e.kind == "observer.note"
            and (e.payload or {}).get("type") == "unknown_spectrum_service"
        ]
    assert "observer.alert" not in kinds
    assert len(notes) == 1
    assert notes[0].payload.get("service") == "not_a_real_service"


def test_unknown_service_strict_emits_alert(aura_home):
    ag = agent(
        "strict-unknown",
        skills=["research"],
        spectrum={"level": "mid", "services": ["bogus"], "strict_services": True},
    )
    with ag.session(export=False) as run:
        alerts = [
            e
            for e in run._session.spine.stream()
            if e.kind == "observer.alert"
            and (e.payload or {}).get("type") == "unknown_spectrum_service"
        ]
    assert len(alerts) == 1


def test_service_config_merge(aura_home):
    ag = agent(
        "limit-config",
        skills=["research"],
        spectrum={
            "level": "mid",
            "services": ["limit"],
            "service_config": {"limit": {"max_tool_calls_per_minute": 2}},
        },
    )
    with ag.session(export=False) as run:
        limits = [o for o in run._session._observers if isinstance(o, LimitObserver)]
        run.emit("tool.call", {"tool": "a"})
        run.emit("tool.call", {"tool": "b"})
        run.emit("tool.call", {"tool": "c"})
        alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert len(limits) == 1
    rate_alerts = [e for e in alerts if (e.payload or {}).get("type") == "rate_limit_exceeded"]
    assert len(rate_alerts) >= 1


def test_merge_spectrum_update_preserves_services():
    merged = merge_spectrum_update(
        {"level": "high", "services": ["monitor", "audit"]},
        {"level": "full"},
    )
    assert merged["level"] == "full"
    assert merged["services"] == ["monitor", "audit"]

    merged_cfg = merge_spectrum_update(
        {"service_config": {"limit": {"max_tool_calls_per_minute": 30}}},
        {"service_config": {"limit": {"max_tokens_per_step": 1000}}},
    )
    assert merged_cfg["service_config"]["limit"]["max_tool_calls_per_minute"] == 30
    assert merged_cfg["service_config"]["limit"]["max_tokens_per_step"] == 1000


def test_limit_single_call_no_breach(aura_home):
    ag = agent(
        "limit-single",
        observers=[
            {
                "preset": "limit",
                "id": "budget",
                "config": {"max_tool_calls_per_minute": 5, "max_tokens_per_step": 1000},
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("tool.call", {"tool": "research", "tokens": 100})
        notes = [e for e in run._session.spine.stream() if e.kind == "observer.note"]
        alerts = [e for e in run._session.spine.stream() if e.kind == "observer.alert"]
    assert not alerts
    assert not notes


def test_limit_warning_then_alert(aura_home):
    ag = agent(
        "limit-warn",
        observers=[
            {
                "preset": "limit",
                "id": "budget",
                "config": {
                    "max_tool_calls_per_minute": 2,
                    "max_tokens_per_step": 100,
                    "warn_ratio": 0.5,
                },
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("tool.call", {"tool": "a", "tokens": 60})
        run.emit("tool.call", {"tool": "b", "tokens": 60})
        run.emit("tool.call", {"tool": "c", "tokens": 60})
        note_types = [
            (e.payload or {}).get("type")
            for e in run._session.spine.stream()
            if e.kind == "observer.note"
        ]
        alert_types = [
            (e.payload or {}).get("type")
            for e in run._session.spine.stream()
            if e.kind == "observer.alert"
        ]
    assert "rate_limit_warning" in note_types or "token_budget_warning" in note_types
    assert "rate_limit_exceeded" in alert_types or "token_budget_exceeded" in alert_types


def test_cli_agent_set_spectrum_merge(run_aura):
    create = run_aura("agent", "create", "merge-bot", "--ref", "acme/merge")
    assert create.returncode == 0

    first = run_aura(
        "agent",
        "set",
        "acme/merge",
        "--spectrum-level",
        "high",
        "--spectrum-service",
        "monitor",
        "--spectrum-service",
        "audit",
    )
    assert first.returncode == 0
    profile = json.loads(first.stdout)
    assert profile["spectrum"]["services"] == ["monitor", "audit"]

    second = run_aura("agent", "set", "acme/merge", "--spectrum-level", "full")
    assert second.returncode == 0
    profile = json.loads(second.stdout)
    assert profile["spectrum"]["level"] == "full"
    assert profile["spectrum"]["services"] == ["monitor", "audit"]


def test_attach_spectrum_services_unit(aura_home):
    ag = agent("unit", skills=["research"], spectrum={"level": "high"})
    with ag.session(export=False) as run:
        before = len(run._session._observers)
        summary = attach_spectrum_services(run._session)
    assert before >= 1
    assert summary["activated"] == []
