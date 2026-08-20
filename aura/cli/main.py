"""AURA CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from aura import __version__
from aura.agents.registry import AgentRegistry, AgentNotFoundError
from aura.api import agent, configure, create_agent
from aura.core.compare import compare_sessions
from aura.core.spine import AuditSpine
from aura.exporters.otel import export_session_otel
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
    create_p.add_argument("name", nargs="?", help="Agent name or agent_ref")
    create_p.add_argument("--ref", dest="agent_ref", help="Stable agent_ref (tenant/slug)")
    create_p.add_argument("--aura-id", help="Supply your own internal aura_id")
    create_p.add_argument("--purpose", help="Agent purpose / drive")
    create_p.add_argument("--policy-version", default="1", help="Policy version label")
    create_p.add_argument("--mode", default="script", help="Default session mode")

    agent_sub.add_parser("list", help="List agents")

    show_p = agent_sub.add_parser("show", help="Show agent profile")
    show_p.add_argument("name", help="Name, agent_ref, or aura_id")

    run_p = sub.add_parser("run", help="Run a script under an agent session")
    run_p.add_argument("target", help="Agent name or script path")
    run_p.add_argument("script", nargs="?", help="Script path when agent given first")
    run_p.add_argument("--mode", help="Session mode: script, task, continuous")

    logs_p = sub.add_parser("logs", help="Print session JSONL")
    logs_p.add_argument("session_id", help="Session id")

    export_p = sub.add_parser("export", help="Print session summary JSON")
    export_p.add_argument("session_id", help="Session id")

    otel_p = sub.add_parser("export-otel", help="Export session as OTel-style JSONL")
    otel_p.add_argument("session_id", help="Session id")

    compare_p = sub.add_parser("compare", help="Compare two session summaries")
    compare_p.add_argument("session_a", help="First session id")
    compare_p.add_argument("session_b", help="Second session id")

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
    elif args.command == "export-otel":
        _cmd_export_otel(args)
    elif args.command == "compare":
        _cmd_compare(args)
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
        handle = create_agent(
            name=args.name,
            agent_ref=args.agent_ref,
            aura_id=args.aura_id,
            purpose=args.purpose,
            policy_version=args.policy_version,
            default_mode=args.mode,
        )
        print(json.dumps(handle.profile.to_dict(), indent=2))
    elif args.agent_command == "list":
        reg = AgentRegistry()
        for p in reg.list_agents():
            ref = p.agent_ref or "-"
            label = p.name or "(unnamed)"
            print(f"{p.aura_id}  {ref}  {label}")
    elif args.agent_command == "show":
        reg = AgentRegistry()
        try:
            profile = reg.resolve(args.name)
        except AgentNotFoundError:
            print(f"not found: {args.name}", file=sys.stderr)
            sys.exit(1)
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


def _cmd_export_otel(args: argparse.Namespace) -> None:
    from aura.config import get_config

    path = export_session_otel(args.session_id, get_config().sessions_dir())
    print(path.read_text(encoding="utf-8"))


def _cmd_compare(args: argparse.Namespace) -> None:
    from aura.config import get_config

    base = get_config().sessions_dir()
    result = compare_sessions(
        base / f"{args.session_a}.summary.json",
        base / f"{args.session_b}.summary.json",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
