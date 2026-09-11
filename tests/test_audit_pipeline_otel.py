"""Smoke test — audit_pipeline example asserts OTel export."""

from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import run_example


def test_audit_pipeline_emits_otel(aura_home):
    repo = Path(__file__).resolve().parents[1]
    result = run_example(repo / "examples" / "09-audit-pipeline" / "main.py", aura_home)
    assert result.returncode == 0, result.stderr or result.stdout
    json_block = result.stdout.split("session:")[0].strip()
    payload = json.loads(json_block)
    assert payload.get("otel_bytes", 0) > 0
    assert payload.get("hash_chain_valid") is True
