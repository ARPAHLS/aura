"""Interactive splash menu for bare `aura` invocations."""

from __future__ import annotations

import builtins
from typing import Callable, Optional

from rich.console import Console
from rich.text import Text

from aura.cli import commands
from aura.cli.help_text import MAIN_MENU, _NAV_BACK, _NAV_EXIT
from aura.cli.help_ui import _parse_nav, _print_nav_footer, _read_line, cmd_help_submenu
from aura.cli.paths_ui import cmd_paths_submenu
from aura.cli.splash import cli_console, print_splash
from aura.cli.styles import MENU_STYLE, TABLE_STYLE


def _print_menu(console: Console) -> None:
    for num, name, desc in MAIN_MENU:
        console.print(f"    [{num}] {name:<12}— {desc}", style=MENU_STYLE)
    _print_nav_footer(console, show_back=False)


def _agents_submenu(
    console: Console,
    input_fn: Callable[[str], str] | None = None,
) -> Optional[str]:
    submenu = {
        "1": "list",
        "list": "list",
        "2": "show",
        "show": "show",
        "3": "create",
        "create": "create",
        "4": "edit",
        "edit": "edit",
    }
    while True:
        console.print(Text("Agents", style=f"bold {TABLE_STYLE}"))
        console.print("    [1] list   — registered agents", style=MENU_STYLE)
        console.print("    [2] show   — profile by name or agent_ref", style=MENU_STYLE)
        console.print("    [3] create — register a new agent", style=MENU_STYLE)
        console.print("    [4] edit   — update ref, purpose, skills, variables", style=MENU_STYLE)
        _print_nav_footer(console, show_back=True)

        raw = _read_line("  agents> ", input_fn)
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            return _NAV_EXIT
        if nav == _NAV_BACK:
            return None
        if not choice:
            continue

        command = submenu.get(choice.lower())
        if command == "list":
            commands.cmd_agent_list(console=console, rich_table=True)
        elif command == "show":
            name = _read_line("  name or agent_ref> ", input_fn)
            if name is None:
                console.print("  Cancelled.", style="dim")
                continue
            if name.strip():
                rc = commands.cmd_agent_show(name.strip(), console=console)
                if rc:
                    console.print(f"  show exited with status {rc}", style="dim #FF9AA2")
        elif command == "create":
            name = _read_line("  name> ", input_fn)
            if name is None:
                console.print("  Cancelled.", style="dim")
                continue
            if not name.strip():
                continue
            agent_ref = _read_line("  agent_ref (optional)> ", input_fn)
            if agent_ref is None:
                console.print("  Cancelled.", style="dim")
                continue
            rc = commands.cmd_agent_create(
                name.strip(),
                agent_ref=agent_ref.strip() or None,
                console=console,
            )
            if rc:
                console.print(f"  create exited with status {rc}", style="dim #FF9AA2")
        elif command == "edit":
            name = _read_line("  name or agent_ref> ", input_fn)
            if name is None or not name.strip():
                console.print("  Cancelled.", style="dim")
                continue
            agent_ref = _read_line("  agent_ref (Enter to skip)> ", input_fn)
            if agent_ref is None:
                console.print("  Cancelled.", style="dim")
                continue
            purpose = _read_line("  purpose (Enter to skip)> ", input_fn)
            if purpose is None:
                console.print("  Cancelled.", style="dim")
                continue
            skills_raw = _read_line("  skills comma-separated (Enter to skip)> ", input_fn)
            if skills_raw is None:
                console.print("  Cancelled.", style="dim")
                continue
            variable = _read_line("  variable key=value (Enter to skip)> ", input_fn)
            if variable is None:
                console.print("  Cancelled.", style="dim")
                continue
            kwargs: dict = {}
            if agent_ref.strip():
                kwargs["agent_ref"] = agent_ref.strip()
            if purpose.strip():
                kwargs["purpose"] = purpose.strip()
            if skills_raw.strip():
                kwargs["skills"] = [s.strip() for s in skills_raw.split(",") if s.strip()]
            if variable.strip():
                kwargs["variables"] = [variable.strip()]
            if not kwargs:
                console.print("  Nothing to update.", style="dim")
                continue
            rc = commands.cmd_agent_set(name.strip(), console=console, **kwargs)
            if rc:
                console.print(f"  edit exited with status {rc}", style="dim #FF9AA2")
        else:
            console.print(f"  Unknown choice: '{choice}'", style="dim #FF9AA2")
        console.print()


def _sessions_submenu(
    console: Console,
    input_fn: Callable[[str], str] | None = None,
) -> Optional[str]:
    submenu = {
        "1": "logs",
        "logs": "logs",
        "2": "export",
        "export": "export",
        "3": "export-otel",
        "otel": "export-otel",
        "4": "compare",
        "compare": "compare",
        "5": "verify",
        "verify": "verify",
    }
    while True:
        console.print(Text("Sessions", style=f"bold {TABLE_STYLE}"))
        console.print("    [1] logs         — print session JSONL", style=MENU_STYLE)
        console.print("    [2] export       — session summary JSON", style=MENU_STYLE)
        console.print("    [3] export-otel  — OTel-style JSONL export", style=MENU_STYLE)
        console.print("    [4] compare      — diff two session summaries", style=MENU_STYLE)
        console.print("    [5] verify       — validate an exported hash chain", style=MENU_STYLE)
        _print_nav_footer(console, show_back=True)

        raw = _read_line("  sessions> ", input_fn)
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            return _NAV_EXIT
        if nav == _NAV_BACK:
            return None
        if not choice:
            continue

        command = submenu.get(choice.lower())
        if command == "logs":
            session_id = _read_line("  session_id> ", input_fn)
            if session_id and session_id.strip():
                commands.cmd_logs(session_id.strip(), console=console)
        elif command == "export":
            session_id = _read_line("  session_id> ", input_fn)
            if session_id and session_id.strip():
                commands.cmd_export(session_id.strip(), console=console)
        elif command == "export-otel":
            session_id = _read_line("  session_id> ", input_fn)
            if session_id and session_id.strip():
                commands.cmd_export_otel(session_id.strip(), console=console)
        elif command == "compare":
            session_a = _read_line("  session_a> ", input_fn)
            if session_a is None:
                console.print("  Cancelled.", style="dim")
                continue
            session_b = _read_line("  session_b> ", input_fn)
            if session_a and session_b and session_a.strip() and session_b.strip():
                commands.cmd_compare(session_a.strip(), session_b.strip(), console=console)
        elif command == "verify":
            path = _read_line("  JSONL path> ", input_fn)
            if path and path.strip():
                commands.cmd_verify_chain(path.strip(), console=console)
        else:
            console.print(f"  Unknown choice: '{choice}'", style="dim #FF9AA2")
        console.print()


def _run_prompt(
    console: Console,
    input_fn: Callable[[str], str] | None = None,
) -> None:
    agent_name = _read_line("  agent name (optional)> ", input_fn)
    if agent_name is None:
        console.print("  Cancelled.", style="dim")
        return
    script = _read_line("  script path (.py)> ", input_fn)
    if script is None or not script.strip():
        console.print("  Cancelled.", style="dim")
        return
    target = script.strip()
    name = agent_name.strip() or None
    if name:
        rc = commands.cmd_run(name, target, console=console)
    else:
        rc = commands.cmd_run(target, console=console)
    if rc:
        console.print(f"  run exited with status {rc}", style="dim #FF9AA2")


def cmd_interactive(
    console: Console | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> None:
    """Launch ASCII splash and interactive menu."""
    if console is None:
        console = cli_console()
    if input_fn is None:
        input_fn = builtins.input

    print_splash(console)

    command_map = {
        "1": "agents",
        "agents": "agents",
        "2": "sessions",
        "sessions": "sessions",
        "3": "run",
        "run": "run",
        "4": "paths",
        "paths": "paths",
        "home": "paths",
        "5": "help",
        "help": "help",
        "6": "version",
        "version": "version",
    }

    _print_menu(console)

    while True:
        raw = _read_line("  > ", input_fn)
        if raw is None:
            console.print("\n  Bye.", style="dim")
            return
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            console.print("  Bye.", style="dim")
            return
        if nav == _NAV_BACK:
            continue
        if not choice:
            continue

        command = command_map.get(choice.lower())
        if command == "agents":
            agents_nav = _agents_submenu(console, input_fn=input_fn)
            if agents_nav == _NAV_EXIT:
                console.print("  Bye.", style="dim")
                return
        elif command == "sessions":
            sessions_nav = _sessions_submenu(console, input_fn=input_fn)
            if sessions_nav == _NAV_EXIT:
                console.print("  Bye.", style="dim")
                return
        elif command == "run":
            _run_prompt(console, input_fn=input_fn)
        elif command == "paths":
            paths_nav = cmd_paths_submenu(console=console, input_fn=input_fn)
            if paths_nav == _NAV_EXIT:
                console.print("  Bye.", style="dim")
                return
        elif command == "help":
            help_nav = cmd_help_submenu(console=console, input_fn=input_fn)
            if help_nav == _NAV_EXIT:
                console.print("  Bye.", style="dim")
                return
        elif command == "version":
            commands.cmd_version(console=console)
        else:
            console.print(f"  Unknown command: '{choice}'", style="dim #FF9AA2")

        console.print()
        _print_menu(console)
