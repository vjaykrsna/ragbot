import asyncio
import logging
from datetime import datetime

import telethon
from telethon.errors import FloodWaitError
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import GetForumTopicsRequest

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

    def __init__(self, client: TelegramClient, storage: Storage):
        self.client = client
        self.storage = storage

    async def extract_from_topic(self, entity, topic, last_msg_ids):
        """
        Extracts all new messages from a specific group topic.

        Args:
            entity: The entity to extract messages from.
            topic: The topic to extract messages from.
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

        iterator_kwargs = {"min_id": last_id, "reverse": True}
        if topic_id != 0:  # 0 is the 'General' topic in non-forum groups
            iterator_kwargs["reply_to"] = topic_id

        async for msg in self.client.iter_messages(entity, **iterator_kwargs):
            if isinstance(msg, telethon.tl.types.MessageService):
                continue
            if not msg.text and not msg.media:
                continue

            try:
                message_type, content, extra_data = get_message_details(msg)
            except Exception:
                logging.exception(f"Failed to process message {msg.id}. Skipping.")
                continue

            if not content:
                continue

            messages.append(
                {
                    "id": msg.id,
                    "date": msg.date.isoformat(),
                    "sender_id": msg.sender_id,
                    "message_type": message_type,
                    "content": content,
                    "extra_data": extra_data,
                    "reply_to_msg_id": msg.reply_to_msg_id,
                    "topic_id": topic_id,
                    "topic_title": topic_title,
                }
            )
            max_id = max(max_id, msg.id)

        if messages:
            full_title = f"{entity.title}_{topic_title}"
            self.storage.save_messages_to_db(full_title, topic_id, messages)
            last_msg_ids[last_id_key] = max_id

    async def extract_from_group_id(self, group_id, last_msg_ids):
        """
        Extracts messages from a specific group ID.

        Args:
            group_id: The ID of the group to extract messages from.
            last_msg_ids: A dictionary mapping topic keys to the last processed message ID.
        """
        try:
            entity = await self.client.get_entity(group_id)
            logging.info(f"\nProcessing Group: {entity.title} (ID: {group_id})")
            if entity.forum:
                try:
                    topics_result = await self.client(
                        GetForumTopicsRequest(
                            channel=entity,
                            offset_date=datetime.now(),
                            offset_id=0,
                            offset_topic=0,
                            limit=100,
                        )
                    )
                    if topics_result and hasattr(topics_result, "topics"):
                        logging.info(
                            f"Found {len(topics_result.topics)} topics. Iterating through them."
                        )
                        for topic in topics_result.topics:
                            await self.extract_from_topic(entity, topic, last_msg_ids)
                    else:
                        logging.info("  - Forum group with no topics found. Skipping.")
                except Exception:
                    logging.exception(
                        f"  - ❌ Error fetching topics for forum '{entity.title}'"
                    )
            else:
                logging.info("  - This is a regular group. Extracting from main chat.")
                general_topic = type("obj", (object,), {"id": 0, "title": "General"})()
                await self.extract_from_topic(entity, general_topic, last_msg_ids)
        except FloodWaitError as fwe:
            logging.warning(
                f"Flood wait error for group {group_id}. Waiting for {fwe.seconds} seconds."
            )
            await asyncio.sleep(fwe.seconds)
            await self.extract_from_group_id(group_id, last_msg_ids)  # Retry
        except Exception:
            logging.exception(f"❌ Error processing group {group_id}")
