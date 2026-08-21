"""Smoke tests — example scripts run without error."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import run_example


@pytest.mark.parametrize(
    "main_py",
    sorted((Path(__file__).resolve().parents[1] / "examples").glob("*/main.py")),
)
def test_example_runs(main_py: Path, aura_home):
    result = run_example(main_py, aura_home)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "session" in result.stdout.lower()
