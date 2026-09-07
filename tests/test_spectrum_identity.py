"""Verified identity policy via spectrum and session overrides (#73)."""

from __future__ import annotations

import json

import pytest

from pathlib import Path

from aura import agent, configure
from aura.core.audit_report import AuditReportBuilder
from aura.core.conformance import ConformanceEngine
from aura.core.spectrum_identity import resolve_verified_identity_required
from aura.core.spine import AuditSpine
from aura.identity.adapters.mock import MockIdentityAdapter
from aura.identity.errors import IdentityRequiredError
from tests.spectrum_helpers import spectrum_block


def test_level_default_high_requires_verified(aura_home):
    ag = agent("id-high-default", skills=["research"], spectrum={"level": "high"})
    policy = resolve_verified_identity_required(ag.profile)
    assert policy.required is True
    assert policy.source == "level_default:high"


def test_level_default_full_requires_verified(aura_home):
    ag = agent("id-full-default", skills=["research"], spectrum={"level": "full"})
    policy = resolve_verified_identity_required(ag.profile)
    assert policy.required is True
    assert policy.source == "level_default:full"


def test_spectrum_opt_out(aura_home):
    ag = agent(
        "id-opt-out",
        skills=["research"],
        spectrum={"level": "high", "identity_required": False},
    )
    policy = resolve_verified_identity_required(ag.profile)
    assert policy.required is False
    assert policy.source == "profile.spectrum"


def test_no_spectrum_block_no_requirement(aura_home):
    ag = agent("id-mid-default", skills=["research"])
    policy = resolve_verified_identity_required(ag.profile)
    assert policy.required is False
    assert policy.source == "none"


def test_high_blocks_without_verified_operator(aura_home):
    ag = agent("id-high-block", skills=["research"], spectrum={"level": "high"})
    with pytest.raises(IdentityRequiredError) as exc:
        with ag.session(export=False) as run:
            run.emit("turn.start", {})
    assert exc.value.reason == "no_verified_operator"
    assert "level_default:high" in (exc.value.source or "")


def test_high_allows_with_mock_adapter(aura_home):
    ag = agent("id-high-ok", skills=["research"], spectrum={"level": "high"})
    adapter = MockIdentityAdapter(subject="verified-operator")
    with ag.session(export=False, identity_adapter=adapter) as run:
        run.emit("turn.start", {})
    assert run.summary["identity"]["verified"] is True


def test_high_blocks_unverified_manual(aura_home):
    ag = agent(
        "id-high-manual",
        skills=["research"],
        spectrum={"level": "high"},
        ids={"operator": {"subject": "ops@corp.com", "verified": False, "method": "manual"}},
    )
    with pytest.raises(IdentityRequiredError) as exc:
        with ag.session(export=False) as run:
            run.emit("turn.start", {})
    assert exc.value.reason == "operator_not_verified"


def test_session_override_require_verified(aura_home):
    ag = agent("id-override", skills=["research"], spectrum=spectrum_block("low"))
    with pytest.raises(IdentityRequiredError):
        with ag.session(export=False, identity={"require_verified": True}) as run:
            run.emit("turn.start", {})


def test_session_open_carries_identity_policy(aura_home):
    ag = agent("id-open-meta", skills=["research"], spectrum={"level": "full"})
    adapter = MockIdentityAdapter(subject="meta-operator")
    with ag.session(export=False, identity_adapter=adapter) as run:
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
        spectrum = (open_evt.payload or {}).get("spectrum") or {}
    assert spectrum.get("verified_identity_required") is True
    assert spectrum.get("verified_identity_required_source") == "level_default:full"


def test_agent_show_includes_identity_policy(run_aura):
    create = run_aura("agent", "create", "id-show", "--ref", "acme/id-show")
    assert create.returncode == 0
    updated = run_aura(
        "agent",
        "set",
        "acme/id-show",
        "--spectrum-level",
        "high",
    )
    assert updated.returncode == 0
    show = run_aura("agent", "show", "acme/id-show")
    assert show.returncode == 0
    payload = json.loads(show.stdout)
    assert payload["effective_spectrum"]["verified_identity_required"] is True
    assert payload["effective_spectrum"]["verified_identity_required_source"] == "level_default:high"


def test_audit_finding_when_unverified_bound(aura_home, tmp_path: Path):
    """Defense-in-depth: audit flags unverified bind when policy required verified."""
    from aura.core.conformance import ConformanceEngine

    ag = agent("id-audit", skills=["research"], spectrum=spectrum_block("high"))
    with ag.session(
        export=False,
        operator={"subject": "inline", "verified": True, "method": "manual"},
    ) as run:
        run.emit("turn.start", {})
        lines: list[str] = []
        for event in run._session.spine.stream():
            row = event.to_dict()
            if row.get("kind") == "session.open":
                row["payload"]["spectrum"]["verified_identity_required"] = True
            if row.get("kind") == "identity.bound":
                row["payload"]["verified"] = False
            lines.append(json.dumps(row))
    log_path = tmp_path / "session.jsonl"
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    spine = AuditSpine.from_jsonl(log_path)
    conformance = ConformanceEngine().summarize(spine, [])
    report = AuditReportBuilder().build(spine, conformance)
    codes = [finding["code"] for finding in report.findings]
    assert "VERIFIED_IDENTITY_REQUIRED" in codes


def test_full_blocks_without_verified_operator(aura_home):
    ag = agent("id-full-block", skills=["research"], spectrum={"level": "full"})
    with pytest.raises(IdentityRequiredError) as exc:
        with ag.session(export=False) as run:
            run.emit("turn.start", {})
    assert exc.value.reason == "no_verified_operator"
    assert exc.value.source == "level_default:full"


def test_global_config_blocks_without_spectrum(aura_home):
    configure(identity_required=True)
    ag = agent("id-global-no-spec", skills=["research"])
    with pytest.raises(IdentityRequiredError) as exc:
        with ag.session(export=False) as run:
            run.emit("turn.start", {})
    assert exc.value.source == "global_config"
    configure(identity_required=False)


def test_low_and_mid_no_default_identity_requirement(aura_home):
    for level in ("low", "mid"):
        ag = agent(f"id-{level}", skills=["research"], spectrum={"level": level})
        policy = resolve_verified_identity_required(ag.profile)
        assert policy.required is False
        with ag.session(export=False) as run:
            run.emit("turn.start", {})
        assert run.summary.get("identity") is None


def test_cli_run_require_identity_blocks(run_aura, tmp_path: Path):
    script = tmp_path / "noop.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    create = run_aura("agent", "create", "run-id", "--ref", "acme/run-id")
    assert create.returncode == 0
    result = run_aura("run", "acme/run-id", str(script), "--require-identity")
    assert result.returncode != 0
    assert "verified" in (result.stderr or result.stdout).lower()


def test_config_show_verified_identity_note(run_aura):
    result = run_aura("config", "show")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "verified_identity_note" in payload
    assert payload["spectrum_levels"]["high"]["verified_identity_default"] is True


def test_global_identity_required_precedence(aura_home):
    configure(identity_required=True)
    ag = agent(
        "id-global",
        skills=["research"],
        spectrum={"level": "low", "identity_required": False},
    )
    policy = resolve_verified_identity_required(ag.profile)
    assert policy.required is False
    assert policy.source == "profile.spectrum"
    configure(identity_required=False)
