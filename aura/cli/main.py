"""AURA CLI entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

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

    set_p = agent_sub.add_parser("set", help="Update agent profile fields")
    set_p.add_argument("name", help="Name, agent_ref, or aura_id")
    set_p.add_argument("--ref", dest="agent_ref", help="Stable agent_ref (tenant/slug)")
    set_p.add_argument("--purpose", help="Agent purpose / drive")
    set_p.add_argument("--policy-version", help="Policy version label")
    set_p.add_argument("--mode", dest="default_mode", help="Default session mode")
    set_p.add_argument(
        "--skill",
        action="append",
        dest="skills",
        help="Skill id (repeatable; replaces skills list)",
    )
    set_p.add_argument(
        "--variable",
        action="append",
        dest="variables",
        help="Profile variable key=value (repeatable; merges)",
    )
    set_p.add_argument(
        "--id",
        action="append",
        dest="ids",
        help="External id key=value (repeatable; merges)",
    )
    set_p.add_argument("--rules-file", type=Path, help="JSON file with rules array")
    set_p.add_argument("--rules-json", help="Inline JSON array of rules")

    config_p = sub.add_parser("config", help="Configuration")
    config_sub = config_p.add_subparsers(dest="config_command")
    config_sub.add_parser("show", help="Show merged config and paths")

    paths_p = sub.add_parser("paths", help="Path resolution and storage")
    paths_sub = paths_p.add_subparsers(dest="paths_command")
    paths_sub.add_parser("show", help="Show resolved paths (default)")
    set_proj = paths_sub.add_parser("set-project", help="Persist default project directory")
    set_proj.add_argument("directory", help="Project directory path")
    set_storage = paths_sub.add_parser("set-storage", help="Persist storage mode")
    set_storage.add_argument("mode", choices=["global", "project"], help="Storage mode")

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

    verify_p = sub.add_parser("verify", help="Verify exported session data")
    verify_sub = verify_p.add_subparsers(dest="verify_command")
    chain_p = verify_sub.add_parser("chain", help="Validate a JSONL audit hash chain")
    chain_p.add_argument("path", help="Path to an exported session JSONL file")

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
    if args.command == "config":
        if args.config_command == "show" or args.config_command is None:
            return commands.cmd_config_show()
        print("usage: aura config show", file=sys.stderr)
        return 1
    if args.command == "paths":
        return _dispatch_paths(args)
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
    if args.command == "verify":
        if args.verify_command == "chain":
            return commands.cmd_verify_chain(args.path)
        print("usage: aura verify chain <path>", file=sys.stderr)
        return 1
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
    if args.agent_command == "set":
        return commands.cmd_agent_set(
            args.name,
            agent_ref=args.agent_ref,
            purpose=args.purpose,
            policy_version=args.policy_version,
            default_mode=args.default_mode,
            skills=args.skills,
            variables=args.variables,
            ids=args.ids,
            rules_file=args.rules_file,
            rules_json=args.rules_json,
        )
    print("usage: aura agent {create|list|show|set}", file=sys.stderr)
    return 1


def _dispatch_paths(args: argparse.Namespace) -> int:
    if args.paths_command in (None, "show"):
        return commands.cmd_paths()
    if args.paths_command == "set-project":
        return commands.cmd_paths_set_project(args.directory)
    if args.paths_command == "set-storage":
        return commands.cmd_paths_set_storage(args.mode)
    return 2


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
