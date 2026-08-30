"""Operator identity adapter tests."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from aura import agent, configure
from aura.exporters.jsonl import build_session_summary
from aura.exporters.otel import events_to_spans
from aura.identity.adapters.mock import MockIdentityAdapter
from aura.identity.errors import IdentityRequiredError
from aura.identity.redaction import redact_summary


def _jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.sig"


def test_no_identity_unchanged(aura_home: Path):
    ag = agent("id-none")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
    assert run.summary is not None
    assert run.summary.get("identity") is None
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "identity.bound" not in kinds


def test_mock_adapter_binds_and_emits(aura_home: Path):
    configure(identity={"adapter": "mock", "subject": "ci-operator"})
    ag = agent("id-mock")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
    assert run.summary["identity"]["subject"] == "ci-operator"
    assert run.summary["identity"]["verified"] is True
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "identity.bound" in kinds
    trailer = run._session.agent_ids_trailer()
    assert trailer["ids"]["operator"]["subject"] == "ci-operator"


def test_manual_operator_from_profile(aura_home: Path):
    ag = agent(
        "id-manual",
        ids={"operator": {"subject": "ops@corp.com", "verified": False, "method": "manual"}},
    )
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
    assert run.summary["identity"]["subject"] == "ops@corp.com"
    assert run.summary["identity"]["verified"] is False


def test_session_operator_override(aura_home: Path):
    ag = agent("id-override")
    with ag.session(
        export=False,
        operator={"subject": "session-operator", "verified": True, "method": "manual"},
    ) as run:
        run.emit("turn.start", {})
    assert run.summary["identity"]["subject"] == "session-operator"


def test_identity_required_raises(aura_home: Path):
    configure(identity_required=True)
    ag = agent("id-required")
    with pytest.raises(IdentityRequiredError):
        with ag.session(export=False) as run:
            run.emit("turn.start", {})
    configure(identity_required=False)


def test_programmatic_adapter(aura_home: Path):
    ag = agent("id-adapter")
    adapter = MockIdentityAdapter(subject="sdk-operator", email="sdk@example.com")
    with ag.session(export=False, identity_adapter=adapter) as run:
        run.emit("turn.start", {})
    assert run.summary["identity"]["subject"] == "sdk-operator"


def test_oidc_unverified_decode(aura_home: Path):
    token = _jwt({"sub": "oidc-user-1", "email": "oidc@corp.com", "name": "OIDC User"})
    configure(identity={"adapter": "oidc", "token": token, "verify_signature": False})
    ag = agent("id-oidc")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
    assert run.summary["identity"]["subject"] == "oidc-user-1"
    assert run.summary["identity"]["method"] == "oidc"


def test_export_redacts_email_by_default(aura_home: Path):
    configure(identity={"adapter": "mock", "subject": "redact-me", "email": "secret@corp.com"})
    ag = agent("id-redact")
    with ag.session() as run:
        run.emit("turn.start", {})
    summary = json.loads(Path(run.exports["summary"]).read_text(encoding="utf-8"))
    operator = summary["agent_ids"]["ids"]["operator"]
    assert operator["subject"] == "redact-me"
    assert operator.get("email") is None
    assert operator.get("subject_hash")


def test_export_pii_includes_email(aura_home: Path):
    configure(
        identity={"adapter": "mock", "subject": "pii-me", "email": "visible@corp.com"},
        identity_export_pii=True,
    )
    ag = agent("id-pii")
    with ag.session() as run:
        run.emit("turn.start", {})
    summary = json.loads(Path(run.exports["summary"]).read_text(encoding="utf-8"))
    assert summary["agent_ids"]["ids"]["operator"]["email"] == "visible@corp.com"


def test_agent_ids_on_every_event(aura_home: Path):
    configure(identity={"adapter": "mock", "subject": "trail-operator"})
    ag = agent("id-trailer")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
    for event in run._session.spine.stream():
        if event.kind in {"membrane.ingress", "session.open", "identity.bound", "turn.start"}:
            assert event.agent_ids["ids"]["operator"]["subject"] == "trail-operator"


def test_otel_promotes_operator_attributes(aura_home: Path):
    configure(identity={"adapter": "mock", "subject": "otel-operator"})
    ag = agent("id-otel")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
    events = [e.to_dict() for e in run._session.spine.stream()]
    spans = events_to_spans(events)
    attrs = spans[-1]["attributes"]
    assert attrs["aura.operator.subject"] == "otel-operator"
    assert attrs["aura.operator.method"] == "mock"


def test_approve_defaults_principal_to_operator(aura_home: Path):
    from aura.core.constraints import ApprovalRequired

    configure(identity={"adapter": "mock", "subject": "approver-operator"})
    ag = agent("id-approve", rules=[{"type": "confirm_before", "tools": ["send"]}])
    with ag.session(export=False) as run:
        with pytest.raises(ApprovalRequired) as exc:
            run.emit("tool.call", {"tool": "send"})
        run.approve(exc.value.request_id)
    approved = [e for e in run._session.spine.stream() if e.kind == "constraint.approved"]
    assert approved[-1].payload["principal"] == "approver-operator"


def test_profile_types_identity_config(aura_home: Path):
    ag = agent(
        "id-types",
        types=[
            {
                "role": "identity",
                "type_id": "arpa.identity.mock",
                "config": {"adapter": "mock", "subject": "types-operator"},
            }
        ],
    )
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
    assert run.summary["identity"]["subject"] == "types-operator"


def test_redact_summary_helper():
    summary = {
        "agent_ids": {
            "ids": {
                "operator": {
                    "subject": "x",
                    "email": "hide@corp.com",
                    "subject_hash": "abc",
                }
            }
        }
    }
    redacted = redact_summary(summary)
    assert redacted["agent_ids"]["ids"]["operator"]["email"] is None


def test_build_session_summary_identity_field(aura_home: Path):
    ag = agent("id-summary")
    with ag.session(
        export=False,
        operator={"subject": "inline", "verified": False},
    ) as run:
        run.emit("turn.start", {})
    raw = build_session_summary(run._session)
    assert raw["identity"]["subject"] == "inline"
