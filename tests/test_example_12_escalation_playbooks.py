"""Smoke tests for examples/12-escalation-playbooks/main.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "examples" / "12-escalation-playbooks" / "main.py"


def _load_main():
    spec = importlib.util.spec_from_file_location("example_12_escalation_playbooks", MAIN)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def example_12():
    return _load_main()


@pytest.mark.parametrize(
    "name,expect_key,expect_value",
    [
        ("slo_miss_email", "has_escalation_email", True),
        ("drift_nudge", "has_nudge", True),
        ("break_alert", "escalation_alert_notes_min", 1),
        ("constraint_nudge", "has_violation", True),
        ("drift_pause_approve", "tool_blocked_pending_approval", True),
        ("custom_handler", "handler_invocations", [{"kind": "slo.missed"}]),
    ],
)
def test_example_12_scenarios(aura_home, example_12, name, expect_key, expect_value):
    result = example_12.SCENARIOS[name]()
    if expect_key == "handler_invocations":
        assert result["handler_invocations"]
        assert result["handler_invocations"][0]["kind"] == "slo.missed"
    elif expect_key == "escalation_alert_notes_min":
        assert result["escalation_alert_notes"] >= expect_value
    else:
        assert result[expect_key] == expect_value
    assert result["escalation_fired"] >= 1
    assert "ESCALATION_FIRED" in result["finding_codes"]
