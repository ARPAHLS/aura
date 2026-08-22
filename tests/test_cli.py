"""CLI integration tests."""

from __future__ import annotations

import json
from pathlib import Path

from aura import agent
from aura.core.spine import AuditSpine


def test_cli_version(run_aura):
    result = run_aura("version")
    assert result.returncode == 0
    assert "aura-harness" in result.stdout
    assert "0.3." in result.stdout


def test_cli_agent_create_list_show(run_aura):
    create = run_aura(
        "agent",
        "create",
        "demo-bot",
        "--ref",
        "acme/demo",
        "--policy-version",
        "2",
    )
    assert create.returncode == 0
    data = json.loads(create.stdout)
    assert data["agent_ref"] == "acme/demo"
    assert data["policy_version"] == "2"

    listing = run_aura("agent", "list")
    assert listing.returncode == 0
    assert "acme/demo" in listing.stdout
    assert "demo-bot" in listing.stdout

    show = run_aura("agent", "show", "acme/demo")
    assert show.returncode == 0
    profile = json.loads(show.stdout)
    assert profile["name"] == "demo-bot"

    missing = run_aura("agent", "show", "no-such-agent")
    assert missing.returncode == 1
    assert "not found" in missing.stderr


def test_cli_run_script(run_aura, tmp_path: Path):
    script = tmp_path / "hello.py"
    script.write_text("# run under aura session\n", encoding="utf-8")
    result = run_aura("run", "cli-runner", str(script))
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["session_id"].startswith("aura_sess_")
    assert "summary" in payload["exports"]


def test_cli_logs_export_compare_otel(run_aura, aura_home: Path):
    ag = agent("cli-export", agent_ref="test/cli")
    with ag.session() as run:
        run.emit("turn.start", {})
        run.emit("turn.end", {"tokens": 1})
    session_id = run.session_id

    logs = run_aura("logs", session_id)
    assert logs.returncode == 0
    rows = [json.loads(line) for line in logs.stdout.splitlines() if line.strip()]
    assert any(r["kind"] == "turn.start" for r in rows)

    export = run_aura("export", session_id)
    assert export.returncode == 0
    summary = json.loads(export.stdout)
    assert summary["agent_ref"] == "test/cli"
    assert summary["audit_report"]["verdict"] == "pass"

    missing = run_aura("export", "missing-session")
    assert missing.returncode == 1

    with ag.session() as run2:
        run2.emit("turn.start", {})
    otel = run_aura("export-otel", run2.session_id)
    assert otel.returncode == 0
    assert "turn.start" in otel.stdout
    otel_path = aura_home / "sessions" / f"{run2.session_id}.otel.jsonl"
    assert otel_path.is_file()

    compare = run_aura("compare", session_id, run2.session_id)
    assert compare.returncode == 0
    diff = json.loads(compare.stdout)
    assert diff["session_a"] == session_id
    assert diff["event_count"]["b"] < diff["event_count"]["a"]


def test_cli_verify_chain(run_aura, tmp_path: Path):
    path = tmp_path / "session.jsonl"
    spine = AuditSpine("session", "aura-id", path)
    spine.append("turn.start", {"input": "hello"})
    spine.append("turn.end", {"output": "world"})

    valid = run_aura("verify", "chain", str(path))
    assert valid.returncode == 0
    assert json.loads(valid.stdout) == {"hash_chain_valid": True}

    rows = AuditSpine.read_jsonl(path)
    rows[1]["content_hash"] = "0" * 64
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    broken = run_aura("verify", "chain", str(path))
    assert broken.returncode == 1
    payload = json.loads(broken.stdout)
    assert payload["hash_chain_valid"] is False
    assert payload["event_id"] == rows[1]["event_id"]


def test_cli_run_requires_script(run_aura):
    result = run_aura("run", "agent-only")
    assert result.returncode == 1
    assert "script" in result.stderr.lower()


def test_cli_help_grouped(run_aura):
    result = run_aura("--help")
    assert result.returncode == 0
    assert "agents" in result.stdout.lower()
    assert "aura agent list" in result.stdout
    assert "aura verify chain path/to/session.jsonl" in result.stdout
    assert "interactive" in result.stdout.lower()


def test_cli_interactive_splash_and_exit(run_aura):
    result = run_aura(input_text="0\n")
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert combined.startswith("\n") or combined.startswith("\r\n")
    assert "AURA Harness" in combined
    from aura.cli.splash import splash_contains_aura

    assert splash_contains_aura(combined)
    assert "Bye." in combined


def test_cli_agent_set(run_aura):
    run_aura("agent", "create", "setter-bot")
    result = run_aura(
        "agent",
        "set",
        "setter-bot",
        "--ref",
        "acme/setter",
        "--purpose",
        "testing",
        "--skill",
        "research",
        "--variable",
        "model=llama3.2",
    )
    assert result.returncode == 0
    profile = json.loads(result.stdout)
    assert profile["agent_ref"] == "acme/setter"
    assert profile["purpose"] == "testing"
    assert profile["skills"] == ["research"]
    assert profile["variables"]["model"] == "llama3.2"


def test_cli_config_show_and_paths(run_aura, aura_home: Path, project_dir: Path):
    import yaml

    (aura_home / "config.yaml").write_text(
        yaml.dump({"default_session_mode": "task"}),
        encoding="utf-8",
    )
    config = run_aura("config", "show")
    assert config.returncode == 0
    data = json.loads(config.stdout)
    assert data["values"]["default_session_mode"] == "task"
    assert str(aura_home) in data["home"]

    paths = run_aura("paths")
    assert paths.returncode == 0
    assert "registry:" in paths.stdout

    set_proj = run_aura("paths", "set-project", str(project_dir))
    assert set_proj.returncode == 0
    assert "project_dir saved" in set_proj.stdout

    set_storage = run_aura("paths", "set-storage", "global")
    assert set_storage.returncode == 0
    assert "storage=global saved" in set_storage.stdout


def test_aura_console_script_entry_point():
    import importlib.metadata

    scripts = {ep.name: ep.value for ep in importlib.metadata.entry_points(group="console_scripts")}
    assert scripts.get("aura") == "aura.cli.main:main"
