#!/usr/bin/env python3

# Detailed test script to understand how iter_messages works.
import asyncio
import os

from telethon.sync import TelegramClient


async def detailed_test():
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

    # Test 1: Just count all messages without any filters
    print("\n=== Test 1: Count all messages (no limit) ===")
    count = 0
    async for msg in client.iter_messages(entity):
        if msg.text or msg.media:
            count += 1
        if count >= 100:  # Stop early for testing
            break
    print(f"Total messages (first 100): {count}")

    # Test 2: Try with a higher limit
    print(r"\n=== Test 2: Count messages with limit=1000 ===")
    count = 0
    async for msg in client.iter_messages(entity, limit=1000):
        if msg.text or msg.media:
            count += 1
    print(f"Total messages with limit=1000: {count}")

    # Test 3: Try with reverse=True
    print(r"\n=== Test 3: Count messages with reverse=True ===")
    count = 0
    async for msg in client.iter_messages(entity, reverse=True):
        if msg.text or msg.media:
            count += 1
        if count >= 100:  # Stop early for testing
            break
    print(f"Total messages with reverse=True (first 100): {count}")

    # Test 4: Try with offset_id=0
    print(r"\n=== Test 4: Count messages with offset_id=0 ===")
    count = 0
    async for msg in client.iter_messages(entity, offset_id=0):
        if msg.text or msg.media:
            count += 1
        if count >= 100:  # Stop early for testing
            break
    print(f"Total messages with offset_id=0 (first 100): {count}")

    # Test 5: Try inspecting the iterator object itself
    print(r"\n=== Test 5: Inspect iterator object ===")
    iterator = client.iter_messages(entity)
    print(f"Iterator type: {type(iterator)}")
    print(
        f"Iterator attributes: {[attr for attr in dir(iterator) if not attr.startswith('_')]}"
    )

    # Test 6: Try getting just one message to see what we get
    print(r"\n=== Test 6: Get first message ===")
    async for msg in client.iter_messages(entity, limit=1):
        print(f"Message ID: {msg.id}")
        print(f"Message text: {msg.text[:100] if msg.text else '(no text)'}")
        print(f"Message date: {msg.date}")
        print(f"Message type: {type(msg)}")
        break

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(detailed_test())
