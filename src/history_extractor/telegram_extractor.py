import asyncio
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict

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
        # Get settings from storage's app_context
        self.settings = storage.app_context.settings.telegram.extraction

    async def extract_from_topic(
        self, entity: Any, topic: Any, last_msg_ids: Dict[str, int]
    ) -> int:
        """
        Extracts all new messages from a specific group topic.

        Args:
            entity: The entity to extract messages from.
            topic: The topic to extract messages from.
            last_msg_ids: A dictionary mapping topic keys to the last processed message ID.

        Returns:
            The number of messages extracted.
        """
        group_id = entity.id
        topic_id = topic.id
        topic_title = normalize_title(getattr(topic, "title", "General"))
        last_id_key = f"{group_id}_{topic_id}"
        last_id = last_msg_ids.get(last_id_key, 0)
        max_id = 0

        # Start timing the extraction process
        start_time = time.time()

        # Collect messages with periodic updates
        message_list = []
        last_update_time = start_time
        update_interval = self.settings.ui_update_interval  # Use configured interval

        # Fetch all messages - simplest approach possible
        iterator_kwargs = {
            "wait_time": 1,
            "reverse": True,  # Process messages in chronological order (oldest first)
        }

        # Only set limit if we want to limit the number of messages
        # For fetching all messages, we don't set a limit

        if topic_id != 0:  # 0 is the 'General' topic in non-forum groups
            iterator_kwargs["reply_to"] = topic_id

        print(f"  Starting to fetch messages for {entity.title}/{topic_title}")

        message_count = 0
        async for msg in self.client.iter_messages(entity, **iterator_kwargs):
            message_count += 1

            # Skip service messages and empty messages
            if isinstance(msg, telethon.tl.types.MessageService):
                continue
            if not msg.text and not msg.media:
                continue

            # Only add messages that are newer than our last processed message
            if last_id > 0 and msg.id <= last_id:
                # When processing in chronological order, once we hit a message
                # that's already been processed, we can stop since all subsequent
                # messages should also have been processed
                print(
                    f"  Stopping extraction for {entity.title}/{topic_title} at message ID {msg.id} (last processed: {last_id})"
                )
                break

            message_list.append(msg)
            max_id = max(max_id, msg.id)

            # Periodic updates on the same line
            current_time = time.time()
            if (
                current_time - last_update_time >= update_interval
                and len(message_list) > 0
            ):
                elapsed = current_time - start_time
                speed = len(message_list) / elapsed if elapsed > 0 else 0
                sys.stdout.write(
                    f"\r-> {entity.title}/{topic_title} - {len(message_list)} messages extracted so far ({speed:.1f} msg/sec)"
                )
                sys.stdout.flush()
                last_update_time = current_time

        print(f"  Finished fetching messages. Total fetched: {message_count}")
        print(f"  Messages to process: {len(message_list)}")

        if not message_list:
            return 0

        # Calculate final extraction speed
        extraction_time = time.time() - start_time
        extraction_speed = (
            len(message_list) / extraction_time if extraction_time > 0 else 0
        )

        # Process messages with optimized batch processing
        batch_size = 250  # Keep at a reasonable value for memory efficiency
        message_batch = []
        total_saved = 0

        for msg in message_list:
            try:
                message_type, content, extra_data = get_message_details(msg)
            except Exception as e:
                logging.debug(f"Failed to process message {msg.id}: {e}")
                continue

            if not content:
                continue

            message_batch.append(
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
            total_saved += 1

            # When batch is full, save to database
            if len(message_batch) >= batch_size:
                if message_batch:
                    full_title = f"{entity.title}_{topic_title}"
                    self.storage.save_messages_to_db(
                        full_title, topic_id, message_batch
                    )
                    message_batch = []  # Clear the batch

        # Save any remaining messages in the batch
        if message_batch:
            full_title = f"{entity.title}_{topic_title}"
            self.storage.save_messages_to_db(full_title, topic_id, message_batch)

        # Update last message ID
        if total_saved > 0:
            last_msg_ids[last_id_key] = max_id
        elif message_count > 0 and max_id > last_msg_ids.get(last_id_key, 0):
            # If we processed messages but didn't save any (because they were already processed),
            # we still need to update the last_id to avoid reprocessing the same messages
            last_msg_ids[last_id_key] = max_id

        # Display final extraction information on a new line
        if extraction_time > 0:
            print(
                f"\n-> {entity.title}/{topic_title} - {total_saved} messages extracted ({extraction_speed:.1f} msg/sec)"
            )
        else:
            print(
                f"\n-> {entity.title}/{topic_title} - {total_saved} messages extracted"
            )

        return total_saved

    async def extract_from_group_id(
        self, group_id: int, last_msg_ids: Dict[str, int]
    ) -> int:
        """
        Extracts messages from a specific group ID.

        Args:
            group_id: The ID of the group to extract messages from.
            last_msg_ids: A dictionary mapping topic keys to the last processed message ID.

        Returns:
            The total number of messages extracted from the group.
        """
        total_messages = 0
        try:
            entity = await self.client.get_entity(group_id)
            start_time = time.time()

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
                        topics = topics_result.topics
                        print(f"-> {entity.title} - Found {len(topics)} topics")
                        # Process topics
                        for i, topic in enumerate(topics, 1):
                            topic_title = normalize_title(
                                getattr(topic, "title", "General")
                            )
                            sys.stdout.write(
                                f"\r-> {entity.title} - Processing topic {i}/{len(topics)}: {topic_title}"
                            )
                            sys.stdout.flush()
                            count = await self.extract_from_topic(
                                entity, topic, last_msg_ids
                            )
                            total_messages += count
                    else:
                        # Forum group with no topics found
                        pass
                except Exception as e:
                    logging.exception(
                        f"Error fetching topics for forum '{entity.title}': {e}"
                    )
            else:
                # Regular group - extract from main chat
                sys.stdout.write(
                    f"\r-> {entity.title} - Extracting messages from main chat"
                )
                sys.stdout.flush()
                general_topic = type("obj", (object,), {"id": 0, "title": "General"})()
                total_messages = await self.extract_from_topic(
                    entity, general_topic, last_msg_ids
                )

            # Calculate and display group extraction speed
            elapsed_time = time.time() - start_time
            if elapsed_time > 0 and total_messages > 0:
                speed = total_messages / elapsed_time
                print(
                    f"\n-> {entity.title} - Group completed: {total_messages} messages ({speed:.1f} msg/sec)"
                )
            elif total_messages > 0:
                print(
                    f"\n-> {entity.title} - Group completed: {total_messages} messages"
                )
        except FloodWaitError as fwe:
            logging.warning(
                f"Flood wait error for group {group_id}. Waiting for {fwe.seconds} seconds."
            )
            await asyncio.sleep(fwe.seconds)
            total_messages = await self.extract_from_group_id(
                group_id, last_msg_ids
            )  # Retry
        except Exception as e:
            logging.exception(f"Error processing group {group_id}: {e}")

        return total_messages
