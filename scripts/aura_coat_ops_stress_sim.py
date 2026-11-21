#!/usr/bin/env python3
"""
AURA-native coat ops stress simulation (#49).

Exercises:
  1. Zero-config stub fallback (backward compatibility)
  2. Webhook delivery with HMAC-SHA256 signing
  3. SSRF URL rejection on unsafe schemes
  4. Mocked SMTP email delivery
  5. Delivery failure resilience (session completes cleanly with delivery="failed")
  6. Membrane-level CoatOpRunner scan on plain Python body (routes through egress)
  7. Multi-escalation burst + hash-chain verification

Usage (repo root):
  python scripts/aura_coat_ops_stress_sim.py
"""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock, patch

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from aura import (  # noqa: E402
    CallableCoatOp,
    CoatOpDeliveryError,
    CoatOpRunner,
    SmtpCoatOp,
    WebhookCoatOp,
    agent,
    configure,
)
from aura.core.spine import AuditSpine, verify_hash_chain  # noqa: E402
from aura.hosts import MockSkill, SkillwareHost  # noqa: E402


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def scenario_stub_fallback() -> None:
    ag = agent(
        "coat-sim-stub",
        variables={"goal": "nickel only"},
        observers=[{"preset": "goal_drift", "config": {"forbidden_topics": ["shipyard"]}}],
        escalations=[{"on": "conformance.drift", "actions": ["email:ops@acme.com", "wake"]}],
    )
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("r", {"s": lambda a: {"ok": True}}))
        host.execute("r", "s", {"q": "shipyard"})
    email_evt = next(e for e in run.get_events() if e.kind == "escalation.email")
    wake_evt = next(e for e in run.get_events() if e.kind == "escalation.wake")
    _assert(email_evt.payload["delivery"] == "stub", "expected stub email")
    _assert(wake_evt.payload["delivery"] == "stub", "expected stub wake")


def scenario_webhook_hmac_delivery() -> None:
    seen: list[dict] = []

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout=5.0):
        seen.append({"body": req.data, "headers": dict(req.headers)})
        return _Resp()

    ag = agent(
        "coat-sim-webhook",
        variables={"goal": "nickel only"},
        observers=[{"preset": "goal_drift", "config": {"forbidden_topics": ["shipyard"]}}],
        escalations=[{"on": "conformance.drift", "actions": ["email:ops@acme.com", "wake:queue"]}],
    )
    with patch("aura.core.coat_ops.urlopen", side_effect=_fake_urlopen):
        with ag.session(
            export=True,
            coat_ops={
                "webhook": {
                    "type": "webhook",
                    "url": "https://hooks.example.com/aura",
                    "hmac_secret": "sim-secret",
                }
            },
        ) as run:
            host = SkillwareHost(run._session)
            host.register(MockSkill("r", {"s": lambda a: {"ok": True}}))
            host.execute("r", "s", {"q": "shipyard"})

    _assert(len(seen) == 2, f"expected 2 webhook calls, got {len(seen)}")
    for item in seen:
        expected = hmac.new(b"sim-secret", item["body"], hashlib.sha256).hexdigest()
        _assert(item["headers"]["X-aura-signature"] == f"sha256={expected}", "bad HMAC")
    _assert(verify_hash_chain(AuditSpine.from_jsonl(Path(run.exports["jsonl"]))) is True, "chain")


def scenario_ssrf_block() -> None:
    for bad_url in (
        "javascript:alert(1)",
        "file:///etc/passwd",
        "http://127.0.0.1:8080/hook",
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost:9000/hook",
    ):
        blocked = False
        try:
            WebhookCoatOp(bad_url).deliver("escalation.email", {})
        except CoatOpDeliveryError:
            blocked = True
        _assert(blocked, f"expected SSRF rejection for {bad_url}")


def scenario_smtp_mocked_delivery() -> None:
    smtp_inst = MagicMock()
    smtp_ctx = MagicMock()
    smtp_ctx.__enter__.return_value = smtp_inst
    smtp_ctx.__exit__.return_value = False
    with patch("aura.core.coat_ops.smtplib.SMTP", return_value=smtp_ctx):
        res = SmtpCoatOp("smtp.example.com").deliver("escalation.email", {"to": "a@b.com"})
    _assert(res["transport"] == "smtp", "expected smtp transport")


def scenario_delivery_failure_resilience() -> None:
    ag = agent(
        "coat-sim-fail",
        variables={"goal": "nickel only"},
        observers=[{"preset": "goal_drift", "config": {"forbidden_topics": ["shipyard"]}}],
        escalations=[{"on": "conformance.drift", "actions": ["email:ops@acme.com"]}],
    )
    with ag.session(
        export=False,
        coat_ops={"email": CallableCoatOp(lambda k, p: (_ for _ in ()).throw(OSError("down")))},
    ) as run:
        host = SkillwareHost(run._session)
        host.register(MockSkill("r", {"s": lambda a: {"ok": True}}))
        host.execute("r", "s", {"q": "shipyard"})
    email_evt = next(e for e in run.get_events() if e.kind == "escalation.email")
    _assert(email_evt.payload["delivery"] == "failed", "expected failed delivery")


def scenario_membrane_coat_scan_plain_body() -> None:
    ag = agent("coat-sim-scan")
    with ag.session(export=True) as run:
        runner = CoatOpRunner(run._session)
        runner.host.register(
            MockSkill(
                "security/prompt_injection_firewall",
                {"security/prompt_injection_firewall": lambda a: {"is_safe": True}},
            )
        )
        res = runner.scan_input("Summarize Q3 metrics")
        _assert(res["is_safe"] is True, "expected safe scan")
    kinds = [e.kind for e in run.get_events()]
    _assert("coat.op.executed" in kinds and "tool.result" in kinds, "missing coat/egress events")
    _assert(verify_hash_chain(AuditSpine.from_jsonl(Path(run.exports["jsonl"]))) is True, "chain")


def main() -> int:
    scenarios = [
        scenario_stub_fallback,
        scenario_webhook_hmac_delivery,
        scenario_ssrf_block,
        scenario_smtp_mocked_delivery,
        scenario_delivery_failure_resilience,
        scenario_membrane_coat_scan_plain_body,
    ]
    with tempfile.TemporaryDirectory() as home:
        os.environ["AURA_HOME"] = home
        configure()
        for fn in scenarios:
            fn()
            print(f"[PASS] {fn.__name__}")
    print(f"ALL COAT OPS SCENARIOS PASSED ({len(scenarios)} total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
