"""AURA CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from aura import __version__
from aura.agents.registry import AgentRegistry
from aura.api import agent, configure, create_agent
from aura.core.spine import AuditSpine
from aura.runtime.python import run_script


def main() -> None:
    parser = argparse.ArgumentParser(prog="aura", description="AURA Harness")
    parser.add_argument(
        "--home",
        help="AURA home directory (default: ~/.aura or AURA_HOME)",
    )
    parser.add_argument(
        "--project",
        help="Project directory for .aura/ storage",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Show version")

    agent_p = sub.add_parser("agent", help="Manage agents")
    agent_sub = agent_p.add_subparsers(dest="agent_command")

    create_p = agent_sub.add_parser("create", help="Create an agent")
    create_p.add_argument("name", nargs="?", help="Agent name")
    create_p.add_argument("--purpose", help="Agent purpose / drive")
    create_p.add_argument("--mode", default="script", help="Default session mode")

    agent_sub.add_parser("list", help="List agents")

    show_p = agent_sub.add_parser("show", help="Show agent profile")
    show_p.add_argument("name", help="Agent name or AURA-000n id")

    run_p = sub.add_parser("run", help="Run a script under an agent session")
    run_p.add_argument("target", help="Agent name or script path")
    run_p.add_argument("script", nargs="?", help="Script path when agent given first")
    run_p.add_argument("--mode", help="Session mode: script, task, continuous")

    logs_p = sub.add_parser("logs", help="Print session JSONL")
    logs_p.add_argument("session_id", help="Session id")

    export_p = sub.add_parser("export", help="Print session summary JSON")
    export_p.add_argument("session_id", help="Session id")

    args = parser.parse_args()
    _apply_global_args(args)

    if args.command == "version":
        print(f"aura-harness {__version__}")
    elif args.command == "agent":
        _cmd_agent(args)
    elif args.command == "run":
        _cmd_run(args)
    elif args.command == "logs":
        _cmd_logs(args)
    elif args.command == "export":
        _cmd_export(args)
    elif args.command is None:
        parser.print_help()
    else:
        parser.print_help()


def _apply_global_args(args: argparse.Namespace) -> None:
    if getattr(args, "home", None):
        os.environ["AURA_HOME"] = args.home
    project = getattr(args, "project", None)
    configure(project_dir=project)


def _cmd_agent(args: argparse.Namespace) -> None:
    if args.agent_command == "create":
        handle = create_agent(name=args.name, purpose=args.purpose, default_mode=args.mode)
        print(json.dumps(handle.profile.to_dict(), indent=2))
    elif args.agent_command == "list":
        reg = AgentRegistry()
        for p in reg.list_agents():
            label = p.name or "(unnamed)"
            print(f"{p.aura_id}  {label}")
    elif args.agent_command == "show":
        reg = AgentRegistry()
        try:
            profile = reg.get_by_name(args.name)
        except KeyError:
            profile = reg.get_by_id(args.name)
        print(json.dumps(profile.to_dict(), indent=2))
    else:
        print("usage: aura agent {create|list|show}", file=sys.stderr)
        sys.exit(1)


def _cmd_run(args: argparse.Namespace) -> None:
    script: Path | None = None
    agent_name: str | None = None
    if args.script:
        agent_name = args.target
        script = Path(args.script)
    elif Path(args.target).suffix == ".py":
        script = Path(args.target)
    else:
        agent_name = args.target
        print("error: provide a .py script path", file=sys.stderr)
        sys.exit(1)

    handle = agent(agent_name) if agent_name else agent()
    result = run_script(handle, script, mode=args.mode)
    print(json.dumps(result, indent=2))


def _cmd_logs(args: argparse.Namespace) -> None:
    from aura.config import get_config

    path = get_config().sessions_dir() / f"{args.session_id}.jsonl"
    for row in AuditSpine.read_jsonl(path):
        print(json.dumps(row))


def _cmd_export(args: argparse.Namespace) -> None:
    from aura.config import get_config

    path = get_config().sessions_dir() / f"{args.session_id}.summary.json"
    if not path.is_file():
        print(f"not found: {path}", file=sys.stderr)
        sys.exit(1)
    print(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
