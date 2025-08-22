import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.raw.functions.channels import GetForumTopics
from pyrogram.raw.types import InputChannel

from src.history_extractor.message_processor import get_message_details
from src.history_extractor.storage import Storage
from src.history_extractor.utils import normalize_title


class TelegramExtractor:
    """
    Extracts messages from Telegram groups and topics.

    Args:
        client: The Telegram client.
        storage: The storage object.
    """

    def __init__(self, client: Client, storage: Storage):
        self.client = client
        self.storage = storage

    async def extract_from_topic(
        self, entity: Any, topic: Any, last_msg_ids: Dict[str, int]
    ) -> None:
        """
        Extracts all new messages from a specific group topic or regular group.

        Args:
            entity: The entity to extract messages from.
            topic: The topic to extract messages from (for forums) or a mock topic object with id=0 for regular groups.
            last_msg_ids: A dictionary mapping topic keys to the last processed message ID.
        """
        messages = []
        group_id = entity.id
        topic_id = topic.id
        topic_title = normalize_title(getattr(topic, "title", "General"))
        last_id_key = f"{group_id}_{topic_id}"
        last_id = last_msg_ids.get(last_id_key, 0)
        max_id = 0

        logging.info(
            f"  - 📥 Extracting from topic: '{topic_title}' (ID: {topic_id}) [Since message ID > {last_id}]"
        )

        # Use offset_id instead of min_id and get_chat_history instead of iter_messages
        # Pyrogram's get_chat_history returns messages in reverse chronological order by default
        # For topics, we need to filter messages by message_thread_id
        start_time = datetime.now()
        processed_count = 0
        saved_count = 0
        last_update_time = start_time

        async for msg in self.client.get_chat_history(
            entity.id if hasattr(entity, "id") else entity, offset_id=last_id
        ):
            # For topics, filter by message_thread_id
            msg_thread_id = getattr(msg, "message_thread_id", 0) or 0
            if topic_id == 0:
                # For general topic, include messages with no thread ID (general messages)
                if msg_thread_id != 0:
                    continue
            else:
                # For specific topics, only include messages with matching thread ID
                if msg_thread_id != topic_id:
                    continue
            # Skip service messages
            if getattr(msg, "service", False):
                continue
            # Skip messages without text or media
            if not getattr(msg, "text", None) and not getattr(msg, "media", None):
                continue

            try:
                message_type, content, extra_data = get_message_details(msg)
            except Exception as e:
                logging.debug(f"Failed to process message {msg.id}: {e}")
                processed_count += 1
                continue

            if not content:
                processed_count += 1
                continue

            # Get sender information
            sender_id = None
            if hasattr(msg, "from_user") and msg.from_user:
                sender_id = msg.from_user.id
            elif hasattr(msg, "sender_chat") and msg.sender_chat:
                sender_id = msg.sender_chat.id

            messages.append(
                {
                    "id": msg.id,
                    "date": msg.date.isoformat()
                    if isinstance(msg.date, datetime)
                    else datetime.fromtimestamp(msg.date).isoformat(),
                    "sender_id": sender_id,
                    "message_type": message_type,
                    "content": content,
                    "extra_data": extra_data,
                    "reply_to_msg_id": getattr(msg, "reply_to_message_id", None),
                    "topic_id": topic_id,
                    "topic_title": topic_title,
                    "source_name": entity.title
                    if hasattr(entity, "title")
                    else str(entity),
                    "source_group_id": entity.id if hasattr(entity, "id") else group_id,
                    "ingestion_timestamp": datetime.now().isoformat(),
                }
            )
            max_id = max(max_id, msg.id)
            saved_count += 1
            processed_count += 1

            # Update progress display every 100 messages or every 2 seconds
            current_time = datetime.now()
            elapsed_since_last_update = (
                current_time - last_update_time
            ).total_seconds()
            if processed_count % 100 == 0 or elapsed_since_last_update > 2:
                elapsed_total = (current_time - start_time).total_seconds()
                speed = processed_count / elapsed_total if elapsed_total > 0 else 0
                # Use \r to overwrite the same line
                print(
                    f"\r    💬 {topic_title}: {processed_count} messages processed, "
                    f"{saved_count} saved, {speed:.1f} msg/sec",
                    end="",
                    flush=True,
                )
                last_update_time = current_time

        if not processed_count:
            logging.info(f"    📝 No new messages in '{topic_title}'")
            return

        # Final status update
        elapsed_total = (datetime.now() - start_time).total_seconds()
        speed = processed_count / elapsed_total if elapsed_total > 0 else 0
        print(
            f"\r    ✅ {topic_title}: {processed_count} messages processed, "
            f"{saved_count} saved, {speed:.1f} msg/sec"
        )

        if messages:
            full_title = f"{entity.title}_{topic_title}"
            self.storage.save_messages_to_db(full_title, topic_id, messages)
            last_msg_ids[last_id_key] = max_id

    async def extract_from_group_id(
        self, group_id: int, last_msg_ids: Dict[str, int]
    ) -> None:
        """
        Extracts messages from a specific group ID.

        Args:
            group_id: The ID of the group to extract messages from.
            last_msg_ids: A dictionary mapping topic keys to the last processed message ID.
        """
        try:
            entity = await self.client.get_chat(group_id)
            logging.info(f"\nProcessing Group: {entity.title} (ID: {group_id})")

            # Try to get forum topics regardless of is_forum flag
            # This handles cases where is_forum is incorrectly reported as False
            topics = []
            try:
                # Create InputChannel object for Pyrogram
                input_channel = InputChannel(
                    channel_id=entity.id,
                    access_hash=getattr(entity, "access_hash", 0),
                )

                # Use Pyrogram's raw function to get forum topics
                topics_result = await self.client.invoke(
                    GetForumTopics(
                        channel=input_channel,
                        offset_date=int(datetime.now().timestamp()),
                        offset_id=0,
                        offset_topic=0,
                        limit=100,
                    )
                )
                if topics_result and hasattr(topics_result, "topics"):
                    topics = topics_result.topics
            except Exception as e:
                # If we can't get topics, it might be a regular group or there was an error
                logging.debug(
                    f"  - Could not fetch topics (might be regular group): {e}"
                )

            if topics:
                logging.info(f"📋 Found {len(topics)} topics:")

                # Display topic list upfront
                for i, topic in enumerate(topics, 1):
                    topic_title = normalize_title(getattr(topic, "title", "General"))
                    logging.info(f"  {i:2d}. {topic_title}")

                logging.info(f"🔄 Starting extraction of {len(topics)} topics...")

                # Process topics with progress tracking
                for i, topic in enumerate(topics, 1):
                    topic_title = normalize_title(getattr(topic, "title", "General"))
                    logging.info(
                        f"📊 Processing topic {i}/{len(topics)}: '{topic_title}'"
                    )
                    await self.extract_from_topic(entity, topic, last_msg_ids)
            else:
                # Check if it's marked as a forum but has no topics, or if it's a regular group
                is_forum = getattr(entity, "is_forum", False)
                if is_forum:
                    logging.info("  - Forum group with no topics found. Skipping.")
                else:
                    logging.info(
                        "  - This is a regular group. Extracting from main chat."
                    )
                    general_topic = type(
                        "obj", (object,), {"id": 0, "title": "General"}
                    )()
                    await self.extract_from_topic(entity, general_topic, last_msg_ids)
        except FloodWait as fwe:
            logging.warning(
                f"Flood wait error for group {group_id}. Waiting for {fwe.value} seconds."
            )
            # Show a message every 30 seconds while waiting
            wait_time = fwe.value
            while wait_time > 0:
                if wait_time % 30 == 0 or wait_time < 30:
                    logging.info(f"Waiting for {wait_time} more seconds...")
                await asyncio.sleep(min(30, wait_time))
                wait_time -= 30
            await self.extract_from_group_id(group_id, last_msg_ids)  # Retry
        except Exception as e:
            logging.exception(f"❌ Error processing group {group_id}: {e}")
