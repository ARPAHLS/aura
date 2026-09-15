"""Run the AURA capability-broker stress simulation (#48)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SIM = REPO / "scripts" / "aura_capability_stress_sim.py"


def test_capability_stress_simulation():
    result = subprocess.run(
        [sys.executable, str(SIM)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "ALL CAPABILITY SCENARIOS PASSED" in result.stdout
