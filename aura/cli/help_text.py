"""Grouped CLI help and interactive menu definitions."""

from __future__ import annotations

from typing import List, Tuple, Union

_DOCS_CLI = "https://github.com/ARPAHLS/aura/blob/main/docs/using-aura.md"
_DOCS_GETTING_STARTED = "https://github.com/ARPAHLS/aura/blob/main/docs/getting-started.md"
_DOCS_TESTING = "https://github.com/ARPAHLS/aura/blob/main/docs/TESTING.md"

HELP_GROUPS: List[Tuple[str, List[Tuple[str, str]], str]] = [
    (
        "Agents",
        [
            ("aura agent create <name>", "register agent profile (optional --ref)"),
            ("aura agent list", "list aura_id, agent_ref, and name"),
            ("aura agent show <id>", "JSON profile by name, agent_ref, or aura_id"),
            ("aura agent set <id> …", "update ref, purpose, skills, variables, rules"),
        ],
        _DOCS_CLI,
    ),
    (
        "Sessions",
        [
            ("aura run <agent> <script.py>", "run script under audited session"),
            ("aura logs <session_id>", "print session JSONL to stdout"),
            ("aura export <session_id>", "print session summary JSON"),
            ("aura export-otel <session_id>", "write OTel-style JSONL beside session"),
            ("aura compare <a> <b>", "diff two session summaries"),
            ("aura verify chain <path>", "validate an exported JSONL hash chain"),
        ],
        _DOCS_CLI,
    ),
    (
        "Paths",
        [
            ("aura paths", "show resolved registry and sessions dirs"),
            ("aura paths set-project <dir>", "persist default project directory"),
            ("aura paths set-storage global|project", "persist storage mode"),
            ("aura config show", "merged global + project YAML and paths"),
            ("aura --home <dir>", "override AURA_HOME for this invocation"),
            ("aura --project <dir>", "one-shot project-scoped .aura/ storage"),
        ],
        _DOCS_GETTING_STARTED,
    ),
    (
        "General",
        [
            ("aura", "interactive menu (splash + numbered options)"),
            ("aura --help", "grouped command reference"),
            ("aura version", "installed package version"),
        ],
        _DOCS_CLI,
    ),
]

_HELP_MENU: List[Tuple[str, str, str, Union[int, str]]] = [
    ("1", "agents", "create, list, show, set", 0),
    ("2", "sessions", "run, logs, export, compare, verify", 1),
    ("3", "paths", "AURA_HOME and project storage", 2),
    ("4", "general", "menu, help, version", 3),
    ("5", "install", "pip install aura-harness", "install"),
    ("6", "docs", "full usage guide online", "docs"),
    ("7", "interactive", "numbered splash menu", "interactive"),
]

CLI_USAGE_EXAMPLES: Tuple[str, ...] = (
    "aura agent create demo-bot --ref acme/demo",
    "aura agent set demo-bot --ref acme/demo --purpose compliance",
    "aura agent list",
    "aura config show",
    "aura paths set-project .",
    "aura run cli-runner path/to/script.py",
    "aura export aura_sess_01H...",
    "aura compare sess_a sess_b",
    "aura export-otel aura_sess_01H...",
    "aura verify chain path/to/session.jsonl",
)

MAIN_MENU: List[Tuple[str, str, str]] = [
    ("1", "agents", "list, show, create, or edit profiles"),
    ("2", "sessions", "logs, export, compare, verify, or export-otel"),
    ("3", "run", "run a Python script under an agent session"),
    ("4", "paths", "view/edit AURA_HOME, project, and config"),
    ("5", "help", "grouped CLI reference and doc links"),
    ("6", "version", "installed package version"),
]

_NAV_EXIT = "exit"
_NAV_BACK = "back"
