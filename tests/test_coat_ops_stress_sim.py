"""Run the AURA-native coat ops stress simulation (#49)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
SIM = REPO / "scripts" / "aura_coat_ops_stress_sim.py"


def test_coat_ops_stress_simulation():
    result = subprocess.run(
        [sys.executable, str(SIM)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "ALL COAT OPS SCENARIOS PASSED" in result.stdout
