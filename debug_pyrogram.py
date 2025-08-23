import asyncio
import os

from pyrogram import Client

# This script will help us understand the actual structure of Pyrogram objects
# We'll need to set up a proper client to see real data


async def inspect_pyrogram_objects():
    """Inspect the actual structure of Pyrogram objects"""
    # You would need to set these values in your .env file
    api_id = int(os.getenv("API_ID", "12345"))
    api_hash = os.getenv("API_HASH", "your_api_hash")
    session_name = os.getenv("SESSION_NAME", "debug_session")

    # Create a client
    client = Client(session_name, api_id, api_hash)

    async with client:
        # Get the current user (me)
        me = await client.get_me()
        print("=== ME OBJECT ===")
        print(f"Type: {type(me)}")
        print(f"Attributes: {[attr for attr in dir(me) if not attr.startswith('_')]}")
        print(f"First Name: {getattr(me, 'first_name', 'N/A')}")
        print(f"Username: {getattr(me, 'username', 'N/A')}")
        print()

        # Try to get a chat (you would need to set GROUP_IDS in your .env)
        group_ids = os.getenv("GROUP_IDS", "")
        if group_ids:
            group_id = int(group_ids.split(",")[0])
            try:
                chat = await client.get_chat(group_id)
                print("=== CHAT OBJECT ===")
                print(f"Type: {type(chat)}")
                print(
                    f"Attributes: {[attr for attr in dir(chat) if not attr.startswith('_')]}"
                )
                print(f"ID: {getattr(chat, 'id', 'N/A')}")
                print(f"Title: {getattr(chat, 'title', 'N/A')}")
                print(f"Is Forum: {getattr(chat, 'is_forum', 'N/A')}")
                print()

                # Get some messages
                async for message in client.get_chat_history(group_id, limit=5):
                    print("=== MESSAGE OBJECT ===")
                    print(f"Type: {type(message)}")
                    print(f"ID: {getattr(message, 'id', 'N/A')}")
                    print(f"Text: {getattr(message, 'text', 'N/A')[:50]}...")
                    print(f"Date: {getattr(message, 'date', 'N/A')}")
                    print(
                        f"Has message_thread_id: {hasattr(message, 'message_thread_id')}"
                    )
                    if hasattr(message, "message_thread_id"):
                        print(
                            f"Message Thread ID: {getattr(message, 'message_thread_id', 'N/A')}"
                        )
                    print(f"Has from_user: {hasattr(message, 'from_user')}")
                    if hasattr(message, "from_user") and message.from_user:
                        print(
                            f"From User ID: {getattr(message.from_user, 'id', 'N/A')}"
                        )
                    print(f"Has sender_chat: {hasattr(message, 'sender_chat')}")
                    if hasattr(message, "sender_chat") and message.sender_chat:
                        print(
                            f"Sender Chat ID: {getattr(message.sender_chat, 'id', 'N/A')}"
                        )
                    print(
                        f"Has reply_to_message_id: {hasattr(message, 'reply_to_message_id')}"
                    )
                    if hasattr(message, "reply_to_message_id"):
                        print(
                            f"Reply To Message ID: {getattr(message, 'reply_to_message_id', 'N/A')}"
                        )
                    print(f"Has media: {hasattr(message, 'media')}")
                    print()
                    break  # Just show one message
            except Exception as e:
                print(f"Error getting chat: {e}")


if __name__ == "__main__":
    asyncio.run(inspect_pyrogram_objects())
