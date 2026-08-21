"""CLI command implementations (scriptable and interactive)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aura import __version__, agent, create_agent
from aura.agents.registry import AgentNotFoundError, AgentRegistry, DuplicateAgentError
from aura.core.compare import compare_sessions
from aura.core.spine import AuditSpine
from aura.exporters.otel import export_session_otel
from aura.runtime.python import run_script

from rich import box
from rich.console import Console
from rich.table import Table

from aura.cli.styles import BORDER_STYLE, CATEGORY_STYLE, ID_STYLE, MENU_STYLE, TABLE_STYLE


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
    """Show resolved paths (alias for paths view)."""
    return cmd_paths(console=console)


def _parse_key_value_pairs(
    pairs: list[str] | None, label: str
) -> tuple[dict[str, str] | None, str | None]:
    if not pairs:
        return None, None
    result: dict[str, str] = {}
    for item in pairs:
        if "=" not in item:
            return None, f"invalid {label} '{item}' (expected key=value)"
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            return None, f"invalid {label} '{item}' (empty key)"
        result[key] = value.strip()
    return result, None


def cmd_agent_set(
    key: str,
    *,
    agent_ref: str | None = None,
    purpose: str | None = None,
    policy_version: str | None = None,
    default_mode: str | None = None,
    skills: list[str] | None = None,
    variables: list[str] | None = None,
    ids: list[str] | None = None,
    rules_file: Path | None = None,
    rules_json: str | None = None,
    console: Console | None = None,
) -> int:
    reg = AgentRegistry()
    try:
        reg.resolve(key)
    except AgentNotFoundError:
        message = f"not found: {key}"
        if console is None:
            print(message, file=sys.stderr)
        else:
            console.print(message, style="bold #FF9AA2")
        return 1

    var_map, err = _parse_key_value_pairs(variables, "variable")
    if err:
        if console is None:
            print(err, file=sys.stderr)
        else:
            console.print(err, style="bold #FF9AA2")
        return 2
    id_map, err = _parse_key_value_pairs(ids, "id")
    if err:
        if console is None:
            print(err, file=sys.stderr)
        else:
            console.print(err, style="bold #FF9AA2")
        return 2

    rules: list[dict] | None = None
    if rules_file is not None:
        if not rules_file.is_file():
            message = f"not found: {rules_file}"
            if console is None:
                print(message, file=sys.stderr)
            else:
                console.print(message, style="bold #FF9AA2")
            return 1
        rules = json.loads(rules_file.read_text(encoding="utf-8"))
        if not isinstance(rules, list):
            message = "rules file must contain a JSON array"
            if console is None:
                print(message, file=sys.stderr)
            else:
                console.print(message, style="bold #FF9AA2")
            return 2
    elif rules_json is not None:
        rules = json.loads(rules_json)
        if not isinstance(rules, list):
            message = "--rules-json must be a JSON array"
            if console is None:
                print(message, file=sys.stderr)
            else:
                console.print(message, style="bold #FF9AA2")
            return 2

    updates: dict = {}
    if agent_ref is not None:
        updates["agent_ref"] = agent_ref or None
    if purpose is not None:
        updates["purpose"] = purpose
    if policy_version is not None:
        updates["policy_version"] = policy_version
    if default_mode is not None:
        updates["default_mode"] = default_mode
    if skills is not None:
        updates["skills"] = skills
    if var_map is not None:
        updates["variables"] = var_map
    if id_map is not None:
        updates["ids"] = id_map
    if rules is not None:
        updates["rules"] = rules

    if not updates:
        message = "no fields to update (pass --ref, --purpose, --skill, etc.)"
        if console is None:
            print(message, file=sys.stderr)
        else:
            console.print(message, style="bold #FF9AA2")
        return 2

    try:
        profile = reg.update_profile(key, **updates)
    except (ValueError, DuplicateAgentError) as exc:
        message = str(exc)
        if console is None:
            print(message, file=sys.stderr)
        else:
            console.print(message, style="bold #FF9AA2")
        return 2

    payload = json.dumps(profile.to_dict(), indent=2)
    if console is None:
        print(payload)
    else:
        console.print(payload, style="dim")
        console.print(f"  saved: {reg.profile_path(profile.aura_id)}", style="dim")
    return 0


def cmd_config_show(*, console: Console | None = None) -> int:
    from aura.config import config_sources, get_config

    cfg = get_config()
    payload = {
        "home": str(cfg.home),
        "project_dir": str(cfg.project_dir) if cfg.project_dir else None,
        "values": cfg.values,
        "registry": str(cfg.registry_dir()),
        "sessions": str(cfg.sessions_dir()),
        "state_file": str(cfg.state_file()),
        "config_files": [
            {"layer": label, "path": str(path), "loaded": loaded}
            for label, path, loaded in config_sources(cfg)
        ],
    }
    text = json.dumps(payload, indent=2)
    if console is None:
        print(text)
    else:
        console.print("AURA config", style=f"bold {TABLE_STYLE}")
        for label, path, loaded in config_sources(cfg):
            status = "loaded" if loaded else "missing"
            console.print(f"  {label}: {path} ({status})", style=MENU_STYLE if loaded else "dim")
        console.print()
        console.print(f"  storage: {cfg.values.get('storage', 'global')}", style=ID_STYLE)
        console.print(f"  registry: {cfg.registry_dir()}", style=CATEGORY_STYLE)
        console.print(f"  sessions: {cfg.sessions_dir()}", style=CATEGORY_STYLE)
        if cfg.project_dir:
            console.print(f"  project: {cfg.project_dir}", style="dim")
    return 0


def cmd_paths(*, console: Console | None = None) -> int:
    from aura.config import config_sources, get_config

    cfg = get_config()
    if console is None:
        print(f"AURA_HOME: {cfg.home}")
        print(f"storage: {cfg.values.get('storage', 'global')}")
        print(f"registry: {cfg.registry_dir()}")
        print(f"sessions: {cfg.sessions_dir()}")
        if cfg.project_dir:
            print(f"project: {cfg.project_dir}")
        for label, path, loaded in config_sources(cfg):
            print(f"config_{label}: {path} ({'loaded' if loaded else 'missing'})")
        return 0

    console.print("Path resolution", style=f"bold {TABLE_STYLE}")
    console.print(f"  AURA_HOME: {cfg.home}", style=ID_STYLE)
    console.print(f"  storage mode: {cfg.values.get('storage', 'global')}", style=MENU_STYLE)
    console.print(f"  registry: {cfg.registry_dir()}", style=CATEGORY_STYLE)
    console.print(f"  sessions: {cfg.sessions_dir()}", style=CATEGORY_STYLE)
    if cfg.project_dir:
        console.print(f"  project: {cfg.project_dir}", style="dim")
    console.print()
    console.print("Config files", style=f"bold {TABLE_STYLE}")
    for label, path, loaded in config_sources(cfg):
        status = "ok" if loaded else "missing"
        console.print(f"  {label}: {path} [{status}]", style="dim" if not loaded else MENU_STYLE)
    console.print(
        "  Tip: aura paths set-project <dir> · aura paths set-storage global|project",
        style="dim",
    )
    return 0


def cmd_paths_set_project(directory: str, *, console: Console | None = None) -> int:
    from aura.config import get_config, reload_config, save_global_config

    candidate = Path(directory).expanduser()
    if not candidate.is_dir():
        message = f"not a directory: {candidate}"
        if console is None:
            print(message, file=sys.stderr)
        else:
            console.print(message, style="bold #FF9AA2")
        return 1
    resolved = str(candidate.resolve())
    path = save_global_config({"project_dir": resolved}, home=get_config().home)
    reload_config(project_dir=resolved)
    message = f"project_dir saved to {path}"
    if console is None:
        print(message)
    else:
        console.print(message, style=ID_STYLE)
    return 0


def cmd_paths_set_storage(mode: str, *, console: Console | None = None) -> int:
    from aura.config import get_config, reload_config, save_global_config, save_project_config

    if mode not in ("global", "project"):
        message = "storage must be 'global' or 'project'"
        if console is None:
            print(message, file=sys.stderr)
        else:
            console.print(message, style="bold #FF9AA2")
        return 2

    cfg = get_config()
    if cfg.project_dir and mode == "project":
        path = save_project_config({"storage": mode}, cfg.project_dir)
    else:
        path = save_global_config({"storage": mode}, home=cfg.home)
    reload_config(project_dir=cfg.project_dir)
    message = f"storage={mode} saved to {path}"
    if console is None:
        print(message)
    else:
        console.print(message, style=ID_STYLE)
    return 0
