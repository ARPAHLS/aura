"""Audit pipeline — session export, audit report, compare, OTel, and hash-chain verify.

Host-agnostic loop using MockSkill + SkillwareHost (reference ToolHost adapter).
Runs two short sessions and compares summaries programmatically; prints CLI follow-ups.

From repo root:
  pip install -e ".[dev]"
  python examples/audit_pipeline.py

Then inspect receipt artifacts:
  aura report show <session_id>
  aura export <session_id>
  aura export-otel <session_id>
  aura compare <session_a> <session_b>
  aura verify chain ~/.aura/sessions/<session_id>.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

from aura import agent, configure
from aura.core.compare import compare_sessions
from aura.core.spine import AuditSpine, verify_hash_chain
from aura.hosts import MockSkill, SkillwareHost


def _run_session(label: str, query: str) -> tuple[str, Path, Path]:
    ag = agent(
        f"audit-pipeline-{label}",
        agent_ref=f"demo/audit-pipeline-{label}",
        purpose="Demonstrate export slice and audit report receipt",
        skills=["research"],
    )
    with ag.session(mode="script") as run:
        host = SkillwareHost(run._session)
        host.register(
            MockSkill(
                "research",
                {"search": lambda args: {"hits": 1, "query": args.get("query")}},
                manifest={"name": "research", "version": "0.0.1"},
            )
        )
        run.emit("turn.start", {"input": query})
        host.execute("research", "search", {"query": query})
        run.emit("turn.end", {"output": "done", "tokens": 12})

    jsonl = Path(run.exports["jsonl"])
    summary = Path(run.exports["summary"])
    return run.session_id, jsonl, summary


def main() -> None:
    configure()

    session_a, jsonl_a, summary_a = _run_session("a", "compliance export slice")
    session_b, _, summary_b = _run_session("b", "compliance export slice rerun")

    summary_payload = json.loads(summary_a.read_text(encoding="utf-8"))
    audit_report = summary_payload.get("audit_report") or {}
    compare = compare_sessions(summary_a, summary_b)
    chain_ok = verify_hash_chain(AuditSpine.from_jsonl(jsonl_a))
    otel_path = summary_a.with_name(f"{session_a}.otel.jsonl")

    print(
        json.dumps(
            {
                "session_a": session_a,
                "session_b": session_b,
                "agent_ref": summary_payload.get("agent_ref"),
                "audit_verdict": audit_report.get("verdict"),
                "hash_chain_valid": audit_report.get("hash_chain_valid"),
                "verify_chain_cli": chain_ok,
                "compare_same_verdict": compare.get("audit_verdict", {}).get("same"),
                "jsonl": str(jsonl_a),
            },
            indent=2,
        )
    )
    print("session:", session_a)
    print(
        "exports:",
        {"jsonl": str(jsonl_a), "summary": str(summary_a), "otel": str(otel_path)},
    )
    print("cli:")
    print(f"  aura report show {session_a}")
    print(f"  aura export {session_a}")
    print(f"  aura export-otel {session_a}")
    print(f"  aura compare {session_a} {session_b}")
    print(f"  aura verify chain {jsonl_a}")


if __name__ == "__main__":
    main()
