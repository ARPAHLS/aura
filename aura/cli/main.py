"""AURA CLI."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="aura", description="AURA Harness")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Show version")
    sub.add_parser("types", help="List registered type plugins")

    run_p = sub.add_parser("run", help="Run from manifest")
    run_p.add_argument("--manifest", "-m", help="Path to manifest YAML or JSON")

    args = parser.parse_args()
    if args.command == "version":
        from aura import __version__
        print(f"aura-harness {__version__}")
    elif args.command is None:
        parser.print_help()
    else:
        parser.print_help()
