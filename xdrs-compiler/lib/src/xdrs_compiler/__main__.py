from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .compiler import Compiler
from .config import CompilerConfig

CONFIG_FILE = ".xdrs-compiler.yml"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="xdrs-compiler",
        description=(
            "Compile documents into XDRS policies and skills using an AI agent pipeline.\n\n"
            "When called with --input-dir, --xdrs-root, and --scope, saves the configuration "
            f"to {CONFIG_FILE} and runs the compiler.\n"
            f"When called with no arguments, reads {CONFIG_FILE} and runs the compiler."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input-dir", help="Directory containing source documents")
    parser.add_argument("--xdrs-root", help="Root directory for XDRS output (e.g. .xdrs)")
    parser.add_argument("--scope", help="XDRS scope name (e.g. myteam)")
    parser.add_argument(
        "--model",
        default=None,
        help="OpenAI model name (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="Working directory for intermediate files (default: .work)",
    )
    parser.add_argument(
        "--config",
        default=CONFIG_FILE,
        metavar="FILE",
        help=f"Config file path (default: {CONFIG_FILE})",
    )
    args = parser.parse_args()

    # Validate OPENAI_API_KEY early
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "Error: OPENAI_API_KEY environment variable is not set.\n"
            "Set it with:  export OPENAI_API_KEY=sk-...",
            file=sys.stderr,
        )
        sys.exit(1)

    config_path = Path(args.config)
    has_args = any([args.input_dir, args.xdrs_root, args.scope])

    if has_args:
        # Require all three core args when any one is provided
        missing = [
            flag
            for flag, val in [
                ("--input-dir", args.input_dir),
                ("--xdrs-root", args.xdrs_root),
                ("--scope", args.scope),
            ]
            if not val
        ]
        if missing:
            print(
                f"Error: The following arguments are required: {', '.join(missing)}",
                file=sys.stderr,
            )
            sys.exit(1)

        config = CompilerConfig(
            input_dir=args.input_dir,  # type: ignore[arg-type]
            xdrs_root=args.xdrs_root,  # type: ignore[arg-type]
            scope=args.scope,  # type: ignore[arg-type]
            model=args.model or "gpt-4o-mini",
            work_dir=args.work_dir or ".work",
        )
        config.save(config_path)
        print(f"Config saved to {config_path}")
    else:
        # No args — read config file
        if not config_path.exists():
            print(
                f"Error: No arguments provided and config file '{config_path}' not found.\n"
                "Run with --input-dir, --xdrs-root, and --scope to create a config file.",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            config = CompilerConfig.load(config_path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error reading config file '{config_path}': {exc}", file=sys.stderr)
            sys.exit(1)

        # Optional per-run overrides
        if args.model:
            config.model = args.model
        if args.work_dir:
            config.work_dir = args.work_dir

    compiler = Compiler(config)
    result = compiler.compile()
    print(result.summary())
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
