"""Smoke tests for examples/14-capability-broker/main.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "examples" / "14-capability-broker" / "main.py"


def _load_main():
    spec = importlib.util.spec_from_file_location("example_14_capability_broker", MAIN)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def example_14():
    return _load_main()


@pytest.mark.parametrize(
    "name,expect_key,expect_value",
    [
        ("allow_inject", "injected", True),
        ("deny_wrong_card", "blocked", True),
        ("low_audit", "executed", 1),
        ("missing_id", "blocked", True),
    ],
)
def test_example_14_scenarios(aura_home, example_14, name, expect_key, expect_value):
    result = getattr(example_14, f"scenario_{name}")()
    assert result[expect_key] == expect_value
    assert result["secret_on_spine"] is False
