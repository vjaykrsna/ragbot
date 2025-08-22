import asyncio
import logging
import os
import sqlite3

from telethon.sync import TelegramClient
from tqdm.asyncio import tqdm

from src.core.app import initialize_app
from src.history_extractor.storage import Storage
from src.history_extractor.telegram_extractor import TelegramExtractor


async def main():
    """Orchestrates the Telegram message extraction process."""
    # Initialize the application context
    app_context = initialize_app()
    settings = app_context.settings

    # Use project root to store session files so they are persistent across runs
    session_path = os.path.join(settings.paths.root_dir, settings.telegram.session_name)

    # Handle session file compatibility issues during client initialization
    try:
        client = TelegramClient(
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
            client = TelegramClient(
                session_path, settings.telegram.api_id, settings.telegram.api_hash
            )
        else:
            raise

    os.makedirs(settings.paths.raw_data_dir, exist_ok=True)

    # Handle session file compatibility issues during start
    try:
        await client.start(
            phone=settings.telegram.phone, password=settings.telegram.password
        )
    except sqlite3.OperationalError as e:
        if "no such column: version" in str(e):
            logging.warning("Session file incompatible. Creating a new one...")
            # Remove the incompatible session file
            session_files = [session_path, f"{session_path}.session"]
            for session_file in session_files:
                if os.path.exists(session_file):
                    os.remove(session_file)
                    logging.info(f"Removed incompatible session file: {session_file}")

            # Create a new client with the same parameters
            client = TelegramClient(
                session_path, settings.telegram.api_id, settings.telegram.api_hash
            )
            await client.start(
                phone=settings.telegram.phone, password=settings.telegram.password
            )
        else:
            raise

    me = await client.get_me()
    logging.info(f"👤 Logged in as: {me.first_name} (@{me.username})")

    if not settings.telegram.group_ids:
        logging.warning(
            "⚠️ No GROUP_IDS found in .env file. Please add the group/channel IDs to scrape."
        )
        return

    storage = Storage(app_context)
    extractor = TelegramExtractor(client, storage)

    group_ids = settings.telegram.group_ids
    last_msg_ids = storage.load_last_msg_ids()

    # Display group list upfront
    logging.info(f"🏢 Groups to process ({len(group_ids)} total):")
    for i, gid in enumerate(group_ids, 1):
        try:
            entity = await client.get_entity(gid)
            group_name = getattr(entity, "title", f"Group {gid}")
            logging.info(f"  {i:2d}. {group_name}")
        except Exception:
            logging.info(f"  {i:2d}. Group {gid} (name unavailable)")

    logging.info(f"🚀 Starting extraction of {len(group_ids)} groups...")

    # Overall progress bar for all groups with better configuration
    with tqdm(
        total=len(group_ids),
        desc="📊 Overall Progress",
        unit="group",
        colour="green",
        bar_format="{desc}: {percentage:3.0f}%|{bar}| {n}/{total} [{elapsed}]",
        leave=True,
        position=0,
    ) as overall_pbar:
        for i, gid in enumerate(group_ids, 1):
            try:
                # Get group info for better display
                entity = await client.get_entity(gid)
                group_name = getattr(entity, "title", f"Group {gid}")
                logging.info(
                    f"📂 Processing group {i}/{len(group_ids)}: '{group_name}'"
                )

                # Process this group with progress tracking
                await extractor.extract_from_group_id(gid, last_msg_ids)

                # Save progress after each group to ensure we don't lose progress
                storage.save_last_msg_ids(last_msg_ids)
                logging.info(f"💾 Saved progress for group '{group_name}'")

                overall_pbar.update(1)
                overall_pbar.set_postfix_str(f"✅ {group_name}")

            except Exception as e:
                logging.error(
                    f"❌ Failed to process group {i}/{len(group_ids)} '{group_name}': {e}"
                )
                overall_pbar.update(1)
                overall_pbar.set_postfix_str(f"❌ {group_name}")

    await client.disconnect()
    logging.info("\n🎉 Extraction complete. Client disconnected.")


if __name__ == "__main__":
    # Using asyncio.run() is the modern way to run an async main function.
    asyncio.run(main())
