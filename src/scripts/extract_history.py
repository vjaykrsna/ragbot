import asyncio
import logging
import os

from telethon.sync import TelegramClient

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
    client = TelegramClient(
        session_path, settings.telegram.api_id, settings.telegram.api_hash
    )

    os.makedirs(settings.paths.raw_data_dir, exist_ok=True)

    await client.start(
        phone=settings.telegram.phone, password=settings.telegram.password
    )

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

    for gid in group_ids:
        await extractor.extract_from_group_id(gid, last_msg_ids)

    storage.save_last_msg_ids(last_msg_ids)

    await client.disconnect()
    logging.info("\n🎉 Extraction complete. Client disconnected.")


if __name__ == "__main__":
    # Using asyncio.run() is the modern way to run an async main function.
    asyncio.run(main())
