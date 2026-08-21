"""Grouped help and interactive help submenu."""

from __future__ import annotations

import builtins
from typing import Callable, List, Optional, Tuple

from rich.console import Console
from rich.text import Text

from aura.cli.help_text import (
    CLI_USAGE_EXAMPLES,
    HELP_GROUPS,
    _DOCS_CLI,
    _HELP_MENU,
    _NAV_BACK,
    _NAV_EXIT,
)
from aura.cli.styles import MENU_STYLE, SPLASH_STYLE, TABLE_STYLE


def _read_line(prompt: str, input_fn: Callable[[str], str] | None = None) -> Optional[str]:
    if input_fn is None:
        input_fn = builtins.input
    try:
        return input_fn(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        return None


def _parse_nav(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if raw is None:
        return None, _NAV_BACK
    text = raw.strip()
    if not text:
        return "", None
    key = text.lower()
    if key in ("0", "q", "quit", "exit"):
        return None, _NAV_EXIT
    if key in ("b", "back", "esc", "escape"):
        return None, _NAV_BACK
    return text, None


def _print_nav_footer(console: Console, *, show_back: bool = True) -> None:
    console.print("  ---", style="dim")
    if show_back:
        console.print("  b — back to previous menu", style="dim")
    console.print("  0 — exit AURA", style="dim")
    console.print()


def _print_help_command_group(
    console: Console, group: Tuple[str, List[Tuple[str, str]], str]
) -> None:
    group_name, commands, doc_link = group
    console.print(Text(group_name, style=f"bold {TABLE_STYLE}"))
    for command, description in commands:
        console.print(f"  {command} — {description}", style=MENU_STYLE)
    console.print(f"  Read more: {doc_link}", style=f"dim {SPLASH_STYLE}")
    console.print()


def _print_help_index(console: Console) -> None:
    console.print(Text("Usage", style=f"bold {TABLE_STYLE}"))
    console.print(
        "  Run aura and choose help (5) for full topic details.",
        style="dim",
    )
    console.print()
    console.print(Text("Topics", style=f"bold {TABLE_STYLE}"))
    for key, slug, summary, _target in _HELP_MENU:
        console.print(f"  {key} {slug:<12}— {summary}", style=MENU_STYLE)
    console.print()


def _print_cli_usage_examples(console: Console) -> None:
    console.print(Text("CLI usage examples", style=f"bold {TABLE_STYLE}"))
    for line in CLI_USAGE_EXAMPLES:
        console.print(f"  {line}", style=MENU_STYLE)
    console.print()


def _print_help_static_topic(console: Console, topic: str) -> None:
    if topic == "install":
        console.print(Text("Install", style=f"bold {TABLE_STYLE}"))
        console.print("  pip install aura-harness", style=MENU_STYLE)
        console.print('  pip install -e ".[dev]"  # local development', style="dim")
    elif topic == "docs":
        console.print(Text("Docs", style=f"bold {TABLE_STYLE}"))
        console.print(f"  {_DOCS_CLI}", style=f"dim {SPLASH_STYLE}")
    elif topic == "interactive":
        console.print(Text("Interactive mode", style=f"bold {TABLE_STYLE}"))
        console.print("  aura — open splash menu", style=MENU_STYLE)
        console.print("  1-6 or command name — run a command", style="dim")
        console.print("  0 — exit from any menu level", style="dim")
    console.print()


def cmd_help(*, console: Console | None = None, brief: bool = True) -> None:
    if console is None:
        console = Console()

    if brief:
        _print_help_index(console)
        _print_cli_usage_examples(console)
        console.print(Text("Install", style=f"bold {TABLE_STYLE}"))
        console.print("  pip install aura-harness", style="dim")
        console.print()
        console.print(Text("Docs", style=f"bold {TABLE_STYLE}"))
        console.print(f"  {_DOCS_CLI}", style=f"dim {SPLASH_STYLE}")
        console.print()
        console.print(Text("Interactive mode", style=f"bold {TABLE_STYLE}"))
        console.print("  aura — menu 1-6; help topic drill-down via 5", style="dim")
        console.print("  0 — exit from any menu level", style="dim")
        console.print()
        return

    for group in HELP_GROUPS:
        _print_help_command_group(console, group)
    _print_cli_usage_examples(console)


def cmd_help_submenu(
    console: Console | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> Optional[str]:
    """Interactive help topics. Returns _NAV_EXIT to quit AURA."""
    if console is None:
        console = Console()

    topic_map = {key: target for key, _slug, _summary, target in _HELP_MENU}
    topic_map.update({slug: target for key, slug, _summary, target in _HELP_MENU})

    while True:
        console.print(Text("Help", style=f"bold {TABLE_STYLE}"))
        for key, slug, summary, _target in _HELP_MENU:
            console.print(f"    [{key}] {slug:<12}— {summary}", style=MENU_STYLE)
        _print_nav_footer(console, show_back=True)

        raw = _read_line("  help> ", input_fn)
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            return _NAV_EXIT
        if nav == _NAV_BACK:
            return None
        if not choice:
            continue

        target = topic_map.get(choice.lower())
        if target is None:
            console.print(f"  Unknown topic: '{choice}'", style="dim #FF9AA2")
            console.print()
            continue

        if isinstance(target, int):
            _print_help_command_group(console, HELP_GROUPS[target])
        else:
            _print_help_static_topic(console, target)

        pause = _read_line("  Press Enter to return to help topics… ", input_fn)
        _, pause_nav = _parse_nav(pause if pause else "")
        if pause_nav == _NAV_EXIT:
            return _NAV_EXIT
        if pause_nav == _NAV_BACK:
            continue
        console.print()
