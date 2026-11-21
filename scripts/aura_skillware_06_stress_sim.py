#!/usr/bin/env python3
"""
AURA + Skillware 0.6.2+ audit bridge, FinOps, Manifest v2, and async egress stress simulation.

Runs 10 core scenarios without requiring Skillware installed, plus 2 live Skillware 0.6.2+
dual-ledger and multi-skill async scenarios when the [skillware] extra is present.

Usage (repo root):
  python scripts/aura_skillware_06_stress_sim.py

Exit 0 when all runnable scenarios pass; 1 on any failure.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from aura import ApprovalRequired, MapSecretBroker, agent, configure  # noqa: E402
from aura.core.constraints import ConstraintViolation  # noqa: E402
from aura.core.payload_redaction import redact_payload  # noqa: E402
from aura.core.spine import AuditSpine, verify_hash_chain  # noqa: E402
from aura.hosts import (  # noqa: E402
    ManifestValidationError,
    MockSkill,
    SkillwareHost,
    create_dispatch_audit_hook,
    skillware_capabilities,
    verify_dual_audit_chain,
)
from aura.hosts.skillware_adapter import make_broker_credential_fn  # noqa: E402


@dataclass
class SimResult:
    name: str
    passed: bool
    skipped: bool = False
    reason: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def scenario_egress_telemetry_and_provenance() -> SimResult:
    ag = agent("sim-sw06-telemetry")
    with ag.session(export=True) as run:
        host = SkillwareHost(run._session)
        host.register(
            MockSkill(
                "finance/wallet_screening",
                {
                    "screen": lambda a: {
                        "verdict": "ALLOW",
                        "provenance": {"report_hash": "f" * 64},
                    }
                },
                manifest={
                    "name": "finance/wallet_screening",
                    "version": "2.1.0",
                    "description": "Screen wallet address",
                    "shape": "atomic",
                    "tier": "core",
                    "target": ["software"],
                    "tags": ["finance", "compliance"],
                },
            )
        )
        host.execute(
            "finance/wallet_screening",
            "screen",
            {"address": "0xabc"},
            audit_meta={"model": "gpt-4o", "prompt_tokens": 2000, "completion_tokens": 500},
        )
    finops = run.audit_report["scorecard"]["finops"]
    _assert(finops["estimated_cost_usd"] == 0.01, f"unexpected cost {finops}")
    otel_lines = Path(run.exports["otel"]).read_text(encoding="utf-8").splitlines()
    spans = [json.loads(line) for line in otel_lines if line]
    res_span = [s for s in spans if s["name"] == "tool.result"][0]
    _assert(res_span["attributes"]["aura.provenance_hash"] == "f" * 64, "missing provenance_hash")
    return SimResult("egress_telemetry_and_provenance", True, metrics={"cost": 0.01})


def scenario_secret_pattern_redaction_and_error_scrub() -> SimResult:
    def _explode(_args: dict[str, Any]) -> None:
        raise ValueError(
            "Auth failed: Bearer tok_secret_999999999, sk-live-supersecret1234567, "
            "AKIAIOSFODNN7EXAMPLE, ghp_1234567890abcdef1234567890"
        )

    ag = agent("sim-sw06-redaction")
    with ag.session(export=True) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("leaky", {"boom": _explode}))
        try:
            host.execute(
                "leaky",
                "boom",
                {
                    "text": (
                        "The bearer of bad news discussed bearer token concepts. "
                        "AIzaSyD-1234567890abcdef1234567890 "
                        "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
                    ),
                    "aws_access_key": "raw-access-key-secret",
                    "prompt_tokens": 42,
                },
            )
        except ValueError:
            pass
    raw_jsonl = Path(run.exports["jsonl"]).read_text(encoding="utf-8")
    for secret in (
        "tok_secret_999999999",
        "sk-live-supersecret1234567",
        "AKIAIOSFODNN7EXAMPLE",
        "ghp_1234567890abcdef1234567890",
        "AIzaSyD-1234567890abcdef1234567890",
        "BEGIN PRIVATE KEY",
        "raw-access-key-secret",
    ):
        _assert(secret not in raw_jsonl, f"secret leaked to spine: {secret}")
    _assert(
        "The bearer of bad news discussed bearer token concepts." in raw_jsonl,
        "English 'bearer' prose was over-redacted",
    )
    _assert('"prompt_tokens": 42' in raw_jsonl, "FinOps token counter erroneously redacted")
    return SimResult("secret_pattern_redaction_and_error_scrub", True)


def scenario_deep_nested_adversarial_payload() -> SimResult:
    root: dict[str, Any] = {}
    cur = root
    for i in range(55):
        nxt: dict[str, Any] = {"level": i}
        cur["next"] = nxt
        cur = nxt
    cur["payload"] = "sk-proj-deepsecret1234567890"
    cleaned = redact_payload(root)
    _assert("sk-proj-deepsecret1234567890" not in str(cleaned), "deep secret not truncated")
    return SimResult("deep_nested_adversarial_payload", True, metrics={"depth": 55})


def scenario_finops_cost_circuit_breaker_and_escalation() -> SimResult:
    ag = agent(
        "sim-sw06-finops-esc",
        observers=[
            {
                "preset": "limit",
                "id": "usd-limit",
                "config": {"max_cost_usd": 0.01, "warn_ratio": 0.6},
            }
        ],
        escalations=[
            {
                "id": "cost-alert-nudge",
                "on": "observer.alert",
                "actions": ["log", "nudge:USD cost cap exceeded"],
            }
        ],
    )
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("llm_tool", {"run": lambda a: {"ok": True}}))
        for _ in range(3):
            host.execute(
                "llm_tool",
                "run",
                {},
                audit_meta={"model": "gpt-4o", "prompt_tokens": 1000, "completion_tokens": 400},
            )
    events = run.get_events()
    _assert(
        any(
            e.kind == "observer.note" and e.payload.get("type") == "cost_budget_warning"
            for e in events
        ),
        "missing cost_budget_warning",
    )
    _assert(
        any(
            e.kind == "observer.alert" and e.payload.get("type") == "cost_budget_exceeded"
            for e in events
        ),
        "missing cost_budget_exceeded",
    )
    _assert(
        any(e.kind == "escalation.fired" for e in events),
        "missing escalation.fired",
    )
    _assert(
        any(
            e.kind == "membrane.nudge" and e.payload.get("message") == "USD cost cap exceeded"
            for e in events
        ),
        "missing membrane.nudge from cost escalation",
    )
    return SimResult(
        "finops_cost_circuit_breaker_and_escalation",
        True,
        metrics={"cost": run.audit_report["scorecard"]["finops"]["estimated_cost_usd"]},
    )


def scenario_unguarded_dispatch_bypass_detection() -> SimResult:
    ag = agent("sim-sw06-bypass")
    with ag.session(export=False) as run:
        hook = create_dispatch_audit_hook(run._session)
        hook(
            {
                "skill_id": "security/prompt_injection_firewall",
                "action": "scan",
                "status": "ok",
                "duration_ms": 2.1,
                "context_mode": "brief",
                "args": {"source_text": "hello"},
            }
        )
    findings = run.audit_report["findings"]
    _assert(
        any(f["code"] == "UNGUARDED_SKILL_DISPATCH" and f["severity"] == "high" for f in findings),
        "missing UNGUARDED_SKILL_DISPATCH finding",
    )
    _assert(run.audit_report["verdict"] == "warn", "expected warn verdict on bypass")
    return SimResult("unguarded_dispatch_bypass_detection", True)


def scenario_manifest_v2_warn_and_strict_enforcement() -> SimResult:
    bad = {
        "name": "x/bad",
        "version": "1.0.0",
        "description": "bad",
        "shape": "unknown_shape",
        "target": ["invalid_target"],
        "tags": ["BAD TAG"],
    }
    ag1 = agent("sim-sw06-mwarn")
    with ag1.session(export=False) as run1:
        host1 = SkillwareHost(run1._session, manifest_validation="warn")
        host1.register(MockSkill("x/bad", {"go": lambda a: {}}, manifest=bad))
    _assert(
        any(f["code"] == "MANIFEST_SCHEMA_INVALID" for f in run1.audit_report["findings"]),
        "warn mode should emit MANIFEST_SCHEMA_INVALID",
    )

    ag2 = agent("sim-sw06-mstrict")
    blocked = False
    with ag2.session(export=False) as run2:
        host2 = SkillwareHost(run2._session, manifest_validation="strict")
        try:
            host2.register(MockSkill("x/bad", {"go": lambda a: {}}, manifest=bad))
        except ManifestValidationError:
            blocked = True
    _assert(blocked, "strict mode should raise ManifestValidationError")
    _assert(any(e.kind == "skill.manifest_invalid" for e in run2.get_events()), "missing event")
    return SimResult("manifest_v2_warn_and_strict_enforcement", True)


def scenario_physical_substrate_hardware_and_bioware_gate() -> SimResult:
    bio_manifest = {
        "name": "bio/liquid_handler",
        "version": "0.1.0",
        "description": "Dispense reagents",
        "target": ["bioware"],
    }
    ag = agent("sim-sw06-bio-gate")
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(
            MockSkill(
                "bio/liquid_handler",
                {"bio/liquid_handler": lambda a: {"dispensed_ul": a["ul"]}},
                manifest=bio_manifest,
            )
        )
        gated = False
        try:
            host.execute("bio/liquid_handler", "bio/liquid_handler", {"ul": 50})
        except ApprovalRequired as exc:
            gated = True
            run.approve(exc.request_id, principal="lab-director@acme")
        _assert(gated, "bioware skill must require approval by default")
        res = host.execute("bio/liquid_handler", "bio/liquid_handler", {"ul": 50})
        _assert(res == {"dispensed_ul": 50}, "post-approval execution failed")
    return SimResult("physical_substrate_hardware_and_bioware_gate", True)


def scenario_high_spectrum_manifest_parameter_schema_enforcement() -> SimResult:
    manifest = {
        "name": "ops/transfer",
        "version": "1.0.0",
        "description": "Typed transfer",
        "parameters": {
            "type": "object",
            "properties": {"amount": {"type": "number", "minimum": 1}},
            "required": ["amount"],
        },
    }
    ag = agent(
        "sim-sw06-high-schema",
        skills=["ops/transfer"],
        spectrum={"level": "high", "identity_required": False},
    )
    called = 0

    def _run(args: dict[str, Any]) -> dict[str, Any]:
        nonlocal called
        called += 1
        return {"ok": True, "amount": args["amount"]}

    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("ops/transfer", {"ops/transfer": _run}, manifest=manifest))
        rejected = False
        try:
            host.execute("ops/transfer", "ops/transfer", {"amount": -5})
        except ConstraintViolation:
            rejected = True
        _assert(rejected and called == 0, "invalid amount must be blocked before skill runs")
        res = host.execute("ops/transfer", "ops/transfer", {"amount": 100})
        _assert(res["ok"] is True and called == 1, "valid call must run")
    return SimResult("high_spectrum_manifest_parameter_schema_enforcement", True)


def scenario_secret_broker_credential_fn_isolation() -> SimResult:
    env_key = "AURA_SIM_ISOLATED_CRED_KEY"
    _assert(env_key not in os.environ, "env key should not exist in os.environ")
    broker = MapSecretBroker({f"env:{env_key}": "isolated-cred-secret-xyz123"})
    ag = agent("sim-sw06-cred-iso")
    with ag.session(export=True, secret_broker=broker) as run:
        fn = make_broker_credential_fn(run._session)
        _assert(fn is not None, "broker credential_fn missing")
        val = fn(env_key)
        _assert(val == "isolated-cred-secret-xyz123", "unexpected resolved credential")
        run.emit("tool.result", {"debug": f"got={val}"})
    _assert(env_key not in os.environ, "os.environ must remain unmutated")
    raw = Path(run.exports["jsonl"]).read_text(encoding="utf-8")
    _assert("isolated-cred-secret-xyz123" not in raw, "credential leaked into spine")
    return SimResult("secret_broker_credential_fn_isolation", True)


def scenario_async_concurrency_100_tasks_hash_chain_stress() -> SimResult:
    active = 0
    peak = 0

    async def _task_fn(args: dict[str, Any]) -> dict[str, Any]:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(float(args.get("delay", 0.002)))
            return {"i": args["i"]}
        finally:
            active -= 1

    async def _drive() -> tuple[Path, dict[str, Any]]:
        ag = agent("sim-sw06-async-100")
        with ag.session(export=True) as run:
            host = SkillwareHost(run._session, max_concurrency=8)
            host.register(
                MockSkill(
                    "batch",
                    {"async_op": _task_fn, "sync_op": lambda a: {"s": a["i"]}},
                )
            )
            coros = []
            for i in range(100):
                if i % 2 == 0:
                    coros.append(
                        host.aexecute(
                            "batch",
                            "async_op",
                            {"i": i, "delay": 0.002},
                            audit_meta={
                                "model": "gpt-4o-mini",
                                "prompt_tokens": 50,
                                "completion_tokens": 25,
                            },
                        )
                    )
                else:
                    coros.append(
                        host.aexecute(
                            "batch",
                            "sync_op",
                            {"i": i},
                            audit_meta={
                                "model": "gpt-4o-mini",
                                "prompt_tokens": 50,
                                "completion_tokens": 25,
                            },
                        )
                    )
            results = await asyncio.gather(*coros)
            _assert(len(results) == 100, f"expected 100 results, got {len(results)}")
            timed_out = False
            try:
                await host.aexecute("batch", "async_op", {"i": -1, "delay": 0.5}, timeout=0.02)
            except asyncio.TimeoutError:
                timed_out = True
            _assert(timed_out, "timeout must raise asyncio.TimeoutError")
        return Path(run.exports["jsonl"]), run.audit_report

    log_path, report = asyncio.run(_drive())
    _assert(peak <= 8, f"concurrency limit breached: peak={peak}")
    _assert(report["hash_chain_valid"] is True, "in-memory hash chain broken")
    reloaded = AuditSpine.from_jsonl(log_path)
    _assert(verify_hash_chain(reloaded) is True, "reloaded JSONL hash chain broken")
    _assert(report["scorecard"]["finops"]["prompt_tokens"] == 5000, "wrong prompt_tokens")
    _assert(report["scorecard"]["finops"]["completion_tokens"] == 2500, "wrong completion_tokens")
    return SimResult(
        "async_concurrency_100_tasks_hash_chain_stress",
        True,
        metrics={"tasks": 100, "peak_concurrency": peak, "events": len(reloaded.stream())},
    )


def scenario_live_skillware_dual_ledger_and_tamper_detection() -> SimResult:
    caps = skillware_capabilities()
    if not (caps["installed"] and caps["audit_hook"]):
        return SimResult(
            "live_skillware_dual_ledger_and_tamper_detection",
            True,
            skipped=True,
            reason="skillware 0.6.2+ audit hook not installed",
        )
    with tempfile.TemporaryDirectory() as td:
        sw_log = Path(td) / "sw_audit.jsonl"
        ag = agent(
            "sim-sw06-live-dual",
            skills=["security/prompt_injection_firewall", "optimization/prompt_rewriter"],
        )
        with ag.session(export=True) as run:
            host = SkillwareHost.create_context(
                run._session,
                skills=["security/prompt_injection_firewall", "optimization/prompt_rewriter"],
                audit_log_path=sw_log,
            )
            r1 = host.execute(
                "security/prompt_injection_firewall",
                "security/prompt_injection_firewall",
                {"source_text": "Summarize quarterly financial results", "sensitivity": "balanced"},
                audit_meta={"model": "gpt-4o", "prompt_tokens": 500, "completion_tokens": 100},
            )
            _assert(r1.get("is_safe") is True, "expected safe classification")
            r2 = host.execute(
                "optimization/prompt_rewriter",
                "optimization/prompt_rewriter",
                {
                    "raw_text": "Please kindly summarize the quarterly report",
                    "compression_aggression": "low",
                },
                audit_meta={"model": "gpt-4o", "prompt_tokens": 500, "completion_tokens": 100},
            )
            _assert("compressed_text" in r2, "expected compressed_text")

        aura_log = Path(run.exports["jsonl"])
        dual = verify_dual_audit_chain(aura_log, sw_log)
        _assert(dual.valid is True and dual.anchored_count == 2, f"dual verify failed: {dual}")

        # Tamper AURA log -> must fail
        tampered_aura = Path(td) / "tampered_aura.jsonl"
        rows = [json.loads(ln) for ln in aura_log.read_text(encoding="utf-8").splitlines() if ln]
        rows[-1]["payload"]["reason"] = "forged"
        tampered_aura.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        dual_aura_bad = verify_dual_audit_chain(tampered_aura, sw_log)
        _assert(
            dual_aura_bad.valid is False and dual_aura_bad.aura_chain_valid is False,
            "missed AURA tamper",
        )

    return SimResult(
        "live_skillware_dual_ledger_and_tamper_detection",
        True,
        metrics={"anchored_count": dual.anchored_count},
    )


def scenario_live_skillware_async_multi_skill() -> SimResult:
    caps = skillware_capabilities()
    if not (caps["installed"] and caps["async_execution"] and caps["audit_hook"]):
        return SimResult(
            "live_skillware_async_multi_skill",
            True,
            skipped=True,
            reason="skillware 0.6.2+ async + audit hook not installed",
        )

    async def _drive() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as td:
            sw_log = Path(td) / "sw_async.jsonl"
            ag = agent(
                "sim-sw06-live-async",
                skills=[
                    "security/prompt_injection_firewall",
                    "optimization/prompt_rewriter",
                    "data_engineering/unit_normalizer",
                ],
            )
            with ag.session(export=True) as run:
                host = SkillwareHost.create_context(
                    run._session,
                    skills=[
                        "security/prompt_injection_firewall",
                        "optimization/prompt_rewriter",
                        "data_engineering/unit_normalizer",
                    ],
                    audit_log_path=sw_log,
                    max_concurrency=3,
                )
                r_fw, r_rw, r_un = await asyncio.gather(
                    host.aexecute(
                        "security/prompt_injection_firewall",
                        "security/prompt_injection_firewall",
                        {"source_text": "Hello world", "sensitivity": "balanced"},
                    ),
                    host.aexecute(
                        "optimization/prompt_rewriter",
                        "optimization/prompt_rewriter",
                        {"raw_text": "Please kindly read this", "compression_aggression": "low"},
                    ),
                    host.aexecute(
                        "data_engineering/unit_normalizer",
                        "data_engineering/unit_normalizer",
                        {"action": "normalize", "value": 100, "from_unit": "km", "to_unit": "m"},
                    ),
                )
                _assert(r_fw.get("is_safe") is True, "firewall failed")
                _assert("compressed_text" in r_rw, "rewriter failed")
                _assert(r_un is not None, "unit_normalizer failed")

            dual = verify_dual_audit_chain(Path(run.exports["jsonl"]), sw_log)
            _assert(dual.valid is True and dual.anchored_count == 3, f"async dual failed: {dual}")
            return {"anchored": dual.anchored_count, "verdict": run.audit_report["verdict"]}

    metrics = asyncio.run(_drive())
    return SimResult("live_skillware_async_multi_skill", True, metrics=metrics)


SCENARIOS: list[Callable[[], SimResult]] = [
    scenario_egress_telemetry_and_provenance,
    scenario_secret_pattern_redaction_and_error_scrub,
    scenario_deep_nested_adversarial_payload,
    scenario_finops_cost_circuit_breaker_and_escalation,
    scenario_unguarded_dispatch_bypass_detection,
    scenario_manifest_v2_warn_and_strict_enforcement,
    scenario_physical_substrate_hardware_and_bioware_gate,
    scenario_high_spectrum_manifest_parameter_schema_enforcement,
    scenario_secret_broker_credential_fn_isolation,
    scenario_async_concurrency_100_tasks_hash_chain_stress,
    scenario_live_skillware_dual_ledger_and_tamper_detection,
    scenario_live_skillware_async_multi_skill,
]


def main() -> int:
    with tempfile.TemporaryDirectory() as home:
        os.environ["AURA_HOME"] = home
        configure()
        results: list[SimResult] = []
        failed = 0
        for fn in SCENARIOS:
            try:
                res = fn()
            except Exception as exc:
                res = SimResult(fn.__name__, passed=False, reason=str(exc))
            results.append(res)
            status = "SKIP" if res.skipped else ("PASS" if res.passed else "FAIL")
            detail = f" ({res.reason})" if res.reason else ""
            print(f"[{status}] {res.name}{detail} {res.metrics or ''}".rstrip())
            if not res.passed:
                failed += 1
        if failed == 0:
            print(f"ALL SCENARIOS PASSED ({len(results)} total)")
            return 0
        print(f"FAILED: {failed}/{len(results)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
