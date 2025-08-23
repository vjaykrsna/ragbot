import argparse
import asyncio
import inspect

import structlog

from src.scripts import extract_history, synthesize_knowledge

logger = structlog.get_logger(__name__)


def run_cli(argv: list[str]):
    """
    Parses command-line arguments and executes the corresponding command.
    This function is separate from main() to be easily testable.
    """
    parser = argparse.ArgumentParser(
        description="Data processing and knowledge synthesis pipeline."
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="sub-command help"
    )

    # --- Extract Command ---
    parser_extract = subparsers.add_parser(
        "extract", help="Extract message history from Telegram."
    )
    parser_extract.set_defaults(func=extract_history.main)

    # --- Synthesize Command ---
    parser_synthesize = subparsers.add_parser(
        "synthesize", help="Synthesize knowledge nuggets from conversations."
    )
    parser_synthesize.set_defaults(func=synthesize_knowledge.main)

    args = parser.parse_args(argv)

    logger.info(f"Executing command: {args.command}")
    if hasattr(args, "func"):
        if inspect.iscoroutinefunction(args.func):
            asyncio.run(args.func())
        else:
            args.func()
    logger.info(f"Command '{args.command}' finished.")


def main():
    """
    Main entry point for the application's command-line interface.
    """
    import sys

    run_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
