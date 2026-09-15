#!/usr/bin/env python3
"""
Capability broker stress simulation (#48).

Exercises named intents, scope matching, secret inject, spine redaction,
spectrum low vs mid+, bypass attempts, and ambiguous payloads. No Skillware extra.

Usage (repo root):
  python scripts/aura_capability_stress_sim.py

Exit 0 when all scenarios pass; 1 on any failure.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from aura import MapSecretBroker, SecretNotFoundError, agent, configure  # noqa: E402
from aura.core.audit_report import AuditReportBuilder  # noqa: E402
from aura.core.capabilities import CapabilityConfigError  # noqa: E402
from aura.core.conformance import ConformanceEngine  # noqa: E402
from aura.core.constraints import ConstraintViolation  # noqa: E402
from aura.hosts import MockSkill, SkillwareHost  # noqa: E402
from aura.membrane.egress import guarded_tool_call  # noqa: E402
from tests.spectrum_helpers import spectrum_block  # noqa: E402

SECRET = "tok_live_shop_x_card_y_99"
ATTACKER = "attacker-supplied-token-value"
BROKER = MapSecretBroker({"env:AURA_CAP_SHOP_X_CARD_Y": SECRET})
CAP = {
    "id": "shop-x-milk",
    "tool": "payment",
    "allowed": {"merchant": "shop-x", "item": "milk", "card": "Y"},
    "secret": {"ref": "env:AURA_CAP_SHOP_X_CARD_Y"},
}


@dataclass
class ScenarioResult:
    name: str
    coat: str
    passed: bool
    reason: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


def _assert(condition: bool, msg: Any) -> None:
    if not condition:
        raise AssertionError(str(msg))


def _kinds(session: Any) -> list[str]:
    return [e.kind for e in session.spine.stream()]


def _blob(session: Any) -> str:
    return json.dumps([e.to_dict() for e in session.spine.stream()])


def _codes(session: Any) -> set[str]:
    conf = ConformanceEngine().summarize(session.spine, session.declared_rules)
    report = AuditReportBuilder().build(session.spine, conf)
    return {str(f.get("code")) for f in report.findings if f.get("code")}


def _pay_agent(name: str, **kwargs: Any):
    kwargs.setdefault("capabilities", [CAP])
    kwargs.setdefault("spectrum", {"level": "mid", "services": ["audit"]})
    return agent(name, **kwargs)


def scenario_allow_inject() -> ScenarioResult:
    captured: dict[str, Any] = {}

    def pay(args: dict[str, Any]) -> dict[str, Any]:
        captured.update(args)
        return {"ok": True, "echo": args.get("token")}

    ag = _pay_agent("stress-cap-allow")
    with ag.session(export=True, secret_broker=BROKER) as run:
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
    blob = _blob(run._session)
    assert captured.get("token") == SECRET
    _assert(SECRET not in blob, "secret leaked on spine")
    _assert(result.get("ok") is True, result)
    _assert("capability.injected" in _kinds(run._session), _kinds(run._session))
    otel = Path(run.exports["otel"]).read_text(encoding="utf-8")
    _assert(SECRET not in otel, "secret leaked on otel")
    return ScenarioResult("capability_allow_inject", "tight", True, metrics={"injected": True})


def scenario_generic_github_scope() -> ScenarioResult:
    """Same model, different vertical: repo label + inject_as=api_key."""
    gh_secret = "ghp_ledger_read_not_a_payment_token"
    cap = {
        "id": "gh-ledger-read",
        "tool": "github.api",
        "allowed": {"repo": "acme/private-ledger", "item": "organic whole milk"},
        "secret": {"ref": "env:AURA_GH_TOKEN"},
        "inject_as": "api_key",
    }
    captured: dict[str, Any] = {}

    def github_api(args: dict[str, Any]) -> dict[str, Any]:
        captured.update(args)
        return {"ok": True}

    ag = agent(
        "stress-cap-github",
        capabilities=[cap],
        spectrum={"level": "mid", "services": ["audit"]},
    )
    broker = MapSecretBroker({"env:AURA_GH_TOKEN": gh_secret})
    with ag.session(export=False, secret_broker=broker) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("gh", {"github.api": github_api}))
        host.execute(
            "gh",
            "github.api",
            {
                "capability_id": "gh-ledger-read",
                "repo": "acme/private-ledger",
                "item": "organic whole milk",
            },
        )
        blocked = False
        try:
            host.execute(
                "gh",
                "github.api",
                {
                    "capability_id": "gh-ledger-read",
                    "repo": "acme/other-repo",
                    "item": "organic whole milk",
                },
            )
        except ConstraintViolation:
            blocked = True
    _assert(captured.get("api_key") == gh_secret, captured)
    _assert("token" not in captured, captured)
    _assert(blocked, "wrong repo must deny")
    _assert(gh_secret not in _blob(run._session), "github secret leaked")
    return ScenarioResult("capability_generic_github", "tight", True)


def scenario_deny_wrong_card() -> ScenarioResult:
    ran = {"n": 0}

    def pay(args: dict[str, Any]) -> dict[str, Any]:
        ran["n"] += 1
        return args

    ag = _pay_agent("stress-cap-deny")
    with ag.session(export=False, secret_broker=BROKER) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
        blocked = False
        try:
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
        except ConstraintViolation:
            blocked = True
    _assert(blocked, "expected block")
    _assert(ran["n"] == 0, ran)
    _assert("CAPABILITY_DENIED" in _codes(run._session), _codes(run._session))
    return ScenarioResult("capability_deny_wrong_card", "tight", True)


def scenario_low_audit_run() -> ScenarioResult:
    captured: dict[str, Any] = {}
    ran = {"n": 0}

    def pay(args: dict[str, Any]) -> dict[str, Any]:
        captured.update(args)
        ran["n"] += 1
        return {"ran": True}

    ag = _pay_agent("stress-cap-low", spectrum={"level": "low", "services": ["audit"]})
    with ag.session(export=False, secret_broker=BROKER) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
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
    _assert(ran["n"] == 1, ran)
    _assert("token" not in captured, captured)
    _assert("CAPABILITY_AUDIT" in _codes(run._session), _codes(run._session))
    return ScenarioResult("capability_low_audit", "loose", True)


def scenario_missing_id() -> ScenarioResult:
    ag = _pay_agent("stress-cap-missing")
    with ag.session(export=False, secret_broker=BROKER) as run:
        blocked = False
        try:
            run.emit("tool.call", {"tool": "payment", "args": {"item": "milk"}})
        except ConstraintViolation:
            blocked = True
    _assert(blocked, "missing id must deny")
    return ScenarioResult("capability_missing_id", "tight", True)


def scenario_unknown_id() -> ScenarioResult:
    ag = _pay_agent("stress-cap-unknown")
    with ag.session(export=False, secret_broker=BROKER) as run:
        blocked = False
        try:
            run.emit("tool.call", {"tool": "payment", "capability_id": "ghost"})
        except ConstraintViolation:
            blocked = True
    _assert(blocked, "unknown id must deny")
    return ScenarioResult("capability_unknown_id", "tight", True)


def scenario_token_bypass() -> ScenarioResult:
    captured: dict[str, Any] = {}

    def pay(args: dict[str, Any]) -> dict[str, Any]:
        captured.update(args)
        return {"echo": args.get("token")}

    ag = _pay_agent("stress-cap-bypass")
    with ag.session(export=False, secret_broker=BROKER) as run:
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
                "token": ATTACKER,
                "api_key": ATTACKER,
            },
        )
    blob = _blob(run._session)
    _assert(captured.get("token") == SECRET, captured)
    _assert(ATTACKER not in blob, "attacker token on spine")
    _assert(SECRET not in blob, "live secret on spine")
    return ScenarioResult("capability_token_bypass", "tight", True)


def scenario_ungated_and_extra_args() -> ScenarioResult:
    ag = _pay_agent("stress-cap-ungated")
    with ag.session(export=False, secret_broker=BROKER) as run:
        run.emit("tool.call", {"tool": "search.web", "query": "milk prices"})
        run.emit(
            "tool.call",
            {
                "tool": "payment",
                "capability_id": "shop-x-milk",
                "args": {
                    "merchant": "shop-x",
                    "item": "milk",
                    "card": "Y",
                    "note": "host metadata",
                },
            },
        )
    _assert("constraint.violated" not in _kinds(run._session), _kinds(run._session))
    return ScenarioResult("capability_ungated_extra", "tight", True)


def scenario_wildcard_and_nested() -> ScenarioResult:
    caps = [
        {
            "id": "flex",
            "tool": "order",
            "allowed": {"merchant.name": "shop-x", "item": "*", "qty": ["1", "2", 3]},
        }
    ]
    ag = agent("stress-cap-flex", capabilities=caps, spectrum={"level": "mid"})
    with ag.session(export=False) as run:
        run.emit(
            "tool.call",
            {
                "tool": "order",
                "capability_id": "flex",
                "args": {"merchant": {"name": "shop-x"}, "item": "bread", "qty": 3},
            },
        )
        blocked = False
        try:
            run.emit(
                "tool.call",
                {
                    "tool": "order",
                    "capability_id": "flex",
                    "args": {"merchant": {"name": "other"}, "item": "bread", "qty": 3},
                },
            )
        except ConstraintViolation:
            blocked = True
    _assert(blocked, "nested merchant must deny")
    return ScenarioResult("capability_wildcard_nested", "tight", True)


def scenario_conflict_ids() -> ScenarioResult:
    ag = _pay_agent("stress-cap-conflict")
    with ag.session(export=False, secret_broker=BROKER) as run:
        blocked = False
        try:
            run.emit(
                "tool.call",
                {
                    "tool": "payment",
                    "capability_id": "shop-x-milk",
                    "args": {"capability": "other", "item": "milk", "card": "Y"},
                },
            )
        except ConstraintViolation:
            blocked = True
    _assert(blocked, "conflicting ids must deny")
    return ScenarioResult("capability_conflict_ids", "tight", True)


def scenario_high_and_full() -> ScenarioResult:
    ag_high = agent(
        "stress-cap-high",
        capabilities=[CAP],
        spectrum=spectrum_block("high"),
    )
    with ag_high.session(export=False, secret_broker=BROKER) as run:
        run.emit(
            "tool.call",
            {
                "tool": "payment",
                "capability_id": "shop-x-milk",
                "args": {"merchant": "shop-x", "item": "milk", "card": "Y"},
            },
        )
    ag_full = agent(
        "stress-cap-full",
        capabilities=[CAP],
        spectrum=spectrum_block("full"),
        sequencer={"steps": [{"id": "pay", "type": "skill", "ref": "payment"}]},
    )
    with ag_full.session(export=False, secret_broker=BROKER) as run:
        blocked = False
        try:
            run.emit(
                "tool.call",
                {
                    "tool": "payment",
                    "capability_id": "shop-x-milk",
                    "args": {"merchant": "shop-x", "item": "milk", "card": "Y"},
                },
            )
        except ConstraintViolation:
            blocked = True
        _assert(blocked, "full requires step_id")
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
    return ScenarioResult("capability_high_full", "tailored", True)


def scenario_unresolved_secret() -> ScenarioResult:
    ag = _pay_agent("stress-cap-unresolved")
    with ag.session(export=False, secret_broker=MapSecretBroker({})) as run:
        failed = False
        try:
            guarded_tool_call(
                run._session,
                tool="payment",
                args={
                    "capability_id": "shop-x-milk",
                    "merchant": "shop-x",
                    "item": "milk",
                    "card": "Y",
                },
                execute=lambda live: live,
            )
        except SecretNotFoundError:
            failed = True
    _assert(failed, "missing broker value must fail")
    _assert("SECRET_BROKER_ERROR" in _codes(run._session), _codes(run._session))
    return ScenarioResult("capability_unresolved_secret", "tight", True)


def scenario_plaintext_rejected() -> ScenarioResult:
    raised = False
    try:
        agent(
            "stress-cap-plaintext",
            capabilities=[{"id": "x", "secret": {"value": "sk-live-nope-nope"}}],
        )
    except CapabilityConfigError:
        raised = True
    _assert(raised, "plaintext secret must be rejected at create")
    return ScenarioResult("capability_plaintext_rejected", "tight", True)


def scenario_escalation_on_deny() -> ScenarioResult:
    ag = agent(
        "stress-cap-esc",
        capabilities=[CAP],
        spectrum={"level": "mid"},
        escalations=[{"on": "constraint.violated", "actions": ["nudge"]}],
    )
    with ag.session(export=False, secret_broker=BROKER) as run:
        try:
            run.emit(
                "tool.call",
                {
                    "tool": "payment",
                    "capability_id": "shop-x-milk",
                    "args": {"merchant": "shop-x", "item": "milk", "card": "Z"},
                },
            )
        except ConstraintViolation:
            pass
    kinds = _kinds(run._session)
    _assert("escalation.fired" in kinds, kinds)
    _assert("membrane.nudge" in kinds, kinds)
    return ScenarioResult("capability_escalation", "tight", True)


def scenario_result_leak() -> ScenarioResult:
    def pay(args: dict[str, Any]) -> dict[str, Any]:
        return {"receipt": f"paid {args['token']}"}

    ag = _pay_agent("stress-cap-leak")
    with ag.session(export=True, secret_broker=BROKER) as run:
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
    jsonl = Path(run.exports["jsonl"]).read_text(encoding="utf-8")
    summary = Path(run.exports["summary"]).read_text(encoding="utf-8")
    _assert(SECRET not in jsonl, "jsonl leak")
    _assert(SECRET not in summary, "summary leak")
    return ScenarioResult("capability_result_leak", "tight", True)


def scenario_empty_capabilities_compat() -> ScenarioResult:
    ag = agent("stress-cap-empty", spectrum={"level": "mid"})
    with ag.session(export=False) as run:
        run.emit("tool.call", {"tool": "legacy.tool", "args": {"q": 1}})
    _assert("tool.call" in _kinds(run._session), _kinds(run._session))
    return ScenarioResult("capability_empty_compat", "tight", True)


SCENARIOS: list[tuple[str, Callable[[], ScenarioResult]]] = [
    ("allow inject", scenario_allow_inject),
    ("generic github scope", scenario_generic_github_scope),
    ("deny wrong card", scenario_deny_wrong_card),
    ("low audit", scenario_low_audit_run),
    ("missing id", scenario_missing_id),
    ("unknown id", scenario_unknown_id),
    ("token bypass", scenario_token_bypass),
    ("ungated extra", scenario_ungated_and_extra_args),
    ("wildcard nested", scenario_wildcard_and_nested),
    ("conflict ids", scenario_conflict_ids),
    ("high and full", scenario_high_and_full),
    ("unresolved secret", scenario_unresolved_secret),
    ("plaintext rejected", scenario_plaintext_rejected),
    ("escalation on deny", scenario_escalation_on_deny),
    ("result leak", scenario_result_leak),
    ("empty compat", scenario_empty_capabilities_compat),
]


def run_all() -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    for label, fn in SCENARIOS:
        try:
            results.append(fn())
        except Exception as exc:
            results.append(
                ScenarioResult(
                    name=getattr(fn, "__name__", label),
                    coat="?",
                    passed=False,
                    reason=str(exc),
                )
            )
    return results


def main() -> int:
    home = tempfile.mkdtemp(prefix="aura_cap_stress_")
    os.environ["AURA_HOME"] = home
    configure()
    results = run_all()
    failed = [r for r in results if not r.passed]
    report = {
        "aura_home": home,
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": len(failed),
        "scenarios": [
            {
                "name": r.name,
                "coat": r.coat,
                "passed": r.passed,
                "reason": r.reason,
                "metrics": r.metrics,
            }
            for r in results
        ],
    }
    print(json.dumps(report, indent=2, default=str))
    if failed:
        print("\nFAILED:", ", ".join(r.name for r in failed), file=sys.stderr)
        return 1
    print(f"\nALL CAPABILITY SCENARIOS PASSED ({len(results)} run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
