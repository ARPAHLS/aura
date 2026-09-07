"""Run coat flow report script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "scripts" / "aura_coat_flow_report.py"


def test_coat_flow_report_runs():
    result = subprocess.run(
        [sys.executable, str(REPORT), "--json"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["flows_run"] >= 2
    coats = {f["coat"] for f in payload["flows"]}
    assert "loose" in coats


@pytest.mark.skillware
def test_coat_flow_report_skillware_coats(skillware_installed):
    result = subprocess.run(
        [sys.executable, str(REPORT), "--json"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["skillware_installed"] is True
    assert payload["flows_run"] == 8
    scenarios = {f["scenario"] for f in payload["flows"]}
    assert "high_skill_allowlist" in scenarios
    assert "high_services_level_defaults" in scenarios
    assert "mid_spectrum_services_limit" in scenarios
    assert "full_sequencer_bind" in scenarios
    for flow in payload["flows"]:
        if flow["scenario"] == "high_services_level_defaults":
            activation = flow["session"].get("services_activation") or {}
            assert activation.get("activated") == ["monitor"]
