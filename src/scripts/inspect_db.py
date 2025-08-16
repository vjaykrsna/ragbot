import argparse
from typing import Any, Dict

import chromadb
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.utils import config
from src.utils.logger import setup_logging

setup_logging()

console = Console()


def display_nugget_details(nuggets: Dict[str, Any]):
    """Displays the details of the most recent nuggets in a rich table."""
    if not nuggets or not nuggets.get("metadatas"):
        console.print(Panel("No nuggets found to display.", style="yellow"))
        return

    # Sort nuggets by timestamp in descending order to get the most recent
    sorted_indices = sorted(
        range(len(nuggets["metadatas"])),
        key=lambda i: nuggets["metadatas"][i].get("timestamp", ""),
        reverse=True,
    )

    table = Table(
        title="Most Recent Knowledge Nuggets",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Timestamp", style="dim", width=20)
    table.add_column("Topic", style="bold green")
    table.add_column("Status", style="cyan")
    table.add_column("Summary", no_wrap=False)

    for i in sorted_indices:
        meta = nuggets["metadatas"][i]
        summary = nuggets["documents"][i]
        table.add_row(
            meta.get("timestamp", "N/A"),
            meta.get("topic", "N/A"),
            meta.get("status", "N/A"),
            summary,
        )

    console.print(table)


def inspect_database(limit: int):
    """
    Connects to the ChromaDB and provides a detailed overview of its contents.
    """
    try:
        console.print(
            Panel(
                f"Connecting to DB at [bold cyan]{config.DB_PATH}[/] and collection [bold cyan]{config.COLLECTION_NAME}[/]",
                title="Database Inspection",
                expand=False,
            )
        )
        client = chromadb.PersistentClient(path=config.DB_PATH)

        try:
            collection = client.get_collection(name=config.COLLECTION_NAME)
            count = collection.count()

            summary_text = Text("Total items in collection: ", style="default")
            summary_text.append(str(count), style="bold green")
            console.print(summary_text)

            if count > 0:
                # Fetch more items than needed to ensure we can sort by recency
                fetch_limit = min(count, max(limit, 50))
                recent_nuggets = collection.get(
                    include=["metadatas", "documents"], limit=fetch_limit
                )
                # Display the most recent 'limit' nuggets
                display_nugget_details(recent_nuggets)

        except Exception:
            console.print(
                f"Could not inspect collection '{config.COLLECTION_NAME}'. It might not exist yet.",
                style="bold red",
            )

    except Exception as e:
        console.print(
            f"An error occurred during database inspection: {e}", style="bold red"
        )


def delete_collection(collection_name: str):
    """Deletes a specific collection from the database."""
    try:
        console.print(f"Connecting to database at path: [cyan]{config.DB_PATH}[/]")
        client = chromadb.PersistentClient(path=config.DB_PATH)

        console.print(
            f"--- Deleting Collection: '{collection_name}' ---", style="bold yellow"
        )
        try:
            client.delete_collection(name=collection_name)
            console.print(
                f"Collection '{collection_name}' deleted successfully.",
                style="bold green",
            )
        except Exception:
            console.print(
                f"Could not delete collection '{collection_name}'. It might not exist.",
                style="bold red",
            )

    except Exception as e:
        console.print(
            f"An error occurred during database management: {e}", style="bold red"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Inspect or manage the ChromaDB database."
    )
    parser.add_argument(
        "--delete",
        type=str,
        metavar="COLLECTION_NAME",
        help="The name of the collection to delete.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of recent items to display (default: 5).",
    )
    args = parser.parse_args()

    if args.delete:
        # A simple confirmation prompt
        response = input(
            f"Are you sure you want to delete the collection '{args.delete}'? This cannot be undone. (y/n): "
        )
        if response.lower() == "y":
            delete_collection(args.delete)
        else:
            console.print("Deletion cancelled.", style="yellow")
    else:
        inspect_database(args.limit)
