#!/usr/bin/env python3

"""
Simple test script to understand how iter_messages works.
"""

import asyncio
import os

from telethon.sync import TelegramClient


async def test_iter_messages():
    # Load environment variables
    from src.core.app import initialize_app

    app_context = initialize_app()
    settings = app_context.settings

    # Initialize client
    session_path = os.path.join(settings.paths.root_dir, settings.telegram.session_name)
    client = TelegramClient(
        session_path, settings.telegram.api_id, settings.telegram.api_hash
    )

    await client.start(
        phone=settings.telegram.phone, password=settings.telegram.password
    )

    me = await client.get_me()
    print(f"Logged in as: {me.first_name} (@{me.username})")

    if not settings.telegram.group_ids:
        print("No GROUP_IDS found in .env file")
        return

    # Test with the first group
    group_id = settings.telegram.group_ids[0]
    entity = await client.get_entity(group_id)
    print(f"Testing with group: {entity.title} (ID: {group_id})")

    # Simple test - just count messages
    print("Counting messages...")
    count = 0
    async for msg in client.iter_messages(
        entity, limit=500
    ):  # Just first 500 for testing
        if msg.text or msg.media:
            count += 1
        if count % 50 == 0:
            print(f"Counted {count} messages so far...")

    print(f"Total messages in first 500: {count}")

    # Now try without limit
    print("Counting ALL messages (this might take a while)...")
    count_all = 0
    start_time = asyncio.get_event_loop().time()
    async for msg in client.iter_messages(entity):
        if msg.text or msg.media:
            count_all += 1
        # Break after a reasonable time for testing
        if count_all >= 1000:  # Just for testing
            break
        if count_all % 100 == 0:
            elapsed = asyncio.get_event_loop().time() - start_time
            rate = count_all / elapsed if elapsed > 0 else 0
            print(f"Counted {count_all} messages so far... ({rate:.1f} msg/sec)")
            if count_all >= 500:  # Stop early for testing
                break

    print(f"Total messages (first 1000): {count_all}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_iter_messages())
