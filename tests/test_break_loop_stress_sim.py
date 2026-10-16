"""Run the AURA break observer trajectory cycle governance stress simulation (#93)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SIM = REPO / "scripts" / "aura_break_loop_stress_sim.py"


def test_break_loop_stress_simulation():
    result = subprocess.run(
        [sys.executable, str(SIM)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "ALL SCENARIOS PASSED SUCCESSFULLY" in result.stdout
