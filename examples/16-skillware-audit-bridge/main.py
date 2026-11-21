"""Example 16 — Skillware 0.6.2+ audit bridge, FinOps telemetry, Manifest v2 safety, and async."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import tempfile

from aura import ApprovalRequired, agent, configure
from aura.hosts import (
    MockSkill,
    SkillwareHost,
    skillware_capabilities,
    verify_dual_audit_chain,
)


def _live() -> bool:
    return os.environ.get("SKILLWARE_LIVE", "").strip().lower() in ("1", "true", "yes")


async def _run_demo() -> dict:
    configure()
    caps = skillware_capabilities()
    live = _live() and caps["installed"] and caps["audit_hook"]
    mode = "live" if live else "mock"

    ag = agent(
        "skillware-audit-bridge-demo",
        purpose="Skillware 0.6.2+ dispatch audit bridge, FinOps, Manifest v2, and async",
        skills=["optimization/prompt_rewriter", "robotics/arm_mover"],
        observers=[
            {
                "preset": "limit",
                "id": "finops-guard",
                "config": {"max_cost_usd": 0.05, "warn_ratio": 0.7},
            }
        ],
    )

    dual_status = None
    with tempfile.TemporaryDirectory() as tmpdir:
        sw_log = Path(tmpdir) / "skillware_audit.jsonl"

        with ag.session(mode="script", export=True) as run:
            if live:
                host = SkillwareHost.create_context(
                    run._session,
                    skills=["optimization/prompt_rewriter"],
                    audit_log_path=sw_log,
                    max_concurrency=4,
                )
            else:
                host = SkillwareHost(run._session, max_concurrency=4)
                host.register(
                    MockSkill(
                        "optimization/prompt_rewriter",
                        {
                            "optimization/prompt_rewriter": lambda a: {
                                "compressed_text": str(a.get("raw_text", ""))[:42],
                                "tokens_saved": 6,
                                "provenance": {"report_hash": "a" * 64},
                            }
                        },
                        manifest={
                            "name": "optimization/prompt_rewriter",
                            "version": "1.0.0",
                            "description": "Compress verbose prompts",
                            "shape": "atomic",
                            "tier": "core",
                            "target": ["software"],
                            "tags": ["optimization"],
                        },
                    )
                )

            # 1) Async execution through AURA egress with FinOps audit_meta
            rewrite = await host.aexecute(
                "optimization/prompt_rewriter",
                "optimization/prompt_rewriter",
                {
                    "raw_text": "Please kindly summarize the compliance brief cleanly.",
                    "compression_aggression": "high",
                },
                audit_meta={
                    "model": "gpt-4o-mini",
                    "prompt_tokens": 800,
                    "completion_tokens": 200,
                },
            )

            # 2) Manifest v2 physical-substrate safety gate (hardware requires operator approval)
            host.register(
                MockSkill(
                    "robotics/arm_mover",
                    {"robotics/arm_mover": lambda a: {"moved": True, "axis": a.get("axis")}},
                    manifest={
                        "name": "robotics/arm_mover",
                        "version": "0.1.0",
                        "description": "Actuate physical hardware arm",
                        "shape": "atomic",
                        "tier": "enterprise",
                        "target": ["hardware"],
                        "tags": ["robotics"],
                    },
                )
            )
            try:
                host.execute("robotics/arm_mover", "robotics/arm_mover", {"axis": "z"})
            except ApprovalRequired as exc:
                run.approve(exc.request_id, principal="safety-officer@example.com")
                hw_res = host.execute("robotics/arm_mover", "robotics/arm_mover", {"axis": "z"})

            run.emit("turn.end", {"output": "audit bridge demo complete", "mode": mode})

        if live and sw_log.is_file():
            dual_status = verify_dual_audit_chain(run.exports["jsonl"], sw_log).to_dict()

    return {
        "mode": mode,
        "session_id": run.session_id,
        "rewrite": rewrite,
        "hardware_result": hw_res,
        "finops": (run.audit_report or {}).get("scorecard", {}).get("finops"),
        "verdict": (run.audit_report or {}).get("verdict"),
        "dual_ledger": dual_status,
        "exports": run.exports,
    }


def main() -> None:
    output = asyncio.run(_run_demo())
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
