import asyncio
import logging
import os
import sqlite3

import structlog
from pyrogram import Client

from src.core.app import initialize_app
from src.history_extractor.storage import Storage
from src.history_extractor.telegram_extractor import TelegramExtractor

logger = structlog.get_logger(__name__)


async def main():
    """Main entry point for the history extraction script."""
    # Initialize the application context
    app_context = initialize_app()
    settings = app_context.settings

    os.makedirs(settings.paths.raw_data_dir, exist_ok=True)

    # Use project root to store session files so they are persistent across runs
    session_path = os.path.join(settings.paths.root_dir, settings.telegram.session_name)

    # Handle session file compatibility issues during client initialization
    try:
        client = Client(
            session_path, settings.telegram.api_id, settings.telegram.api_hash
        )
    except sqlite3.OperationalError as e:
        if "no such column: version" in str(e):
            logging.warning(
                "Session file incompatible during initialization. Creating a new one..."
            )
            # Remove the incompatible session file
            session_files = [session_path, f"{session_path}.session"]
            for session_file in session_files:
                if os.path.exists(session_file):
                    os.remove(session_file)
                    logging.info(f"Removed incompatible session file: {session_file}")

            # Create a new client with the same parameters
            client = Client(
                session_path, settings.telegram.api_id, settings.telegram.api_hash
            )
        else:
            raise

    # Start the Pyrogram client
    async with client:
        # Get the current user
        me = await client.get_me()
        logging.info(
            f"👤 Logged in as: {me.first_name} (@{getattr(me, 'username', 'N/A')})"
        )

        if not settings.telegram.group_ids:
            logging.warning(
                "⚠️ No GROUP_IDS found in .env file. Please add the group/channel IDs to scrape."
            )
            return

        storage = Storage(app_context)
        extractor = TelegramExtractor(client, storage)

        group_ids = settings.telegram.group_ids
        last_msg_ids = storage.load_last_msg_ids()

        # Display group list upfront and cache group info to avoid redundant API calls
        logging.info(f"🏢 Groups to process ({len(group_ids)} total):")
        group_cache = {}  # Cache to store group info and avoid redundant API calls
        for i, gid in enumerate(group_ids, 1):
            try:
                entity = await client.get_chat(gid)
                group_cache[gid] = entity  # Cache the group info
                group_name = getattr(entity, "title", f"Group {gid}")
                logging.info(f"  {i:2d}. {group_name}")
            except Exception:
                logging.info(f"  {i:2d}. Group {gid} (name unavailable)")
                group_cache[gid] = None  # Cache the failure

        logging.info(f"🚀 Starting extraction of {len(group_ids)} groups...")

        # Create a copy of last_msg_ids for thread-safe access
        import copy

        last_msg_ids_copy = copy.deepcopy(last_msg_ids)

        # Process groups concurrently based on the concurrent_groups setting
        semaphore = asyncio.Semaphore(settings.telegram.extraction.concurrent_groups)

        async def process_group_with_semaphore(gid, i, total_groups):
            """Process a single group with semaphore control for concurrency limiting"""
            async with semaphore:
                group_name = f"Group {gid}"  # Default name
                try:
                    # Get group info from cache to avoid redundant API calls
                    entity = group_cache.get(gid)
                    if entity is None:
                        # If not in cache or failed previously, try to fetch it
                        entity = await client.get_chat(gid)
                        group_cache[gid] = entity  # Update cache

                    group_name = (
                        getattr(entity, "title", f"Group {gid}")
                        if entity
                        else f"Group {gid}"
                    )
                    logging.info(
                        f'📂 Processing group {i}/{total_groups}: "{group_name}"'
                    )

                    # Process this group with its own copy of last_msg_ids
                    # Note: This approach avoids race conditions but means progress tracking
                    # is not shared between concurrent groups
                    local_last_msg_ids = copy.deepcopy(last_msg_ids_copy)
                    await extractor.extract_from_group_id(
                        gid, local_last_msg_ids, entity
                    )

                    # Update the shared last_msg_ids with the results from this group
                    # This needs to be done in a thread-safe manner
                    for key, value in local_last_msg_ids.items():
                        if (
                            key not in last_msg_ids_copy
                            or value > last_msg_ids_copy[key]
                        ):
                            last_msg_ids_copy[key] = value

                    logging.info(
                        f'✅ Completed group {i}/{total_groups}: "{group_name}"'
                    )
                    return True

                except Exception as e:
                    logging.error(
                        f'❌ Failed to process group {i}/{total_groups} "{group_name}": {e}'
                    )
                    return False

        # Create tasks for all groups
        tasks = [
            process_group_with_semaphore(gid, i, len(group_ids))
            for i, gid in enumerate(group_ids, 1)
        ]

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Update the original last_msg_ids with the results
        last_msg_ids.update(last_msg_ids_copy)

        # Check results for any exceptions
        for i, result in enumerate(results, 1):
            if isinstance(result, Exception):
                logging.error(f"Unexpected error in group {i}: {result}")

        # Ensure all data is saved and resources are cleaned up
        try:
            storage.save_last_msg_ids(last_msg_ids)
            logging.info("\n💾 Progress tracking data saved.")
        except Exception as e:
            logging.error(f"\n❌ Failed to save progress tracking data: {e}")

        logging.info("\n🎉 Extraction complete.")


if __name__ == "__main__":
    asyncio.run(main())
