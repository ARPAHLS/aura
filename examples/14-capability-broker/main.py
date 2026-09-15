"""Example 14 — Capability broker: named intent, scope check, secret inject (#48)."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from aura import MapSecretBroker, agent, configure
from aura.core.audit_report import AuditReportBuilder
from aura.core.conformance import ConformanceEngine
from aura.core.constraints import ConstraintViolation
from aura.core.payload_redaction import REDACTED
from aura.hosts import MockSkill, SkillwareHost

ScenarioFn = Callable[[], dict[str, Any]]

SECRET = "tok_live_shop_x_card_y_99"
BROKER = MapSecretBroker({"env:AURA_CAP_SHOP_X_CARD_Y": SECRET})
CAP = {
    "id": "shop-x-milk",
    "tool": "payment",
    "allowed": {"merchant": "shop-x", "item": "milk", "card": "Y"},
    "secret": {"ref": "env:AURA_CAP_SHOP_X_CARD_Y"},
}


def _report(session) -> dict[str, Any]:
    kinds = [e.kind for e in session.spine.stream()]
    conf = ConformanceEngine().summarize(session.spine, session.declared_rules)
    report = AuditReportBuilder().build(session.spine, conf)
    blob = json.dumps([e.to_dict() for e in session.spine.stream()])
    return {
        "kinds": kinds,
        "audit_verdict": report.verdict,
        "finding_codes": sorted({f.get("code") for f in report.findings if f.get("code")}),
        "secret_on_spine": SECRET in blob,
        "redacted_marker": REDACTED in blob,
    }


def scenario_allow_inject() -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def pay(args: dict[str, Any]) -> dict[str, Any]:
        captured.update(args)
        return {"charged": True, "echo": args.get("token")}

    ag = agent(
        "cap-demo-allow",
        capabilities=[CAP],
        spectrum={"level": "mid", "services": ["audit"]},
    )
    with ag.session(secret_broker=BROKER) as run:
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
    summary = _report(run._session)
    return {
        "scenario": "allow_inject",
        "session_id": run.session_id,
        "injected": captured.get("token") == SECRET,
        "result_ok": result.get("charged") is True,
        **summary,
    }


def scenario_deny_wrong_card() -> dict[str, Any]:
    ran = {"n": 0}

    def pay(args: dict[str, Any]) -> dict[str, Any]:
        ran["n"] += 1
        return {"charged": True}

    ag = agent(
        "cap-demo-deny",
        capabilities=[CAP],
        spectrum={"level": "mid", "services": ["audit"]},
    )
    blocked = False
    with ag.session(secret_broker=BROKER) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("pay", {"payment": pay}))
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
    summary = _report(run._session)
    return {
        "scenario": "deny_wrong_card",
        "session_id": run.session_id,
        "blocked": blocked,
        "executed": ran["n"],
        **summary,
    }


def scenario_low_audit() -> dict[str, Any]:
    ran = {"n": 0}

    def pay(args: dict[str, Any]) -> dict[str, Any]:
        ran["n"] += 1
        return {"ran": True, "had_token": "token" in args}

    ag = agent(
        "cap-demo-low",
        capabilities=[CAP],
        spectrum={"level": "low", "services": ["audit"]},
    )
    with ag.session(secret_broker=BROKER) as run:
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
    summary = _report(run._session)
    return {
        "scenario": "low_audit",
        "session_id": run.session_id,
        "executed": ran["n"],
        **summary,
    }


def scenario_missing_id() -> dict[str, Any]:
    ag = agent(
        "cap-demo-missing",
        capabilities=[CAP],
        spectrum={"level": "mid", "services": ["audit"]},
    )
    blocked = False
    with ag.session(secret_broker=BROKER) as run:
        try:
            run.emit("tool.call", {"tool": "payment", "args": {"item": "milk", "card": "Y"}})
        except ConstraintViolation:
            blocked = True
    summary = _report(run._session)
    return {
        "scenario": "missing_id",
        "session_id": run.session_id,
        "blocked": blocked,
        **summary,
    }


SCENARIOS: dict[str, ScenarioFn] = {
    "allow_inject": scenario_allow_inject,
    "deny_wrong_card": scenario_deny_wrong_card,
    "low_audit": scenario_low_audit,
    "missing_id": scenario_missing_id,
}


def main() -> None:
    configure()
    selected = os.environ.get("CAPABILITY_SCENARIO", "all").strip().lower()
    if selected == "all":
        results = [fn() for fn in SCENARIOS.values()]
    elif selected in SCENARIOS:
        results = [SCENARIOS[selected]()]
    else:
        known = ", ".join(sorted(SCENARIOS))
        raise SystemExit(f"Unknown CAPABILITY_SCENARIO={selected!r}. Choose: all, {known}")
    print(json.dumps(results, indent=2))
    print(f"session count: {len(results)}")


if __name__ == "__main__":
    main()
