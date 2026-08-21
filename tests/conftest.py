"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from aura import configure


@pytest.fixture
def aura_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated AURA_HOME with configure() applied."""
    home = tmp_path / "aura_home"
    home.mkdir()
    monkeypatch.setenv("AURA_HOME", str(home))
    configure()
    return home


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    return proj


@pytest.fixture
def run_aura(aura_home: Path):
    """Run `python -m aura.cli.main` with isolated AURA_HOME."""

    def _run(
        *args: str,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["AURA_HOME"] = str(aura_home)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        return subprocess.run(
            [sys.executable, "-m", "aura.cli.main", *args],
            env=env,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=input_text,
        )

    return _run


def run_example(main_py: Path, aura_home: Path) -> subprocess.CompletedProcess[str]:
    """Run an example script with AURA_HOME set."""
    env = os.environ.copy()
    env["AURA_HOME"] = str(aura_home)
    return subprocess.run(
        [sys.executable, str(main_py)],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(main_py.parent),
        timeout=30,
    )


@pytest.fixture
def example_scripts() -> Sequence[Path]:
    root = Path(__file__).resolve().parents[1] / "examples"
    return sorted(root.glob("*/main.py"))
