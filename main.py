import argparse
import asyncio
import inspect
import logging

from src.scripts import extract_history, process_data, synthesize_knowledge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """
    Main entry point for the application's command-line interface.
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

    # --- Process Command ---
    parser_process = subparsers.add_parser(
        "process", help="Process raw data into structured conversations."
    )
    parser_process.set_defaults(func=process_data.main)

    # --- Synthesize Command ---
    parser_synthesize = subparsers.add_parser(
        "synthesize", help="Synthesize knowledge nuggets from conversations."
    )
    parser_synthesize.set_defaults(func=synthesize_knowledge.main)

    args = parser.parse_args()

    logger.info(f"Executing command: {args.command}")
    if hasattr(args, "func"):
        if inspect.iscoroutinefunction(args.func):
            asyncio.run(args.func())
        else:
            args.func()
    logger.info(f"Command '{args.command}' finished.")


if __name__ == "__main__":
    main()
