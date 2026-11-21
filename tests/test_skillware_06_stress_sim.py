"""Run the AURA + Skillware 0.6.2+ audit bridge, FinOps, Manifest v2, and async stress sim."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
SIM = REPO / "scripts" / "aura_skillware_06_stress_sim.py"


def test_skillware_06_stress_simulation():
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
