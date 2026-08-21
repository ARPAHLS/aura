"""Additional coverage for config, export, runtime, registry, and spine gaps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from aura import agent
from aura.agents.registry import AgentRegistry
from aura.config import AuraConfig, configure, get_config
from aura.core.compare import compare_sessions, load_summary
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


def test_configure_overrides(aura_home: Path):
    configure(export_on_close=False)
    assert get_config().values["export_on_close"] is False


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
    assert verify_hash_chain_dicts(rows) is False
    assert verify_hash_chain(spine) is True


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
