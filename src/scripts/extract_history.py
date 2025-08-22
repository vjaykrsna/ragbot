import asyncio
import logging
import os
import sqlite3
import sys

from telethon.sync import TelegramClient

from src.core.app import initialize_app
from src.history_extractor.storage import Storage
from src.history_extractor.telegram_extractor import TelegramExtractor


async def main():
    # Orchestrates the Telegram message extraction process.
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
    print(f"👤 Logged in as: {me.first_name} (@{me.username})")

    if not settings.telegram.group_ids:
        print(
            "⚠️ No GROUP_IDS found in .env file. Please add the group/channel IDs to scrape."
        )
        return

    storage = Storage(app_context)
    extractor = TelegramExtractor(client, storage)

    group_ids = settings.telegram.group_ids
    last_msg_ids = storage.load_last_msg_ids()

    print(f"🏢 Starting extraction of {len(group_ids)} groups...")

    total_messages_extracted = 0
    for i, gid in enumerate(group_ids, 1):
        try:
            # Get group info for better display
            entity = await client.get_entity(gid)
            group_name = getattr(entity, "title", f"Group {gid}")
            sys.stdout.write(
                f"\\r📂 Processing group {i}/{len(group_ids)}: '{group_name}'"
            )
            sys.stdout.flush()

            # Process this group
            count = await extractor.extract_from_group_id(gid, last_msg_ids)
            total_messages_extracted += count

            # Save progress after each group to ensure we don't lose progress
            storage.save_last_msg_ids(last_msg_ids)
            print(f"\\n💾 Saved progress for group '{group_name}'")

        except Exception as e:
            logging.error(
                f"❌ Failed to process group {i}/{len(group_ids)} '{group_name}': {e}"
            )

    await client.disconnect()
    print(
        f"\\n🎉 Extraction complete. Total messages extracted: {total_messages_extracted}"
    )


if __name__ == "__main__":
    # Using asyncio.run() is the modern way to run an async main function.
    asyncio.run(main())
