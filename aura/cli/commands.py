"""CLI command implementations (scriptable and interactive)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aura import __version__, agent, create_agent
from aura.agents.registry import AgentNotFoundError, AgentRegistry
from aura.core.compare import compare_sessions
from aura.core.spine import AuditSpine
from aura.exporters.otel import export_session_otel
from aura.runtime.python import run_script

from rich import box
from rich.console import Console
from rich.table import Table

from aura.cli.styles import BORDER_STYLE, CATEGORY_STYLE, ID_STYLE, TABLE_STYLE


def cmd_version(*, console: Console | None = None) -> int:
    line = f"aura-harness {__version__}"
    if console is None:
        print(line)
    else:
        console.print(line, style=ID_STYLE)
    return 0


def cmd_agent_create(
    name: str | None,
    *,
    agent_ref: str | None = None,
    aura_id: str | None = None,
    purpose: str | None = None,
    policy_version: str = "1",
    mode: str = "script",
    console: Console | None = None,
) -> int:
    handle = create_agent(
        name=name,
        agent_ref=agent_ref,
        aura_id=aura_id,
        purpose=purpose,
        policy_version=policy_version,
        default_mode=mode,
    )
    payload = json.dumps(handle.profile.to_dict(), indent=2)
    if console is None:
        print(payload)
    else:
        console.print(payload, style="dim")
    return 0


def cmd_agent_list(*, console: Console | None = None, rich_table: bool = False) -> int:
    reg = AgentRegistry()
    agents = reg.list_agents()
    if rich_table and console is not None:
        table = Table(
            box=box.SIMPLE_HEAVY,
            border_style=BORDER_STYLE,
            header_style=TABLE_STYLE,
            expand=True,
        )
        table.add_column("AURA_ID", style=ID_STYLE, no_wrap=True, ratio=2)
        table.add_column("AGENT_REF", style=CATEGORY_STYLE, no_wrap=True, ratio=2)
        table.add_column("NAME", ratio=2)
        for profile in agents:
            table.add_row(
                profile.aura_id,
                profile.agent_ref or "-",
                profile.name or "(unnamed)",
            )
        console.print(table)
        if not agents:
            console.print("No agents registered yet.", style="dim")
        return 0

    for profile in agents:
        ref = profile.agent_ref or "-"
        label = profile.name or "(unnamed)"
        print(f"{profile.aura_id}  {ref}  {label}")
    return 0


def cmd_agent_show(name: str, *, console: Console | None = None) -> int:
    reg = AgentRegistry()
    try:
        profile = reg.resolve(name)
    except AgentNotFoundError:
        message = f"not found: {name}"
        if console is None:
            print(message, file=sys.stderr)
        else:
            console.print(message, style="bold #FF9AA2")
        return 1
    payload = json.dumps(profile.to_dict(), indent=2)
    if console is None:
        print(payload)
    else:
        console.print(payload, style="dim")
    return 0


def cmd_run(
    target: str,
    script: str | None = None,
    *,
    mode: str | None = None,
    console: Console | None = None,
) -> int:
    script_path: Path | None = None
    agent_name: str | None = None
    if script:
        agent_name = target
        script_path = Path(script)
    elif Path(target).suffix == ".py":
        script_path = Path(target)
    else:
        agent_name = target
        message = "error: provide a .py script path"
        if console is None:
            print(message, file=sys.stderr)
        else:
            console.print(message, style="bold #FF9AA2")
        return 1

    handle = agent(agent_name) if agent_name else agent()
    result = run_script(handle, script_path, mode=mode)
    payload = json.dumps(result, indent=2)
    if console is None:
        print(payload)
    else:
        console.print(payload, style="dim")
    return 0


def cmd_logs(session_id: str, *, console: Console | None = None) -> int:
    from aura.config import get_config

    path = get_config().sessions_dir() / f"{session_id}.jsonl"
    if not path.is_file():
        message = f"not found: {path}"
        if console is None:
            print(message, file=sys.stderr)
        else:
            console.print(message, style="bold #FF9AA2")
        return 1
    rows = AuditSpine.read_jsonl(path)
    for row in rows:
        line = json.dumps(row)
        if console is None:
            print(line)
        else:
            console.print(line, style="dim")
    return 0


def cmd_export(session_id: str, *, console: Console | None = None) -> int:
    from aura.config import get_config

    path = get_config().sessions_dir() / f"{session_id}.summary.json"
    if not path.is_file():
        message = f"not found: {path}"
        if console is None:
            print(message, file=sys.stderr)
        else:
            console.print(message, style="bold #FF9AA2")
        return 1
    text = path.read_text(encoding="utf-8")
    if console is None:
        print(text)
    else:
        console.print(text, style="dim")
    return 0


def cmd_export_otel(session_id: str, *, console: Console | None = None) -> int:
    from aura.config import get_config

    path = export_session_otel(session_id, get_config().sessions_dir())
    text = path.read_text(encoding="utf-8")
    if console is None:
        print(text)
    else:
        console.print(text, style="dim")
    return 0


def cmd_compare(session_a: str, session_b: str, *, console: Console | None = None) -> int:
    from aura.config import get_config

    base = get_config().sessions_dir()
    path_a = base / f"{session_a}.summary.json"
    path_b = base / f"{session_b}.summary.json"
    if not path_a.is_file() or not path_b.is_file():
        missing = []
        if not path_a.is_file():
            missing.append(str(path_a))
        if not path_b.is_file():
            missing.append(str(path_b))
        message = "not found: " + ", ".join(missing)
        if console is None:
            print(message, file=sys.stderr)
        else:
            console.print(message, style="bold #FF9AA2")
        return 1
    result = compare_sessions(path_a, path_b)
    payload = json.dumps(result, indent=2)
    if console is None:
        print(payload)
    else:
        console.print(payload, style="dim")
    return 0


def cmd_home(*, console: Console | None = None) -> int:
    from aura.config import get_config

    cfg = get_config()
    if console is None:
        print(f"AURA_HOME: {cfg.home}")
        print(f"registry: {cfg.registry_dir()}")
        print(f"sessions: {cfg.sessions_dir()}")
        print(f"storage: {cfg.values.get('storage', 'global')}")
        if cfg.project_dir:
            print(f"project: {cfg.project_dir}")
        return 0

    console.print("AURA paths", style=f"bold {TABLE_STYLE}")
    console.print(f"  home: {cfg.home}", style=ID_STYLE)
    console.print(f"  registry: {cfg.registry_dir()}", style=CATEGORY_STYLE)
    console.print(f"  sessions: {cfg.sessions_dir()}", style=CATEGORY_STYLE)
    console.print(f"  storage mode: {cfg.values.get('storage', 'global')}", style="dim")
    if cfg.project_dir:
        console.print(f"  project: {cfg.project_dir}", style="dim")
    return 0
