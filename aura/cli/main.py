"""AURA CLI entry point."""

from __future__ import annotations

import argparse
import os
import sys

from aura import __version__
from aura.cli import commands
from aura.cli.help_ui import cmd_help
from aura.cli.interactive import cmd_interactive
from aura.config import configure


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aura", description="AURA Harness", add_help=False)
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="Show grouped help and exit.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"aura-harness {__version__}",
    )
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

    return parser


def apply_global_args(args: argparse.Namespace) -> None:
    if getattr(args, "home", None):
        os.environ["AURA_HOME"] = args.home
    project = getattr(args, "project", None)
    configure(project_dir=project)


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "version":
        return commands.cmd_version()
    if args.command == "agent":
        return _dispatch_agent(args)
    if args.command == "run":
        return commands.cmd_run(args.target, args.script, mode=args.mode)
    if args.command == "logs":
        return commands.cmd_logs(args.session_id)
    if args.command == "export":
        return commands.cmd_export(args.session_id)
    if args.command == "export-otel":
        return commands.cmd_export_otel(args.session_id)
    if args.command == "compare":
        return commands.cmd_compare(args.session_a, args.session_b)
    if args.command is None:
        if args.help:
            cmd_help()
            return 0
        cmd_interactive()
        return 0
    return 2


def _dispatch_agent(args: argparse.Namespace) -> int:
    if args.agent_command == "create":
        return commands.cmd_agent_create(
            args.name,
            agent_ref=args.agent_ref,
            aura_id=args.aura_id,
            purpose=args.purpose,
            policy_version=args.policy_version,
            mode=args.mode,
        )
    if args.agent_command == "list":
        return commands.cmd_agent_list()
    if args.agent_command == "show":
        return commands.cmd_agent_show(args.name)
    print("usage: aura agent {create|list|show}", file=sys.stderr)
    return 1


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    apply_global_args(args)

    if args.help and args.command is not None:
        parser.print_help()
        raise SystemExit(0)

    code = dispatch(args)
    if code:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
