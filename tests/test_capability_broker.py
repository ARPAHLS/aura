"""Capability broker, scope checks, secret inject, and spine redaction (#48)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aura import (
    CapabilityConfigError,
    EnvSecretBroker,
    MapSecretBroker,
    SecretNotFoundError,
    agent,
)
from aura.core.audit_report import AuditReportBuilder
from aura.core.capabilities import parse_capabilities
from aura.core.conformance import ConformanceEngine
from aura.core.constraints import ConstraintViolation
from aura.core.payload_redaction import REDACTED
from aura.core.secrets import CallableSecretBroker, ChainSecretBroker
from aura.hosts import MockSkill, SkillwareHost
from aura.membrane.egress import guarded_tool_call
from tests.spectrum_helpers import spectrum_block

SECRET = "tok_live_shop_x_card_y_99"
CAP_SHOP = {
    "id": "shop-x-milk",
    "tool": "payment",
    "allowed": {"merchant": "shop-x", "item": "milk", "card": "Y"},
    "secret": {"ref": "env:AURA_CAP_SHOP_X_CARD_Y"},
}


def _broker() -> MapSecretBroker:
    return MapSecretBroker({"env:AURA_CAP_SHOP_X_CARD_Y": SECRET})


def _agent(name: str, **kwargs):
    kwargs.setdefault("capabilities", [CAP_SHOP])
    kwargs.setdefault("spectrum", {"level": "mid", "services": ["audit"]})
    return agent(name, **kwargs)


def _spine_text(run) -> str:
    return json.dumps([e.to_dict() for e in run._session.spine.stream()])


def _kinds(run) -> list[str]:
    return [e.kind for e in run._session.spine.stream()]


def _findings(run) -> list[dict]:
    conf = ConformanceEngine().summarize(run._session.spine, run._session.declared_rules)
    report = AuditReportBuilder().build(run._session.spine, conf)
    return report.findings


def test_parse_rejects_plaintext_secret():
    with pytest.raises(CapabilityConfigError, match="ref only"):
        parse_capabilities(
            [{"id": "x", "tool": "payment", "secret": {"value": "sk-live-please-no"}}],
            strict=True,
        )


def test_parse_accepts_long_scope_labels():
    caps = parse_capabilities(
        [
            {
                "id": "gh-ledger-read",
                "tool": "github.api",
                "allowed": {
                    "repo": "acme/private-ledger",
                    "item": "organic whole milk",
                },
                "secret": {"ref": "env:AURA_GH_TOKEN"},
                "inject_as": "api_key",
            }
        ],
        strict=True,
    )
    assert caps[0].allowed["repo"] == "acme/private-ledger"
    assert caps[0].inject_as == "api_key"


def test_parse_rejects_tokenish_allowed_value():
    with pytest.raises(CapabilityConfigError, match="plaintext secret"):
        parse_capabilities(
            [
                {
                    "id": "x",
                    "tool": "payment",
                    "allowed": {"card": "tok_live_shop_x_card_y_99"},
                }
            ],
            strict=True,
        )


def test_parse_rejects_duplicate_ids():
    with pytest.raises(CapabilityConfigError, match="duplicate"):
        parse_capabilities(
            [
                {"id": "x", "tool": "payment"},
                {"id": "x", "tool": "refund"},
            ],
            strict=True,
        )


def test_registry_rejects_plaintext(aura_home: Path):
    from aura.agents.registry import AgentRegistry

    with pytest.raises(CapabilityConfigError):
        AgentRegistry().create(
            name="bad-caps",
            capabilities=[{"id": "x", "secret": {"token": "abc"}}],
        )


def test_profile_roundtrip_has_ref_not_value(aura_home: Path):
    ag = _agent("cap-roundtrip")
    dumped = json.dumps(ag.profile.to_dict())
    assert "env:AURA_CAP_SHOP_X_CARD_Y" in dumped
    assert SECRET not in dumped
    assert "tok_live" not in dumped


def test_allow_matching_scope_injects_and_redacts(aura_home: Path):
    captured: dict = {}

    def pay(args):
        captured.update(args)
        return {"ok": True, "echo": args.get("token")}

    ag = _agent("cap-allow")
    with ag.session(export=False, secret_broker=_broker()) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
        result = host.execute(
            "pay",
            "payment",
            {
                "capability_id": "shop-x-milk",
                "merchant": "shop-x",
                "item": "milk",
                "card": "Y",
            },
        )
    assert result["ok"] is True
    assert captured["token"] == SECRET
    text = _spine_text(run)
    assert SECRET not in text
    assert "capability.injected" in _kinds(run)
    assert REDACTED in text or "shop-x-milk" in text
    for event in run._session.spine.stream():
        blob = json.dumps(event.payload)
        assert SECRET not in blob


def test_github_style_inject_as_api_key(aura_home: Path):
    gh_secret = "ghp_ledger_read_not_a_payment_token"
    captured: dict = {}

    def github_api(args):
        captured.update(args)
        return {"ok": True}

    ag = agent(
        "cap-github",
        capabilities=[
            {
                "id": "gh-ledger-read",
                "tool": "github.api",
                "allowed": {"repo": "acme/private-ledger"},
                "secret": {"ref": "env:AURA_GH_TOKEN"},
                "inject_as": "api_key",
            }
        ],
        spectrum={"level": "mid", "services": ["audit"]},
    )
    with ag.session(
        export=False,
        secret_broker=MapSecretBroker({"env:AURA_GH_TOKEN": gh_secret}),
    ) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("gh", {"github.api": github_api}))
        host.execute(
            "gh",
            "github.api",
            {"capability_id": "gh-ledger-read", "repo": "acme/private-ledger"},
        )
    assert captured["api_key"] == gh_secret
    assert "token" not in captured
    assert gh_secret not in _spine_text(run)


def test_deny_wrong_card_mid_blocks(aura_home: Path):
    executed = {"n": 0}

    def pay(args):
        executed["n"] += 1
        return {"ok": True}

    ag = _agent("cap-deny-card")
    with ag.session(export=False, secret_broker=_broker()) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
        with pytest.raises(ConstraintViolation, match="scope mismatch"):
            host.execute(
                "pay",
                "payment",
                {
                    "capability_id": "shop-x-milk",
                    "merchant": "shop-x",
                    "item": "milk",
                    "card": "Z",
                },
            )
    assert executed["n"] == 0
    assert "constraint.violated" in _kinds(run)
    codes = {f.get("code") for f in _findings(run)}
    assert "CAPABILITY_DENIED" in codes


def test_missing_capability_id_on_gated_tool_denied(aura_home: Path):
    ag = _agent("cap-missing-id")
    with ag.session(export=False, secret_broker=_broker()) as run:
        with pytest.raises(ConstraintViolation, match="Capability id required"):
            run.emit("tool.call", {"tool": "payment", "args": {"item": "milk"}})


def test_unknown_capability_id_denied(aura_home: Path):
    ag = _agent("cap-unknown")
    with ag.session(export=False, secret_broker=_broker()) as run:
        with pytest.raises(ConstraintViolation, match="Unknown capability"):
            run.emit(
                "tool.call",
                {"tool": "payment", "capability_id": "nope", "args": {"card": "Y"}},
            )


def test_low_audit_only_still_runs_without_inject(aura_home: Path):
    captured: dict = {}

    def pay(args):
        captured.update(args)
        return {"ran": True}

    ag = _agent("cap-low-audit", spectrum={"level": "low", "services": ["audit"]})
    with ag.session(export=False, secret_broker=_broker()) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
        result = host.execute(
            "pay",
            "payment",
            {
                "capability_id": "shop-x-milk",
                "merchant": "shop-x",
                "item": "milk",
                "card": "Z",
            },
        )
    assert result["ran"] is True
    assert "token" not in captured
    assert "constraint.violated" in _kinds(run)
    codes = {f.get("code") for f in _findings(run)}
    assert "CAPABILITY_AUDIT" in codes
    assert "CAPABILITY_DENIED" not in codes


def test_low_matching_scope_still_injects(aura_home: Path):
    captured: dict = {}

    def pay(args):
        captured.update(args)
        return {"ok": True}

    ag = _agent("cap-low-ok", spectrum={"level": "low", "services": ["audit"]})
    with ag.session(export=False, secret_broker=_broker()) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
        host.execute(
            "pay",
            "payment",
            {
                "capability_id": "shop-x-milk",
                "merchant": "shop-x",
                "item": "milk",
                "card": "Y",
            },
        )
    assert captured["token"] == SECRET
    assert SECRET not in _spine_text(run)


def test_agent_supplied_token_never_used(aura_home: Path):
    captured: dict = {}

    def pay(args):
        captured.update(args)
        return args

    ag = _agent("cap-bypass-token")
    with ag.session(export=False, secret_broker=_broker()) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
        host.execute(
            "pay",
            "payment",
            {
                "capability_id": "shop-x-milk",
                "merchant": "shop-x",
                "item": "milk",
                "card": "Y",
                "token": "attacker-supplied-token-value",
            },
        )
    assert captured["token"] == SECRET
    text = _spine_text(run)
    assert "attacker-supplied-token-value" not in text
    assert SECRET not in text


def test_result_echo_secret_is_redacted(aura_home: Path):
    def pay(args):
        return {"receipt": f"charged with {args['token']}"}

    ag = _agent("cap-result-leak")
    with ag.session(export=True, secret_broker=_broker()) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
        result = host.execute(
            "pay",
            "payment",
            {
                "capability_id": "shop-x-milk",
                "merchant": "shop-x",
                "item": "milk",
                "card": "Y",
            },
        )
    assert SECRET in result["receipt"]
    text = Path(run.exports["jsonl"]).read_text(encoding="utf-8")
    assert SECRET not in text
    otel = Path(run.exports["otel"]).read_text(encoding="utf-8")
    assert SECRET not in otel


def test_ungated_tool_still_works(aura_home: Path):
    ag = _agent("cap-ungated")
    with ag.session(export=False, secret_broker=_broker()) as run:
        run.emit("tool.call", {"tool": "search.web", "query": "tires"})
    assert "tool.call" in _kinds(run)
    assert "constraint.violated" not in _kinds(run)


def test_numeric_and_wildcard_allowed(aura_home: Path):
    caps = [
        {
            "id": "qty-any",
            "tool": "order",
            "allowed": {"item": "milk", "qty": "*"},
        }
    ]
    ag = agent(
        "cap-wild",
        capabilities=caps,
        spectrum={"level": "mid", "services": ["audit"]},
    )
    with ag.session(export=False) as run:
        run.emit(
            "tool.call",
            {"tool": "order", "capability_id": "qty-any", "args": {"item": "milk", "qty": 3}},
        )
        run.emit(
            "tool.call",
            {
                "tool": "order",
                "capability_id": "qty-any",
                "args": {"item": "milk", "qty": "3"},
            },
        )


def test_nested_allowed_and_list(aura_home: Path):
    caps = [
        {
            "id": "nested",
            "tool": "payment",
            "allowed": {"merchant.name": "shop-x", "card": ["Y", "Y2"]},
        }
    ]
    ag = agent("cap-nested", capabilities=caps, spectrum={"level": "mid"})
    with ag.session(export=False) as run:
        run.emit(
            "tool.call",
            {
                "tool": "payment",
                "capability_id": "nested",
                "args": {"merchant": {"name": "shop-x"}, "card": "Y2"},
            },
        )
        with pytest.raises(ConstraintViolation):
            run.emit(
                "tool.call",
                {
                    "tool": "payment",
                    "capability_id": "nested",
                    "args": {"merchant": {"name": "other"}, "card": "Y"},
                },
            )


def test_strict_args_rejects_extra(aura_home: Path):
    caps = [
        {
            "id": "strict",
            "tool": "payment",
            "allowed": {"item": "milk"},
            "strict_args": True,
        }
    ]
    ag = agent("cap-strict", capabilities=caps, spectrum={"level": "mid"})
    with ag.session(export=False) as run:
        with pytest.raises(ConstraintViolation, match="extra args"):
            run.emit(
                "tool.call",
                {
                    "tool": "payment",
                    "capability_id": "strict",
                    "args": {"item": "milk", "note": "smuggle"},
                },
            )


def test_conflicting_capability_ids_denied(aura_home: Path):
    ag = _agent("cap-conflict")
    with ag.session(export=False, secret_broker=_broker()) as run:
        with pytest.raises(ConstraintViolation, match="conflicting"):
            run.emit(
                "tool.call",
                {
                    "tool": "payment",
                    "capability_id": "shop-x-milk",
                    "args": {"capability_id": "other", "item": "milk", "card": "Y"},
                },
            )


def test_tool_mismatch_denied(aura_home: Path):
    ag = _agent("cap-tool-mismatch")
    with ag.session(export=False, secret_broker=_broker()) as run:
        with pytest.raises(ConstraintViolation, match="bound to tool"):
            run.emit(
                "tool.call",
                {
                    "tool": "refund",
                    "capability_id": "shop-x-milk",
                    "args": {"merchant": "shop-x", "item": "milk", "card": "Y"},
                },
            )


def test_high_bind_includes_capability_tool(aura_home: Path):
    ag = agent(
        "cap-high",
        capabilities=[CAP_SHOP],
        spectrum=spectrum_block("high"),
    )
    with ag.session(export=False, secret_broker=_broker()) as run:
        run.emit(
            "tool.call",
            {
                "tool": "payment",
                "capability_id": "shop-x-milk",
                "args": {"merchant": "shop-x", "item": "milk", "card": "Y"},
            },
        )


def test_full_still_requires_step_id(aura_home: Path):
    ag = agent(
        "cap-full",
        capabilities=[CAP_SHOP],
        spectrum=spectrum_block("full"),
        sequencer={"steps": [{"id": "pay", "type": "skill", "ref": "payment"}]},
    )
    with ag.session(export=False, secret_broker=_broker()) as run:
        with pytest.raises(ConstraintViolation, match="sequencer"):
            run.emit(
                "tool.call",
                {
                    "tool": "payment",
                    "capability_id": "shop-x-milk",
                    "args": {"merchant": "shop-x", "item": "milk", "card": "Y"},
                },
            )
        run.emit(
            "tool.call",
            {
                "tool": "payment",
                "capability_id": "shop-x-milk",
                "step_id": "pay",
                "args": {"merchant": "shop-x", "item": "milk", "card": "Y"},
            },
            step_id="pay",
        )


def test_secret_broker_unresolved_emits_error(aura_home: Path):
    ag = _agent("cap-missing-env")
    with ag.session(export=False, secret_broker=MapSecretBroker({})) as run:
        with pytest.raises(SecretNotFoundError):
            guarded_tool_call(
                run._session,
                tool="payment",
                skill_id="pay",
                args={
                    "capability_id": "shop-x-milk",
                    "merchant": "shop-x",
                    "item": "milk",
                    "card": "Y",
                },
                execute=lambda live: live,
            )
    assert "tool.error" in _kinds(run)
    codes = {f.get("code") for f in _findings(run)}
    assert "SECRET_BROKER_ERROR" in codes


def test_env_and_callable_and_chain_brokers(aura_home: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AURA_CAP_SHOP_X_CARD_Y", SECRET)
    captured: dict = {}

    def pay(args):
        captured["env"] = args.get("token")
        return {"ok": True}

    ag = _agent("cap-env")
    with ag.session(export=False, secret_broker=EnvSecretBroker()) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
        host.execute(
            "pay",
            "payment",
            {
                "capability_id": "shop-x-milk",
                "merchant": "shop-x",
                "item": "milk",
                "card": "Y",
            },
        )
    assert captured["env"] == SECRET

    callable_broker = CallableSecretBroker(lambda ref: SECRET if "SHOP" in ref else None)
    captured.clear()
    ag2 = _agent("cap-callable")
    with ag2.session(export=False, secret_broker=callable_broker) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
        host.execute(
            "pay",
            "payment",
            {
                "capability_id": "shop-x-milk",
                "merchant": "shop-x",
                "item": "milk",
                "card": "Y",
            },
        )
    assert captured["env"] == SECRET

    chain = ChainSecretBroker([MapSecretBroker({}), EnvSecretBroker()])
    captured.clear()
    ag3 = _agent("cap-chain")
    with ag3.session(export=False, secret_broker=chain) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
        host.execute(
            "pay",
            "payment",
            {
                "capability_id": "shop-x-milk",
                "merchant": "shop-x",
                "item": "milk",
                "card": "Y",
            },
        )
    assert captured["env"] == SECRET


def test_escalation_fires_on_capability_deny(aura_home: Path):
    ag = agent(
        "cap-esc",
        capabilities=[CAP_SHOP],
        spectrum={"level": "mid", "services": ["audit"]},
        escalations=[{"on": "constraint.violated", "actions": ["log", "nudge"]}],
    )
    with ag.session(export=False, secret_broker=_broker()) as run:
        with pytest.raises(ConstraintViolation):
            run.emit(
                "tool.call",
                {
                    "tool": "payment",
                    "capability_id": "shop-x-milk",
                    "args": {"merchant": "shop-x", "item": "milk", "card": "Z"},
                },
            )
    kinds = _kinds(run)
    assert "escalation.fired" in kinds
    assert "membrane.nudge" in kinds


def test_empty_capabilities_preserves_old_emit(aura_home: Path):
    ag = agent("cap-empty", spectrum={"level": "mid"})
    with ag.session(export=False) as run:
        run.emit("tool.call", {"tool": "anything.goes", "args": {"q": 1}})
    assert "tool.call" in _kinds(run)


def test_cli_capabilities_roundtrip(run_aura, tmp_path: Path):
    create = run_aura("agent", "create", "cap-cli")
    assert create.returncode == 0
    caps_path = tmp_path / "caps.json"
    caps_path.write_text(json.dumps([CAP_SHOP]), encoding="utf-8")
    result = run_aura(
        "agent",
        "set",
        "cap-cli",
        "--capabilities-file",
        str(caps_path),
    )
    assert result.returncode == 0
    profile = json.loads(result.stdout)
    assert profile["capabilities"][0]["id"] == "shop-x-milk"
    assert profile["capabilities"][0]["secret"]["ref"] == "env:AURA_CAP_SHOP_X_CARD_Y"
    assert "value" not in json.dumps(profile)

    show = run_aura("agent", "show", "cap-cli")
    assert show.returncode == 0
    shown = json.loads(show.stdout)
    assert shown["capabilities_summary"]["count"] == 1
    assert "shop-x-milk" in shown["capabilities_summary"]["ids"]

    bad = run_aura(
        "agent",
        "set",
        "cap-cli",
        "--capabilities-json",
        json.dumps([{"id": "x", "secret": {"value": "nope"}}]),
    )
    assert bad.returncode == 2


def test_session_open_capability_summary(aura_home: Path):
    ag = _agent("cap-open-meta")
    with ag.session(export=False, secret_broker=_broker()) as run:
        open_evt = next(e for e in run._session.spine.stream() if e.kind == "session.open")
    caps = (open_evt.payload.get("spectrum") or {}).get("capabilities") or {}
    assert caps.get("count") == 1
    assert caps.get("ids") == ["shop-x-milk"]
    assert "MapSecretBroker" in str(caps.get("broker"))
