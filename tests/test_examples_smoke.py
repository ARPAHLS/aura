"""Smoke tests — numbered example folders run without error."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import run_example

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"

# Keep in sync with examples/README.md (learning path 01–12 + supplementary 13).
EXPECTED_EXAMPLE_DIRS = (
    "01-minimal-loop",
    "02-guarded-tools",
    "03-task-mode",
    "04-sequencer-pipeline",
    "05-skillware-skill-types",
    "06-skillware-sequencer-chain",
    "07-observer-presets",
    "08-emit-only-loop",
    "09-audit-pipeline",
    "10-observer-metrics-snapshot",
    "11-scheduled-agent-slo",
    "12-escalation-playbooks",
    "13-operator-identity",
)


def _example_main_paths() -> list[Path]:
    return [EXAMPLES_DIR / name / "main.py" for name in EXPECTED_EXAMPLE_DIRS]


def test_example_catalog_matches_readme():
    for name in EXPECTED_EXAMPLE_DIRS:
        main_py = EXAMPLES_DIR / name / "main.py"
        assert main_py.is_file(), f"missing {main_py.relative_to(EXAMPLES_DIR.parent)}"
    extra = {
        p.parent.name
        for p in EXAMPLES_DIR.glob("*/main.py")
        if p.parent.name not in EXPECTED_EXAMPLE_DIRS
    }
    assert not extra, f"unexpected example folders: {sorted(extra)}"


@pytest.mark.parametrize("main_py", _example_main_paths())
def test_example_runs(main_py: Path, aura_home: Path):
    result = run_example(main_py, aura_home)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "session" in result.stdout.lower()
