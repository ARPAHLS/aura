"""Interactive paths submenu."""

from __future__ import annotations

from typing import Callable, Optional

from rich.console import Console
from rich.text import Text

from aura.cli import commands
from aura.cli.help_text import _NAV_BACK, _NAV_EXIT
from aura.cli.help_ui import _parse_nav, _print_nav_footer, _read_line
from aura.cli.styles import MENU_STYLE, TABLE_STYLE


def cmd_paths_submenu(
    console: Console | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> Optional[str]:
    """Interactive paths editor. Returns _NAV_EXIT to quit AURA."""
    if console is None:
        console = Console()

    submenu = {
        "1": "view",
        "view": "view",
        "2": "project",
        "project": "project",
        "3": "storage",
        "storage": "storage",
        "4": "config",
        "config": "config",
    }

    while True:
        console.print(Text("Paths", style=f"bold {TABLE_STYLE}"))
        console.print("    [1] view     — resolved registry and sessions dirs", style=MENU_STYLE)
        console.print("    [2] project  — persist default project directory", style=MENU_STYLE)
        console.print("    [3] storage  — global or project-scoped storage", style=MENU_STYLE)
        console.print("    [4] config   — merged config (read-only)", style=MENU_STYLE)
        _print_nav_footer(console, show_back=True)

        raw = _read_line("  paths> ", input_fn)
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            return _NAV_EXIT
        if nav == _NAV_BACK:
            return None
        if not choice:
            continue

        command = submenu.get(choice.lower())
        if command == "view":
            commands.cmd_paths(console=console)
        elif command == "project":
            directory = _read_line("  project directory> ", input_fn)
            if directory and directory.strip():
                rc = commands.cmd_paths_set_project(directory.strip(), console=console)
                if rc:
                    console.print(f"  set-project exited with status {rc}", style="dim #FF9AA2")
        elif command == "storage":
            mode = _read_line("  storage (global|project)> ", input_fn)
            if mode and mode.strip():
                rc = commands.cmd_paths_set_storage(mode.strip().lower(), console=console)
                if rc:
                    console.print(f"  set-storage exited with status {rc}", style="dim #FF9AA2")
        elif command == "config":
            commands.cmd_config_show(console=console)
        else:
            console.print(f"  Unknown choice: '{choice}'", style="dim #FF9AA2")
        console.print()
