"""Run the AURA + Skillware host stress simulation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SIM = REPO / "scripts" / "aura_host_stress_sim.py"


@pytest.mark.skillware
def test_host_stress_simulation(skillware_installed):
    result = subprocess.run(
        [sys.executable, str(SIM)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "ALL SCENARIOS PASSED" in result.stdout
