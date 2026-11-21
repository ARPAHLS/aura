"""Tests for Skillware 0.6.2+ integration, audit bridge, FinOps, Manifest v2, and async egress."""

from __future__ import annotations

import builtins
from unittest.mock import patch

from aura.hosts import (
    skillware_available,
    skillware_capabilities,
    skillware_version,
)


def test_skillware_version_and_capabilities_when_absent():
    real_import = builtins.__import__

    def _block_skillware(name, *args, **kwargs):
        if name == "skillware" or name.startswith("skillware."):
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    with patch.object(builtins, "__import__", side_effect=_block_skillware):
        assert skillware_available() is False
        assert skillware_version() is None
        caps = skillware_capabilities()
        assert caps == {
            "installed": False,
            "manifest_schema": False,
            "audit_hook": False,
            "async_execution": False,
            "secret_provider": False,
            "deprecation_warning": False,
        }


def test_skillware_version_and_capabilities_when_installed():
    if not skillware_available():
        return
    ver = skillware_version()
    assert isinstance(ver, str) and len(ver) > 0
    caps = skillware_capabilities()
    assert caps["installed"] is True
    assert isinstance(caps["manifest_schema"], bool)
    assert isinstance(caps["audit_hook"], bool)
    assert isinstance(caps["async_execution"], bool)
    assert isinstance(caps["secret_provider"], bool)
    assert isinstance(caps["deprecation_warning"], bool)


def test_egress_telemetry_provenance_and_otel(aura_home):
    from pathlib import Path
    import json
    from aura import agent
    from aura.hosts import MockSkill, SkillwareHost

    ag = agent("telemetry-agent")
    with ag.session(export=True) as run:
        host = SkillwareHost(run._session)
        host.register(
            MockSkill(
                "finance/wallet_screening",
                {
                    "screen": lambda a: {
                        "verdict": "ALLOW",
                        "provenance": {"report_hash": "a" * 64, "generator": "test"},
                    }
                },
                manifest={
                    "name": "finance/wallet_screening",
                    "version": "2.1.0",
                    "description": "s",
                },
            )
        )
        res = host.execute(
            "finance/wallet_screening",
            "screen",
            {"address": "0x123"},
            audit_meta={
                "model": "gpt-4o",
                "prompt_tokens": 1000,
                "completion_tokens": 500,
            },
        )

    assert res["verdict"] == "ALLOW"
    tool_results = [e for e in run.get_events() if e.kind == "tool.result"]
    assert len(tool_results) == 1
    tr = tool_results[0]
    assert tr.span_id is not None
    assert tr.telemetry["latency_ms"] >= 0.0
    assert tr.telemetry["skill_version"] == "2.1.0"
    assert tr.telemetry["model"] == "gpt-4o"
    assert tr.telemetry["prompt_tokens"] == 1000
    assert tr.telemetry["completion_tokens"] == 500
    assert tr.telemetry["estimated_cost_usd"] == 0.0075
    assert tr.telemetry["provenance_hash"] == "a" * 64

    finops = run.audit_report["scorecard"]["finops"]
    assert finops["prompt_tokens"] == 1000
    assert finops["completion_tokens"] == 500
    assert finops["estimated_cost_usd"] == 0.0075
    assert finops["cost_by_model"]["gpt-4o"] == 0.0075
    assert finops["cost_by_skill"]["finance/wallet_screening"] == 0.0075

    otel_path = Path(run.exports["otel"])
    spans = [
        json.loads(line) for line in otel_path.read_text(encoding="utf-8").splitlines() if line
    ]
    tr_spans = [s for s in spans if s["name"] == "tool.result"]
    assert len(tr_spans) == 1
    attrs = tr_spans[0]["attributes"]
    assert attrs["aura.model"] == "gpt-4o"
    assert attrs["gen_ai.request.model"] == "gpt-4o"
    assert attrs["gen_ai.usage.input_tokens"] == 1000
    assert attrs["gen_ai.usage.output_tokens"] == 500
    assert attrs["gen_ai.tool.name"] == "screen"
    assert attrs["aura.estimated_cost_usd"] == 0.0075
    assert attrs["aura.provenance_hash"] == "a" * 64
    assert attrs["aura.latency_ms"] >= 0.0
    assert isinstance(tr_spans[0]["start_time_unix_nano"], int)
    assert tr_spans[0]["status"] == {"code": "OK"}


def test_dispatch_hook_unguarded_bypass_detection(aura_home):
    from aura import agent
    from aura.hosts import create_dispatch_audit_hook

    ag = agent("bypass-detect")
    with ag.session(export=False) as run:
        hook = create_dispatch_audit_hook(run._session)
        # Simulate SkillContext calling on_dispatch directly WITHOUT SkillwareHost.execute()
        hook(
            {
                "skill_id": "optimization/prompt_rewriter",
                "action": "execute",
                "status": "ok",
                "duration_ms": 4.2,
                "context_mode": "brief",
                "trace_id": "sw-trace-1",
                "span_id": "sw-span-1",
                "args": {"raw_text": "hello"},
                "model": "gpt-4o-mini",
                "prompt_tokens": 1000,
                "completion_tokens": 200,
            }
        )

    kinds = [e.kind for e in run.get_events()]
    assert "skill.dispatch" in kinds
    assert "skill.egress_bypass" in kinds
    findings = run.audit_report["findings"]
    assert any(
        f["code"] == "UNGUARDED_SKILL_DISPATCH" and f["severity"] == "high" for f in findings
    )
    assert run.audit_report["scorecard"]["skillware"]["unguarded_bypasses"] == 1
    assert run.audit_report["verdict"] == "warn"


def test_live_skill_context_dual_ledger_and_verification(aura_home, tmp_path):
    import json
    from pathlib import Path
    import pytest
    from aura import agent
    from aura.hosts import SkillwareHost, skillware_capabilities, verify_dual_audit_chain

    caps = skillware_capabilities()
    if not (caps["installed"] and caps["audit_hook"]):
        pytest.skip("Skillware 0.6.2+ with audit hook required")

    sw_log = tmp_path / "skillware_audit.jsonl"
    ag = agent("dual-ledger-agent", skills=["optimization/prompt_rewriter"])
    with ag.session(export=True) as run:
        host = SkillwareHost.create_context(
            run._session,
            skills=["optimization/prompt_rewriter"],
            audit_log_path=sw_log,
        )
        res = host.execute(
            "optimization/prompt_rewriter",
            "optimization/prompt_rewriter",
            {
                "raw_text": "Please kindly summarize this report with sk-proj-supersecret123456789",
                "compression_aggression": "low",
            },
            audit_meta={
                "model": "gpt-4o",
                "prompt_tokens": 2000,
                "completion_tokens": 400,
            },
        )

    assert "compressed_text" in res
    aura_log = Path(run.exports["jsonl"])

    # FinOps must NOT double-count bridged skill.dispatch + tool.result
    finops = run.audit_report["scorecard"]["finops"]
    assert finops["prompt_tokens"] == 2000
    assert finops["completion_tokens"] == 400
    assert finops["estimated_cost_usd"] == 0.009
    assert run.audit_report["scorecard"]["skillware"]["dispatches"] == 1
    assert run.audit_report["scorecard"]["skillware"]["unguarded_bypasses"] == 0
    assert run.audit_report["verdict"] == "pass"

    # Dual ledger verification passes on intact logs
    dual = verify_dual_audit_chain(aura_log, sw_log)
    assert dual.valid is True
    assert dual.aura_chain_valid is True
    assert dual.skillware_chain_valid is True
    assert dual.anchored_count == 1
    assert dual.missing_in_skillware == []
    assert dual.unanchored_in_aura == []

    # Tampering Skillware log fails dual-ledger verification
    tampered_sw = tmp_path / "tampered_sw.jsonl"
    rows = [json.loads(line) for line in sw_log.read_text(encoding="utf-8").splitlines() if line]
    rows[0]["action"] = "tampered_action"
    tampered_sw.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    dual_bad = verify_dual_audit_chain(aura_log, tampered_sw)
    assert dual_bad.valid is False
    assert dual_bad.skillware_chain_valid is False

    # Shadow unanchored execution in Skillware log is caught
    shadow_sw = tmp_path / "shadow_sw.jsonl"
    from skillware import SkillContext

    shadow_sw.write_text(sw_log.read_text(encoding="utf-8"), encoding="utf-8")
    ctx_shadow = SkillContext(skills=["optimization/prompt_rewriter"], audit_log_path=shadow_sw)
    ctx_shadow.execute(
        "optimization/prompt_rewriter",
        {"raw_text": "shadow call", "compression_aggression": "low"},
    )
    dual_shadow = verify_dual_audit_chain(aura_log, shadow_sw)
    assert dual_shadow.valid is False
    assert dual_shadow.skillware_chain_valid is True
    assert len(dual_shadow.unanchored_in_aura) == 1


def test_unified_secret_pattern_redaction_and_depth_guard(aura_home):
    from aura import agent
    from aura.core.payload_redaction import REDACTED, redact_payload, secret_like_key
    from aura.hosts import MockSkill, SkillwareHost
    import pytest

    # FinOps usage counters must NEVER be redacted
    for keep in ("prompt_tokens", "completion_tokens", "tokens_saved", "new_tokens", "tokens"):
        assert secret_like_key(keep) is False
    for sec in ("api_key", "access_key", "aws_access_key", "client_secret", "private_key"):
        assert secret_like_key(sec) is True

    # Deep nesting DoS guard (>32 levels)
    nested: dict = {"leaf": "ok"}
    cur = nested
    for _ in range(40):
        nxt: dict = {}
        cur["child"] = nxt
        cur = nxt
    cur["secret_value"] = "hidden"
    redacted_nested = redact_payload(nested)
    assert isinstance(redacted_nested, dict)

    # Raw secret patterns inside free-form args and raised error messages are scrubbed on the spine
    def _boom(_args):
        raise RuntimeError(
            "Upstream rejected Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig and "
            "key sk-proj-secretvalue987654321 and AWS AKIAIOSFODNN7EXAMPLE"
        )

    ag = agent("redact-patterns")
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("leaky", {"fail": _boom}))
        with pytest.raises(RuntimeError):
            host.execute(
                "leaky",
                "fail",
                {
                    "note": (
                        "The bearer of bad news discussed bearer token concepts and "
                        "bearer responsibilities. "
                        "ghp_1234567890abcdef1234567890 "
                        "AIzaSyD-1234567890abcdef1234567890 "
                        "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
                    ),
                    "prompt_tokens": 250,
                },
            )

    events = run.get_events()
    serialized = str([e.to_dict() for e in events])
    assert "sk-proj-secretvalue987654321" not in serialized
    assert "AKIAIOSFODNN7EXAMPLE" not in serialized
    assert "ghp_1234567890abcdef1234567890" not in serialized
    assert "AIzaSyD-1234567890abcdef1234567890" not in serialized
    assert "BEGIN RSA PRIVATE KEY" not in serialized
    assert "eyJhbGciOiJIUzI1NiJ9" not in serialized
    assert REDACTED in serialized

    tool_call = [e for e in events if e.kind == "tool.call"][0]
    assert tool_call.payload["args"]["prompt_tokens"] == 250
    prose = "The bearer of bad news discussed bearer token concepts and bearer responsibilities."
    assert prose in tool_call.payload["args"]["note"]
    tool_err = [e for e in events if e.kind == "tool.error"][0]
    assert tool_err.payload["error_type"] == "RuntimeError"


def test_limit_observer_usd_cost_budget_alert(aura_home):
    from aura import agent
    from aura.hosts import MockSkill, SkillwareHost

    ag = agent(
        "finops-budget-agent",
        observers=[
            {
                "preset": "limit",
                "id": "cost-guard",
                "config": {"max_cost_usd": 0.01, "warn_ratio": 0.7},
            }
        ],
    )
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("calc", {"run": lambda a: {"ok": True}}))
        # Call 1: gpt-4o 1000 in + 500 out = $0.0075 (>= 0.007 warn threshold)
        host.execute(
            "calc",
            "run",
            {"i": 1},
            audit_meta={"model": "gpt-4o", "prompt_tokens": 1000, "completion_tokens": 500},
        )
        # Call 2: +$0.0075 -> $0.015 (> 0.01 alert threshold)
        host.execute(
            "calc",
            "run",
            {"i": 2},
            audit_meta={"model": "gpt-4o", "prompt_tokens": 1000, "completion_tokens": 500},
        )

    events = run.get_events()
    notes = [e for e in events if e.kind == "observer.note"]
    alerts = [e for e in events if e.kind == "observer.alert"]
    assert any(n.payload.get("type") == "cost_budget_warning" for n in notes)
    assert any(a.payload.get("type") == "cost_budget_exceeded" for a in alerts)
    assert run.audit_report["scorecard"]["finops"]["estimated_cost_usd"] == 0.015


def test_manifest_v2_validation_warn_strict_and_mock_compat(aura_home):
    import pytest
    from aura import agent
    from aura.hosts import ManifestValidationError, MockSkill, SkillwareHost

    # 1) Legacy guardrail-only MockSkill manifest remains 100% valid
    ag_legacy = agent("legacy-manifest")
    with ag_legacy.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("ops", {"ping": lambda a: "ok"}, manifest={"deny_tools": ["rm"]}))
    reg = [e for e in run.get_events() if e.kind == "skill.registered"][0]
    assert reg.payload["manifest_validation"]["valid"] is True
    assert reg.payload["taxonomy"]["shape"] == "atomic"
    assert reg.payload["taxonomy"]["target"] == ["software"]

    # 2) Warn mode records schema errors on spine & audit_report without blocking registration
    bad_manifest = {
        "name": "bad/skill",
        "version": "1.0.0",
        "description": "invalid taxonomy",
        "shape": "quantum",
        "target": ["marsware"],
        "tags": ["INVALID TAG!"],
    }
    ag_warn = agent("warn-manifest")
    with ag_warn.session(export=False) as run:
        host = SkillwareHost(run._session, manifest_validation="warn")
        host.register(MockSkill("bad/skill", {"go": lambda a: {}}, manifest=bad_manifest))
    reg_warn = [e for e in run.get_events() if e.kind == "skill.registered"][0]
    assert reg_warn.payload["manifest_validation"]["valid"] is False
    assert len(reg_warn.payload["manifest_validation"]["errors"]) >= 1
    assert any(f["code"] == "MANIFEST_SCHEMA_INVALID" for f in run.audit_report["findings"])

    # 3) Strict mode emits skill.manifest_invalid and rejects bind with ManifestValidationError
    ag_strict = agent("strict-manifest")
    with ag_strict.session(export=False) as run:
        host = SkillwareHost(run._session, manifest_validation="strict")
        with pytest.raises(ManifestValidationError) as exc_info:
            host.register(MockSkill("bad/skill", {"go": lambda a: {}}, manifest=bad_manifest))
        assert exc_info.value.skill_id == "bad/skill"
        assert "bad/skill" not in host._skills
    assert any(e.kind == "skill.manifest_invalid" for e in run.get_events())


def test_physical_target_safety_gate_and_opt_in(aura_home):
    import pytest
    from aura import ApprovalRequired, agent
    from aura.hosts import MockSkill, SkillwareHost

    hw_manifest = {
        "name": "robotics/arm_mover",
        "version": "0.1.0",
        "description": "Actuate robotic arm",
        "shape": "atomic",
        "tier": "enterprise",
        "target": ["hardware"],
        "tags": ["robotics"],
    }

    # Default allow_hardware_execution=False requires explicit operator approval
    ag_safe = agent("hw-safe")
    with ag_safe.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(
            MockSkill(
                "robotics/arm_mover",
                {"robotics/arm_mover": lambda a: {"moved": True}},
                manifest=hw_manifest,
            )
        )
        with pytest.raises(ApprovalRequired) as exc:
            host.execute("robotics/arm_mover", "robotics/arm_mover", {"axis": "x"})
        run.approve(exc.value.request_id, principal="safety-officer@acme")
        res = host.execute("robotics/arm_mover", "robotics/arm_mover", {"axis": "x"})
    assert res == {"moved": True}
    reg = [e for e in run.get_events() if e.kind == "skill.registered"][0]
    assert reg.payload["physical_target"] is True
    assert reg.payload["hardware_execution_acknowledged"] is False
    assert any(f["code"] == "PHYSICAL_TARGET_REGISTERED" for f in run.audit_report["findings"])

    # Explicit allow_hardware_execution=True executes directly while auditing acknowledgment
    ag_ack = agent("hw-ack")
    with ag_ack.session(export=False) as run:
        host = SkillwareHost(run._session, allow_hardware_execution=True)
        host.register(
            MockSkill(
                "robotics/arm_mover",
                {"robotics/arm_mover": lambda a: {"moved": True}},
                manifest=hw_manifest,
            )
        )
        res = host.execute("robotics/arm_mover", "robotics/arm_mover", {"axis": "y"})
    assert res == {"moved": True}
    reg_ack = [e for e in run.get_events() if e.kind == "skill.registered"][0]
    assert reg_ack.payload["hardware_execution_acknowledged"] is True


def test_deprecated_skill_and_high_spectrum_auto_schema_wiring(aura_home):
    import pytest
    from aura import agent
    from aura.core.constraints import ConstraintViolation
    from aura.hosts import MockSkill, SkillwareHost

    manifest = {
        "name": "monitoring/legacy_probe",
        "version": "0.1.0",
        "description": "Deprecated probe with JSON Schema parameters",
        "deprecated": True,
        "deprecation_notice": "Use monitoring/rpc_health_probe instead.",
        "parameters": {
            "type": "object",
            "properties": {"count": {"type": "integer", "minimum": 1}},
            "required": ["count"],
        },
    }
    executed = []
    ag = agent(
        "high-schema-agent",
        skills=["monitoring/legacy_probe"],
        spectrum={"level": "high", "identity_required": False},
    )
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(
            MockSkill(
                "monitoring/legacy_probe",
                {"monitoring/legacy_probe": lambda a: executed.append(a) or {"ok": True}},
                manifest=manifest,
            )
        )
        # Missing required integer 'count' is blocked at egress BEFORE skill body runs
        with pytest.raises(ConstraintViolation):
            host.execute("monitoring/legacy_probe", "monitoring/legacy_probe", {"count": "bad"})
        assert executed == []
        # Valid payload passes schema_check and runs
        res = host.execute("monitoring/legacy_probe", "monitoring/legacy_probe", {"count": 3})
        assert res == {"ok": True}

    findings = run.audit_report["findings"]
    assert any(f["code"] == "SKILL_DEPRECATED" for f in findings)
    assert any(f["code"] == "SCHEMA_VIOLATION" for f in findings)


def test_secret_broker_credential_fn_bridge_and_scrub(aura_home):
    from aura import MapSecretBroker, agent
    from aura.hosts.skillware_adapter import make_broker_credential_fn

    broker = MapSecretBroker({"env:MY_SKILL_KEY": "super-secret-broker-value-999"})
    ag = agent("cred-bridge")
    with ag.session(export=False, secret_broker=broker) as run:
        cred_fn = make_broker_credential_fn(run._session)
        assert cred_fn is not None
        val = cred_fn("MY_SKILL_KEY")
        assert val == "super-secret-broker-value-999"
        # Emitting a payload that accidentally echoes the resolved value must scrub it!
        run.emit("tool.result", {"echo": f"leaked:{val}"})

    result_evt = [e for e in run.get_events() if e.kind == "tool.result"][0]
    assert "super-secret-broker-value-999" not in str(result_evt.payload)


def test_async_egress_concurrency_timeout_and_hash_chain_integrity(aura_home):
    import asyncio
    from pathlib import Path
    import pytest
    from aura import agent
    from aura.core.spine import AuditSpine, verify_hash_chain
    from aura.hosts import MockSkill, SkillwareHost

    active = 0
    peak_active = 0

    async def _slow_async(args):
        nonlocal active, peak_active
        active += 1
        peak_active = max(peak_active, active)
        try:
            await asyncio.sleep(float(args.get("delay", 0.01)))
            return {"idx": args["idx"], "ok": True}
        finally:
            active -= 1

    async def _run() -> tuple[list[dict], Path, dict]:
        ag = agent("async-stress")
        with ag.session(export=True) as run:
            host = SkillwareHost(run._session, max_concurrency=4)
            host.register(
                MockSkill("worker", {"work": _slow_async, "sync": lambda a: {"s": a["i"]}})
            )

            # Run 32 concurrent async tasks + sync offloads with concurrency cap = 4
            tasks = [
                host.aexecute(
                    "worker",
                    "work",
                    {"idx": i, "delay": 0.005},
                    audit_meta={
                        "model": "gpt-4o-mini",
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                    },
                )
                for i in range(32)
            ]
            results = await asyncio.gather(*tasks)

            # Also verify sync handler offload through aexecute
            sync_res = await host.aexecute("worker", "sync", {"i": 99})
            assert sync_res == {"s": 99}

            # Verify timeout enforcement and structured TimeoutError audit event
            with pytest.raises(asyncio.TimeoutError):
                await host.aexecute("worker", "work", {"idx": -1, "delay": 0.5}, timeout=0.02)

        return results, Path(run.exports["jsonl"]), run.audit_report

    results, log_path, report = asyncio.run(_run())
    assert len(results) == 32
    assert peak_active <= 4
    assert report["hash_chain_valid"] is True

    reloaded = AuditSpine.from_jsonl(log_path)
    assert verify_hash_chain(reloaded) is True
    errors = [e for e in reloaded.stream() if e.kind == "tool.error"]
    assert len(errors) == 1
    assert errors[0].payload["error_type"] == "TimeoutError"
    assert errors[0].payload["timeout_seconds"] == 0.02
    assert report["scorecard"]["finops"]["prompt_tokens"] == 3200
    assert report["scorecard"]["finops"]["completion_tokens"] == 1600


def test_live_skillware_async_context_execution(aura_home, tmp_path):
    import asyncio
    from pathlib import Path
    import pytest
    from aura import agent
    from aura.hosts import SkillwareHost, skillware_capabilities, verify_dual_audit_chain

    caps = skillware_capabilities()
    if not (caps["installed"] and caps["async_execution"] and caps["audit_hook"]):
        pytest.skip("Skillware 0.6.2+ with async execution and audit hook required")

    sw_log = tmp_path / "async_sw.jsonl"

    async def _run():
        ag = agent("live-async-sw", skills=["optimization/prompt_rewriter"])
        with ag.session(export=True) as run:
            host = SkillwareHost.create_context(
                run._session,
                skills=["optimization/prompt_rewriter"],
                audit_log_path=sw_log,
                max_concurrency=3,
            )
            calls = [
                host.aexecute(
                    "optimization/prompt_rewriter",
                    "optimization/prompt_rewriter",
                    {
                        "raw_text": f"Please kindly summarize document number {i} carefully.",
                        "compression_aggression": "low",
                    },
                    audit_meta={
                        "model": "gemini-2.5-flash",
                        "prompt_tokens": 200,
                        "completion_tokens": 50,
                    },
                )
                for i in range(6)
            ]
            results = await asyncio.gather(*calls)
        return results, Path(run.exports["jsonl"]), run.audit_report

    results, aura_log, report = asyncio.run(_run())
    assert len(results) == 6
    assert all("compressed_text" in r for r in results)
    assert report["verdict"] == "pass"
    assert report["scorecard"]["skillware"]["dispatches"] == 6
    assert report["scorecard"]["skillware"]["unguarded_bypasses"] == 0
    assert report["scorecard"]["finops"]["prompt_tokens"] == 1200

    dual = verify_dual_audit_chain(aura_log, sw_log)
    assert dual.valid is True
    assert dual.anchored_count == 6


def test_otel_error_span_status_and_custom_model_pricing(aura_home):
    import json
    from pathlib import Path
    import pytest
    from aura import agent
    from aura.hosts import MockSkill, SkillwareHost

    ag = agent(
        "custom-pricing-otel",
        observers=[
            {
                "preset": "limit",
                "id": "custom-cost",
                "config": {
                    "max_cost_usd": 0.005,
                    "warn_ratio": 0.5,
                    "model_pricing": {"custom-internal-llm": [5.0, 20.0]},
                },
            }
        ],
    )
    with ag.session(export=True) as run:
        host = SkillwareHost(run._session)
        host.register(
            MockSkill(
                "worker",
                {"fail": lambda a: (_ for _ in ()).throw(RuntimeError("boom"))},
            )
        )
        with pytest.raises(RuntimeError):
            host.execute(
                "worker",
                "fail",
                {"x": 1},
                audit_meta={
                    "model": "custom-internal-llm",
                    "prompt_tokens": 1000,
                    "completion_tokens": 100,
                },
            )
        # 1000*5/1M + 100*20/1M = 0.005 + 0.002 = 0.007 > max_cost_usd (0.005)
    events = run.get_events()
    assert any(
        e.kind == "observer.alert" and e.payload.get("type") == "cost_budget_exceeded"
        for e in events
    )
    spans = [
        json.loads(ln)
        for ln in Path(run.exports["otel"]).read_text(encoding="utf-8").splitlines()
        if ln
    ]
    err_spans = [s for s in spans if s["name"] == "tool.error"]
    assert len(err_spans) == 1
    assert err_spans[0]["status"] == {"code": "ERROR"}
    assert err_spans[0]["attributes"]["error.type"] == "RuntimeError"
    assert err_spans[0]["attributes"]["gen_ai.tool.name"] == "fail"
