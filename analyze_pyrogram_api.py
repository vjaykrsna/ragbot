#!/usr/bin/env python3
"""
Script to analyze the actual Pyrogram API response structure and verify
that our code is correctly extracting and storing the information.
"""

import asyncio
import os
from datetime import datetime

from pyrogram import Client

# Import our message processor to test it
from src.history_extractor.message_processor import get_message_details


def analyze_object_structure(obj, name="object", depth=0, max_depth=3):
    """Recursively analyze an object's structure"""
    if depth > max_depth:
        return

    indent = "  " * depth
    print(f"{indent}{name} ({type(obj).__name__}):")

    if obj is None:
        print(f"{indent}  None")
        return

    if isinstance(obj, (str, int, float, bool)):
        print(f"{indent}  Value: {repr(obj)}")
        return

    if isinstance(obj, (list, tuple)):
        print(f"{indent}  Length: {len(obj)}")
        if len(obj) > 0 and depth < max_depth:
            analyze_object_structure(obj[0], f"{name}[0]", depth + 1, max_depth)
        return

    if isinstance(obj, dict):
        print(f"{indent}  Keys: {list(obj.keys())}")
        if obj and depth < max_depth:
            first_key = list(obj.keys())[0]
            analyze_object_structure(
                obj[first_key], f"{name}['{first_key}']", depth + 1, max_depth
            )
        return

    # For regular objects, show attributes
    attrs = [
        attr
        for attr in dir(obj)
        if not attr.startswith("_") and not callable(getattr(obj, attr, None))
    ]
    print(f"{indent}  Attributes: {attrs[:20]}{'...' if len(attrs) > 20 else ''}")

    # Show some key attributes that we care about
    key_attrs = [
        "id",
        "text",
        "date",
        "from_user",
        "sender_chat",
        "message_thread_id",
        "reply_to_message_id",
        "media",
        "poll",
        "service",
    ]

    for attr in key_attrs:
        if hasattr(obj, attr):
            value = getattr(obj, attr, None)
            if value is not None:
                print(f"{indent}  {attr}: {type(value).__name__}")
                if depth < max_depth and attr in ["from_user", "sender_chat", "poll"]:
                    analyze_object_structure(value, f"{attr}", depth + 1, max_depth)


async def main():
    """Main function to analyze Pyrogram API responses"""
    print("=== Pyrogram API Response Structure Analysis ===\\n")

    # Load environment variables (assuming they're set)
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone = os.getenv("PHONE")
    session_name = os.getenv("SESSION_NAME", "debug_session")

    if not all([api_id, api_hash, phone]):
        print("Missing required environment variables: API_ID, API_HASH, PHONE")
        print("Please set them in your .env file")
        return

    api_id = int(api_id)

    # Create client
    client = Client(session_name, api_id, api_hash)

    async with client:
        # Get current user
        print("1. Analyzing current user (me):")
        me = await client.get_me()
        analyze_object_structure(me, "me")
        print()

        # Get a group to test with (if GROUP_IDS is set)
        group_ids = os.getenv("GROUP_IDS", "")
        if group_ids:
            group_id = int(group_ids.split(",")[0])
            print(f"2. Analyzing group {group_id}:")
            try:
                chat = await client.get_chat(group_id)
                analyze_object_structure(chat, f"chat_{group_id}")
                print()

                # Get some messages
                print(f"3. Analyzing messages from group {group_id}:")
                message_count = 0
                async for message in client.get_chat_history(group_id, limit=5):
                    message_count += 1
                    print(f"\\n--- Message {message_count} ---")
                    analyze_object_structure(message, f"message_{message_count}")

                    # Test our message processor
                    print("  Our get_message_details output:")
                    msg_type, content, extra_data = get_message_details(message)
                    print(f"    Type: {msg_type}")
                    print(
                        f"    Content: {repr(content)[:100]}{'...' if len(repr(content)) > 100 else ''}"
                    )
                    print(f"    Extra data keys: {list(extra_data.keys())}")

                    # Check specific attributes we use
                    print("  Key attributes check:")
                    print(
                        f"    has message_thread_id: {hasattr(message, 'message_thread_id')}"
                    )
                    if hasattr(message, "message_thread_id"):
                        print(
                            f"    message_thread_id: {getattr(message, 'message_thread_id', None)}"
                        )
                    print(f"    has text: {hasattr(message, 'text')}")
                    if hasattr(message, "text"):
                        text = getattr(message, "text", None)
                        print(
                            f"    text type: {type(text).__name__}, length: {len(text) if text else 0}"
                        )
                    print(f"    has media: {hasattr(message, 'media')}")
                    print(f"    has poll: {hasattr(message, 'poll')}")
                    if hasattr(message, "poll") and message.poll:
                        print(f"    poll type: {type(message.poll).__name__}")
                        analyze_object_structure(
                            message.poll, "poll", depth=2, max_depth=2
                        )
                    print(f"    has service: {hasattr(message, 'service')}")
                    print(f"    has from_user: {hasattr(message, 'from_user')}")
                    print(f"    has sender_chat: {hasattr(message, 'sender_chat')}")

                    if message_count >= 3:  # Just analyze first 3 messages
                        break

            except Exception as e:
                print(f"Error analyzing group {group_id}: {e}")
        else:
            print("No GROUP_IDS set in environment, skipping group analysis")

        # Test with a simple message creation to understand structure
        print("\\n4. Testing message structure with a simple example:")

        # Create a mock message-like object to test our understanding
        class MockMessage:
            def __init__(self):
                self.id = 12345
                self.text = "Test message"
                self.date = datetime.now()
                self.from_user = None
                self.sender_chat = None
                self.message_thread_id = None
                self.reply_to_message_id = None
                self.media = None
                self.service = False

        mock_msg = MockMessage()
        print("Mock message structure:")
        analyze_object_structure(mock_msg, "mock_msg")

        msg_type, content, extra_data = get_message_details(mock_msg)
        print("Our processing of mock message:")
        print(f"  Type: {msg_type}")
        print(f"  Content: {repr(content)}")
        print(f"  Extra data: {extra_data}")


if __name__ == "__main__":
    asyncio.run(main())
