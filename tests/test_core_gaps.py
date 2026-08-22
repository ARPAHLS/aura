"""Additional coverage for config, export, runtime, registry, and spine gaps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from aura import agent
from aura.agents.registry import AgentRegistry
from aura.config import (
    AuraConfig,
    configure,
    config_sources,
    get_config,
    reload_config,
    save_project_config,
)
from aura.core.audit_report import AuditReportBuilder
from aura.core.compare import compare_sessions, load_summary
from aura.core.constraints import ConstraintContext, ConstraintEngine, ConstraintViolation
from aura.core.conformance import ConformanceEngine
from aura.core.spine import AuditSpine, verify_hash_chain, verify_hash_chain_dicts
from aura.exporters.jsonl import export_session
from aura.exporters.otel import export_otel_jsonl, export_session_otel, events_to_spans
from aura.hosts.skillware import SkillwareHost
from aura.runtime.python import aura_wrapped, run_script
from aura.sequencer.middleware import MiddlewarePolicy, MiddlewareStack


def test_config_merge_global_and_project(aura_home: Path, project_dir: Path):
    (aura_home / "config.yaml").write_text(
        yaml.dump({"default_session_mode": "task"}),
        encoding="utf-8",
    )
    (project_dir / "aura.project.yaml").write_text(
        yaml.dump({"storage": "project", "export_on_close": False}),
        encoding="utf-8",
    )
    cfg = AuraConfig(home=aura_home, project_dir=project_dir)
    assert cfg.values["default_session_mode"] == "task"
    assert cfg.values["storage"] == "project"
    assert cfg.values["export_on_close"] is False
    assert cfg.project_aura_dir == project_dir / ".aura"
    sessions = cfg.sessions_dir()
    assert str(project_dir) in str(sessions)


def test_config_sources_layers(aura_home: Path, project_dir: Path):
    (aura_home / "config.yaml").write_text(yaml.dump({"export_on_close": True}), encoding="utf-8")
    (project_dir / "aura.project.yaml").write_text(
        yaml.dump({"storage": "project"}), encoding="utf-8"
    )
    cfg = AuraConfig(home=aura_home, project_dir=project_dir)
    layers = dict((label, loaded) for label, _path, loaded in config_sources(cfg))
    assert layers["global"] is True
    assert layers["project"] is True


def test_configure_overrides(aura_home: Path):
    configure(export_on_close=False)
    assert get_config().values["export_on_close"] is False


def test_registry_ulid_and_legacy_coexist(aura_home: Path):
    reg = AgentRegistry()
    legacy = reg.create(name="legacy", aura_id="AURA-0042", agent_ref="team/legacy")
    modern = reg.create(name="modern", agent_ref="team/modern")
    assert legacy.aura_id == "AURA-0042"
    assert modern.aura_id != legacy.aura_id
    assert reg.get_by_id("AURA-0042").name == "legacy"
    assert reg.resolve("team/modern").aura_id == modern.aura_id


def test_registry_legacy_aura_id_and_archive(aura_home: Path):
    reg = AgentRegistry()
    legacy = reg.create(name="legacy-bot", aura_id="AURA-0001", agent_ref="legacy/bot")
    assert reg.get_by_id("AURA-0001").aura_id == legacy.aura_id
    assert reg.resolve("legacy/bot").name == "legacy-bot"

    reg.archive("AURA-0001")
    archived = reg.get_by_id("AURA-0001")
    assert archived.archived is True
    assert reg.list_agents() == []
    assert len(reg.list_agents(include_archived=True)) == 1

    reg.create(name="legacy-bot", agent_ref="legacy/bot")
    assert reg.resolve("legacy/bot").archived is False


def test_registry_archive_frees_name_and_ref(aura_home: Path):
    reg = AgentRegistry()
    first = reg.create(name="reuse", agent_ref="team/reuse")
    reg.archive(first.aura_id)
    second = reg.create(name="reuse", agent_ref="team/reuse")
    assert second.aura_id != first.aura_id


def test_hash_chain_detects_tamper(tmp_path: Path):
    log = tmp_path / "tampered.jsonl"
    spine = AuditSpine("sess-t", "AGENT-1", log_path=log)
    spine.append("turn.start", {})
    spine.append("turn.end", {})
    rows = AuditSpine.read_jsonl(log)
    rows[1]["content_hash"] = "0" * 64
    log.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    assert verify_hash_chain_dicts(rows) is False
    assert verify_hash_chain(spine) is True
    reloaded = AuditSpine.from_jsonl(log)
    assert verify_hash_chain(reloaded) is False


def test_audit_report_reflects_tampered_jsonl(aura_home: Path):
    ag = agent("tamper-report")
    with ag.session() as run:
        run.emit("turn.start", {})
        run.emit("turn.end", {})
    log_path = Path(run.exports["jsonl"])
    rows = AuditSpine.read_jsonl(log_path)
    rows[1]["content_hash"] = "0" * 64
    log_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )

    spine = AuditSpine.from_jsonl(log_path)
    conf = ConformanceEngine().summarize(spine, ag.profile.rules)
    report = AuditReportBuilder().build(spine, conf, agent_ref=ag.profile.agent_ref)
    assert report.hash_chain_valid is False
    assert report.verdict in ("warn", "fail")
    assert any(f["code"] == "HASH_CHAIN_BROKEN" for f in report.findings)


def test_constraint_matrix_allow_deny_and_tokens():
    engine = ConstraintEngine()
    allow_rule = [{"type": "allow_tools", "tools": ["search.web", "gmail.draft"]}]
    deny_rule = [{"type": "deny_tools", "deny": ["shell.exec"]}]

    allowed = engine.evaluate(
        ConstraintContext(
            event_kind="tool.call",
            payload={"tool": "search.web"},
            rules=allow_rule,
            session_state={},
        )
    )
    assert allowed[0].passed is True

    blocked = engine.evaluate(
        ConstraintContext(
            event_kind="tool.call",
            payload={"tool": "shell.exec"},
            rules=allow_rule,
            session_state={},
        )
    )
    assert blocked[0].blocked is True

    denied = engine.evaluate(
        ConstraintContext(
            event_kind="tool.call",
            payload={"tool": "shell.exec"},
            rules=deny_rule,
            session_state={},
        )
    )
    assert denied[0].blocked is True

    at_limit = engine.evaluate(
        ConstraintContext(
            event_kind="turn.end",
            payload={"tokens": 100},
            rules=[{"type": "max_tokens_per_step", "limit": 100}],
            session_state={},
        )
    )
    assert at_limit[0].passed is True

    over_limit = engine.evaluate(
        ConstraintContext(
            event_kind="turn.end",
            payload={"tokens": 101},
            rules=[{"type": "max_tokens_per_step", "limit": 100}],
            session_state={},
        )
    )
    assert over_limit[0].blocked is True


def test_constraint_allow_tools_session_emit(aura_home: Path):
    ag = agent("allow-matrix", rules=[{"type": "allow_tools", "tools": ["ok.tool"]}])
    with ag.session(export=False) as run:
        run.emit("tool.call", {"tool": "ok.tool"})
        with pytest.raises(ConstraintViolation):
            run.emit("tool.call", {"tool": "bad.tool"})


def test_compare_sessions_edge_cases(aura_home: Path):
    ag = agent("cmp-edges", policy_version="1")
    with ag.session() as run_a:
        run_a.emit("turn.start", {})
    with ag.session() as run_b:
        run_b.emit("turn.start", {})
        run_b.emit("turn.end", {})

    path_a = Path(run_a.exports["summary"])
    path_b = Path(run_b.exports["summary"])

    result = compare_sessions(path_a, path_b)
    assert result["conformance"]["same"] is True
    assert result["audit_verdict"]["same"] is True
    assert result["policy_version"]["a"] == "1"
    assert result["event_count"]["delta"] == 1

    with pytest.raises(FileNotFoundError):
        compare_sessions(path_a, path_a.parent / "missing.summary.json")


def test_compare_mismatched_agent_ref_and_hash_chain(aura_home: Path):
    ag_a = agent("cmp-a", agent_ref="team/a")
    ag_b = agent("cmp-b", agent_ref="team/b")
    with ag_a.session() as run_a:
        pass
    with ag_b.session() as run_b:
        run_b.emit("turn.start", {})

    path_a = Path(run_a.exports["summary"])
    path_b = Path(run_b.exports["summary"])
    result = compare_sessions(path_a, path_b)
    assert result["agent_ref"]["same"] is False
    assert result["agent_ref_a"] == "team/a"
    assert result["agent_ref_b"] == "team/b"
    assert result["hash_chain_valid"]["same"] is True
    assert result["event_count"]["delta"] == 1

    summary_b = json.loads(path_b.read_text(encoding="utf-8"))
    summary_b["audit_report"]["hash_chain_valid"] = False
    tampered_b = path_b.parent / "tampered.summary.json"
    tampered_b.write_text(json.dumps(summary_b), encoding="utf-8")
    diff = compare_sessions(path_a, tampered_b)
    assert diff["hash_chain_valid"]["same"] is False
    assert diff["hash_chain_valid"]["a"] is True
    assert diff["hash_chain_valid"]["b"] is False


def test_compare_empty_sessions(aura_home: Path):
    ag = agent("cmp-empty")
    with ag.session() as run_a:
        pass
    with ag.session() as run_b:
        pass
    result = compare_sessions(Path(run_a.exports["summary"]), Path(run_b.exports["summary"]))
    assert result["event_count"]["delta"] == 0
    assert result["conformance"]["same"] is True


def test_load_summary_roundtrip(aura_home: Path):
    ag = agent("summary-load")
    with ag.session() as run:
        run.emit("turn.start", {})
    path = Path(run.exports["summary"])
    data = load_summary(path)
    assert data["session_id"] == run.session_id


def test_export_session_writes_summary_and_otel(aura_home: Path):
    ag = agent("export-direct", agent_ref="ex/direct", policy_version="3")
    with ag.session(export=False) as run:
        run.emit("turn.start", {})
        run.emit("turn.end", {"tokens": 2})
        from aura.core.conformance import ConformanceEngine

        conf = ConformanceEngine().summarize(run._session.spine, run._session.rules)
        paths = export_session(run._session, aura_home / "sessions", conformance=conf)
    assert Path(paths["summary"]).is_file()
    assert Path(paths["jsonl"]).is_file()
    assert Path(paths["otel"]).is_file()
    summary = json.loads(Path(paths["summary"]).read_text(encoding="utf-8"))
    assert summary["mode"] == "script"
    assert summary["audit_report"]["verdict"] == "pass"


def test_otel_export_session_and_spans(aura_home: Path):
    ag = agent("otel-gap", policy_version="9")
    with ag.session() as run:
        run.emit("turn.start", {"note": "x"})
    otel_path = export_session_otel(run.session_id, aura_home / "sessions")
    assert otel_path.is_file()
    lines = otel_path.read_text(encoding="utf-8").strip().splitlines()
    span = json.loads(lines[0])
    assert span["name"] == "membrane.ingress" or span["name"] in {
        "membrane.ingress",
        "session.open",
        "turn.start",
    }
    events = AuditSpine.read_jsonl(aura_home / "sessions" / f"{run.session_id}.jsonl")
    spans = events_to_spans(events)
    assert len(spans) == len(events)
    export_otel_jsonl(events, aura_home / "sessions" / "manual.otel.jsonl")
    assert (aura_home / "sessions" / "manual.otel.jsonl").is_file()


def test_session_script_mode_export(aura_home: Path):
    ag = agent("script-mode", default_mode="script")
    with ag.session(mode="script") as run:
        run.emit("turn.start", {})
        run.emit("turn.end", {"tokens": 1})
    summary = json.loads(Path(run.exports["summary"]).read_text(encoding="utf-8"))
    assert summary["mode"] == "script"
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "task.complete" not in kinds


def test_session_export_uses_project_storage(aura_home: Path, project_dir: Path):
    save_project_config({"storage": "project"}, project_dir)
    reload_config(project_dir=project_dir)
    ag = agent("proj-storage")
    with ag.session() as run:
        run.emit("turn.start", {})
    assert str(project_dir / ".aura" / "sessions") in run.exports["summary"]


def test_session_task_mode_goal(aura_home: Path):
    ag = agent("task-mode", default_mode="task")
    with ag.session(mode="task") as run:
        run.emit("task.start", {"goal": "demo"})
        run.complete_goal({"status": "done"})
    summary = json.loads(Path(run.exports["summary"]).read_text(encoding="utf-8"))
    assert summary["mode"] == "task"
    kinds = [e.kind for e in run._session.spine.stream()]
    assert "task.complete" in kinds


def test_session_continuous_mode(aura_home: Path):
    ag = agent("continuous-mode", default_mode="continuous")
    with ag.session(mode="continuous") as run:
        run.emit("turn.start", {})
    summary = json.loads(Path(run.exports["summary"]).read_text(encoding="utf-8"))
    assert summary["mode"] == "continuous"


def test_runtime_run_script_and_wrapper(aura_home: Path, tmp_path: Path):
    script = tmp_path / "sample.py"
    script.write_text(
        "RESULT = 40 + 2\n",
        encoding="utf-8",
    )
    handle = agent("runtime-script")
    out = run_script(handle, script)
    assert out["session_id"].startswith("aura_sess_")
    assert "summary" in out["exports"]

    @aura_wrapped(handle)
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5


def test_middleware_policy_and_stack():
    assert MiddlewarePolicy.from_manifest({}) is None
    policy = MiddlewarePolicy.from_manifest(
        {"middleware": {"scope": "per_step", "order": [{"op": "noop", "config": {}}]}}
    )
    assert policy is not None
    assert policy.scope == "per_step"
    stack = MiddlewareStack(policy)
    assert stack.run_inbound({"value": 1}) == {"value": 1}


def test_skillware_host_register_by_id_and_missing(aura_home: Path):
    ag = agent("host-gap")
    with ag.session(export=False) as run:
        host = SkillwareHost(run._session)

        class _Skill:
            skill_id = "wrapped"

            def execute(self, tool: str, args=None):
                return {"tool": tool}

        host.register_by_id("wrapped", _Skill())
        assert host.execute("wrapped", "ping", {}) == {"tool": "ping"}

        with pytest.raises(KeyError, match="not registered"):
            host.execute("missing", "ping", {})


@pytest.mark.skillware
def test_skillware_extra_import():
    pytest.importorskip("skillware")
