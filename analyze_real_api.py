#!/usr/bin/env python3
"""
Script to analyze real Pyrogram API responses using existing configuration.
"""

import asyncio
import os

# Add the src directory to the path so we can import our modules
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from pyrogram import Client

from src.core.app import initialize_app
from src.history_extractor.message_processor import get_message_details


def analyze_message_structure(message, indent=""):
    """Analyze the structure of a Pyrogram message object"""
    print(f"{indent}Message ID: {getattr(message, 'id', 'N/A')}")
    print(f"{indent}Type: {type(message).__name__}")

    # Key attributes we care about
    attrs_to_check = [
        "text",
        "date",
        "from_user",
        "sender_chat",
        "message_thread_id",
        "reply_to_message_id",
        "media",
        "poll",
        "service",
        "photo",
        "document",
        "video",
        "audio",
        "voice",
        "sticker",
        "has_protected_content",
        "edit_date",
        "views",
        "forwards",
    ]

    for attr in attrs_to_check:
        if hasattr(message, attr):
            value = getattr(message, attr, None)
            if value is not None:
                if attr == "date" and hasattr(value, "isoformat"):
                    print(f"{indent}  {attr}: {value.isoformat()}")
                elif attr in ["from_user", "sender_chat"]:
                    print(
                        f"{indent}  {attr}: {type(value).__name__} (ID: {getattr(value, 'id', 'N/A')})"
                    )
                elif attr == "poll":
                    print(f"{indent}  {attr}: {type(value).__name__}")
                    analyze_poll_structure(value, indent + "    ")
                else:
                    print(
                        f"{indent}  {attr}: {type(value).__name__} = {repr(value)[:50]}{'...' if len(repr(value)) > 50 else ''}"
                    )


def analyze_poll_structure(poll, indent=""):
    """Analyze the structure of a Pyrogram poll object"""
    print(f"{indent}Poll ID: {getattr(poll, 'id', 'N/A')}")

    poll_attrs = [
        "question",
        "options",
        "total_voter_count",
        "is_quiz",
        "is_anonymous",
        "close_period",
        "close_date",
    ]
    for attr in poll_attrs:
        if hasattr(poll, attr):
            value = getattr(poll, attr, None)
            if value is not None:
                if attr == "options":
                    print(f"{indent}  {attr}: List[{len(value)} options]")
                    if value:
                        first_option = value[0]
                        print(
                            f"{indent}    First option: {type(first_option).__name__}"
                        )
                        option_attrs = ["text", "voter_count", "correct"]
                        for opt_attr in option_attrs:
                            if hasattr(first_option, opt_attr):
                                opt_value = getattr(first_option, opt_attr, None)
                                print(f"{indent}      {opt_attr}: {repr(opt_value)}")
                else:
                    print(f"{indent}  {attr}: {type(value).__name__} = {repr(value)}")


def analyze_entity_structure(entity, indent=""):
    """Analyze the structure of a Pyrogram entity (chat) object"""
    print(f"{indent}Entity ID: {getattr(entity, 'id', 'N/A')}")
    print(f"{indent}Title: {getattr(entity, 'title', 'N/A')}")
    print(f"{indent}Type: {type(entity).__name__}")

    entity_attrs = ["is_forum", "access_hash", "username", "type", "photo"]
    for attr in entity_attrs:
        if hasattr(entity, attr):
            value = getattr(entity, attr, None)
            if value is not None:
                print(f"{indent}  {attr}: {type(value).__name__} = {repr(value)}")


async def main():
    """Main analysis function"""
    print("=== Real Pyrogram API Response Analysis ===")
    print()

    # Initialize app to get settings
    app_context = initialize_app()
    settings = app_context.settings

    # Use existing session
    session_path = os.path.join(settings.paths.root_dir, settings.telegram.session_name)
    print(f"Using session: {session_path}")

    # Create client with existing credentials
    client = Client(session_path, settings.telegram.api_id, settings.telegram.api_hash)

    async with client:
        # Get current user
        print("1. Current User (me):")
        me = await client.get_me()
        print(
            f"   Name: {getattr(me, 'first_name', 'N/A')} @{getattr(me, 'username', 'N/A')}"
        )
        print()

        # Analyze groups if configured
        if settings.telegram.group_ids:
            print(f"2. Analyzing {len(settings.telegram.group_ids)} configured groups:")

            for i, group_id in enumerate(
                settings.telegram.group_ids[:3]
            ):  # Limit to first 3
                try:
                    print(f"   Group {i + 1} (ID: {group_id}):")
                    entity = await client.get_chat(group_id)
                    analyze_entity_structure(entity, "     ")

                    # Check if it's a forum
                    is_forum = getattr(entity, "is_forum", False)
                    print(f"     Is Forum: {is_forum}")

                    # Get some messages
                    print("     Sample Messages:")
                    message_count = 0
                    async for message in client.get_chat_history(group_id, limit=3):
                        message_count += 1
                        print(f"     Message {message_count}:")
                        analyze_message_structure(message, "       ")

                        # Test our message processor
                        print("       Our Processing:")
                        msg_type, content, extra_data = get_message_details(message)
                        print(f"         Type: {msg_type}")
                        print(f"         Content length: {len(str(content))}")
                        print(f"         Extra data keys: {list(extra_data.keys())}")

                        if msg_type == "poll":
                            print(
                                f"         Poll question: {content.get('question', 'N/A')[:30]}..."
                            )
                            print(
                                f"         Poll options: {len(content.get('options', []))}"
                            )

                    if message_count == 0:
                        print("       No messages found")

                except Exception as e:
                    print(f"     Error analyzing group {group_id}: {e}")

                if i >= 2:  # Limit to 3 groups
                    break
        else:
            print("2. No groups configured in .env")

        print()
        print("=== Analysis Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
