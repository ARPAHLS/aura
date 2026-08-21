"""ASCII splash screen for the interactive CLI."""

from __future__ import annotations

from typing import Tuple

from rich.console import Console
from rich.text import Text

from aura import __version__
from aura.cli.styles import (
    SPLASH_GRADIENT_END,
    SPLASH_GRADIENT_MID,
    SPLASH_GRADIENT_START,
    SPLASH_STYLE,
)

_SPLASH_LOGO_LINES: Tuple[str, ...] = (
    " █████╗ ██╗   ██╗██████╗  █████╗ ",
    "██╔══██╗██║   ██║██╔══██╗██╔══██╗",
    "███████║██║   ██║██████╔╝███████║",
    "██╔══██║██║   ██║██╔══██╗██╔══██║",
    "██║  ██║╚██████╔╝██║  ██║██║  ██║",
    "╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝",
)


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def _lerp_rgb(
    start: Tuple[int, int, int], end: Tuple[int, int, int], t: float
) -> Tuple[int, int, int]:
    return tuple(int(start[i] + (end[i] - start[i]) * t) for i in range(3))


def _splash_gradient_color(column: int, width: int) -> str:
    if width <= 1:
        return _rgb_to_hex(SPLASH_GRADIENT_START)
    t = column / (width - 1)
    if t <= 0.5:
        rgb = _lerp_rgb(SPLASH_GRADIENT_START, SPLASH_GRADIENT_MID, t / 0.5)
    else:
        rgb = _lerp_rgb(SPLASH_GRADIENT_MID, SPLASH_GRADIENT_END, (t - 0.5) / 0.5)
    return _rgb_to_hex(rgb)


def gradient_text_line(line: str, width: int) -> Text:
    text = Text()
    for column, char in enumerate(line):
        text.append(char, style=_splash_gradient_color(column, width))
    return text


def gradient_splash_text(logo_lines: Tuple[str, ...]) -> Text:
    width = max(len(line) for line in logo_lines)
    text = Text()
    for line in logo_lines:
        text.append(gradient_text_line(line, width))
        text.append("\n")
    return text


def cli_console(*, stderr: bool = False) -> Console:
    """Console tuned for CLI output (UTF-8 safe when piped on Windows)."""
    import sys

    stream = sys.stderr if stderr else sys.stdout
    return Console(file=stream, legacy_windows=stream.isatty(), force_terminal=stream.isatty())


def print_splash(console: Console | None = None, *, version: str | None = None) -> None:
    """Render the AURA ASCII logo and tagline."""
    if console is None:
        console = cli_console()
    version = version if version is not None else __version__
    logo_width = max(len(line) for line in _SPLASH_LOGO_LINES)

    try:
        console.print(gradient_splash_text(_SPLASH_LOGO_LINES))
        console.print(
            gradient_text_line(
                f"  AURA Harness v{version} — Runtime membrane for agent loops",
                logo_width,
            )
        )
    except UnicodeEncodeError:
        plain = Console(force_terminal=False, no_color=True, file=console.file)
        plain.print("AURA")
        plain.print(f"AURA Harness v{version} — Runtime membrane for agent loops")
    console.print(
        Text(
            "  https://github.com/ARPAHLS/aura  ·  https://arpacorp.net\n",
            style=f"dim {SPLASH_STYLE}",
        )
    )


def splash_contains_aura(text: str) -> bool:
    """True when combined output includes AURA branding from the splash."""
    return "AURA Harness" in text and ("█████╗" in text or text.strip().startswith("AURA"))
