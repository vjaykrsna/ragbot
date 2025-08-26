import asyncio
import time
from datetime import datetime
from typing import Any, Dict, Tuple

import structlog
from pyrogram import Client
from pyrogram.errors import FloodWait

from src.core.error_handler import (
    default_alert_manager,
    handle_critical_errors,
    retry_with_backoff,
)
from src.history_extractor.memory_utils import (
    calculate_dynamic_batch_size,
    estimate_message_size,
    get_memory_usage_mb,
)
from src.history_extractor.message_processor import get_message_details
from src.history_extractor.storage import Storage
from src.history_extractor.utils import normalize_title

logger = structlog.get_logger(__name__)


class GeneralTopic:
    """A mock topic object for regular groups that are not forums."""

    def __init__(self):
        self.id = 0
        self.title = "General"


class TelegramExtractor:
    """
    Extracts messages from Telegram groups and topics.

    Args:
        client: The Telegram client.
        storage: The storage object.
    """

    def __init__(self, client: Client, storage: Storage, settings=None, metrics=None):
        """
        Initializes the TelegramExtractor.

        Args:
            client: The Pyrogram client instance.
            storage: The storage instance for saving messages.
            settings: Application settings (optional, will be loaded if not provided).
            metrics: Metrics instance for tracking (optional, will be created if not provided).
        """
        if not client or not storage:
            raise ValueError("Client and storage are required")
        self.client = client
        self.storage = storage

        # Initialize settings
        if settings is None:
            from src.core.config import get_settings

            self.settings = get_settings()
        else:
            self.settings = settings

        # Initialize metrics
        if metrics is None:
            from src.core.metrics import Metrics

            self.metrics = Metrics()
        else:
            self.metrics = metrics

    async def extract_from_topic(
        self,
        entity: Any,
        topic: Any,
        last_msg_ids: Dict[Tuple[int, int], int],
        last_msg_ids_lock=None,
    ) -> int:
        """
        Extracts all new messages from a specific group topic or regular group.

        Args:
            entity: The entity to extract messages from.
            topic: The topic to extract messages from (for forums) or a mock topic object with id=0 for regular groups.
            last_msg_ids: A dictionary mapping topic keys to the last processed message ID.

        Returns:
            The number of messages extracted.
        """
        group_id = entity.id
        topic_id = topic.message_thread_id
        topic_title = normalize_title(getattr(topic, "name", "General"))
        last_id_key = (group_id, topic_id)
        last_id = last_msg_ids.get(last_id_key, 0)
        max_id = 0

        # Start timing the extraction process
        start_time = time.time()
        start_time_dt = datetime.now()

        # Initialize variables at the start of the method
        message_size_estimate = 0  # Initialize with default value
        batch_size = (
            self.settings.telegram.extraction.batch_size
        )  # Use configurable batch size
        message_batch = []
        total_saved = 0
        processed_count = 0
        saved_count = 0
        max_id = 0
        last_update_time_dt = start_time_dt  # Initialize with start time

        logger.info(
            f"  - 📥 Extracting from topic: '{topic_title}' (ID: {topic_id}) [Since message ID > {last_id}]"
        )

        chat_history = self.client.get_chat_history(
            entity.id if hasattr(entity, "id") else entity, offset_id=last_id
        )
        if chat_history is not None:
            async for msg in chat_history:
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
                    processed_count += 1
                    # Update progress display every N messages or every M seconds (based on config)
                    current_time = datetime.now()
                    elapsed_since_last_update = (
                        current_time - last_update_time_dt
                    ).total_seconds()
                    if (
                        processed_count
                        % self.settings.telegram.extraction.progress_update_messages
                        == 0
                        or elapsed_since_last_update
                        > self.settings.telegram.extraction.ui_update_interval
                    ):
                        elapsed_total = (current_time - start_time_dt).total_seconds()
                        speed = (
                            processed_count / elapsed_total if elapsed_total > 0 else 0
                        )
                        memory_usage = get_memory_usage_mb()
                        # Use \r to overwrite the same line
                        print(
                            f"\r    💬 {topic_title:<20} | "
                            f"Messages: {processed_count:>6} | "
                            f"Saved: {saved_count:>6} | "
                            f"Speed: {speed:>5.1f} msg/sec | "
                            f"Memory: {memory_usage:>6.1f}MB",
                            end="",
                            flush=True,
                        )
                        last_update_time_dt = current_time
                    continue

                try:
                    message_type, content, extra_data = get_message_details(msg)
                except Exception as e:
                    logger.warning(f"Failed to process message {msg.id}: {e}")
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

                message_dict = {
                    "id": msg.id,
                    "date": (
                        msg.date.isoformat()
                        if isinstance(msg.date, datetime)
                        else datetime.fromtimestamp(msg.date).isoformat()
                    ),
                    "sender_id": sender_id,
                    "message_type": message_type,
                    "content": content,
                    "extra_data": extra_data,
                    "reply_to_msg_id": getattr(msg, "reply_to_message_id", None),
                    "topic_id": topic_id,
                    "topic_title": topic_title,
                    "source_name": (
                        entity.title if hasattr(entity, "title") else str(entity)
                    ),
                    "source_group_id": entity.id if hasattr(entity, "id") else group_id,
                    "ingestion_timestamp": datetime.now().isoformat(),
                }

                # Estimate message size for dynamic batch sizing
                if processed_count == 1:  # Estimate size from first message
                    message_size_estimate = estimate_message_size(message_dict)
                    # Adjust batch size based on available memory
                    batch_size = calculate_dynamic_batch_size(
                        self.settings.telegram.extraction.batch_size,
                        message_size_estimate,
                    )

                message_batch.append(message_dict)
                max_id = max(max_id, msg.id)
                processed_count += 1
                saved_count += 1

                # Update progress display every N messages or every M seconds (based on config)
                current_time = datetime.now()
                elapsed_since_last_update = (
                    current_time - last_update_time_dt
                ).total_seconds()
                if (
                    processed_count
                    % self.settings.telegram.extraction.progress_update_messages
                    == 0
                    or elapsed_since_last_update
                    > self.settings.telegram.extraction.ui_update_interval
                ):
                    elapsed_total = (current_time - start_time_dt).total_seconds()
                    speed = processed_count / elapsed_total if elapsed_total > 0 else 0
                    memory_usage = get_memory_usage_mb()
                    # Use \r to overwrite the same line
                    print(
                        f"\r    💬 {topic_title:<20} | "
                        f"Messages: {processed_count:>6} | "
                        f"Saved: {saved_count:>6} | "
                        f"Speed: {speed:>5.1f} msg/sec | "
                        f"Memory: {memory_usage:>6.1f}MB",
                        end="",
                        flush=True,
                    )
                    last_update_time_dt = current_time

                # When batch is full, save to database
                if len(message_batch) >= batch_size:
                    if message_batch:
                        full_title = f"{entity.title}_{topic_title}"
                        self.storage.save_messages_to_db(
                            full_title, topic_id, message_batch
                        )
                        total_saved += len(message_batch)
                        self.metrics.record_messages(len(message_batch))
                        message_batch = []  # Clear the batch

                        # Log metrics periodically
                        if (
                            total_saved
                            % (
                                self.settings.telegram.extraction.progress_update_messages
                                * 5
                            )
                            == 0
                        ):
                            self.metrics.log_summary()

                        # Re-estimate batch size after each batch to adapt to changing conditions
                        if processed_count > 1:
                            batch_size = calculate_dynamic_batch_size(
                                self.settings.telegram.extraction.batch_size,
                                message_size_estimate,
                            )

        # Save any remaining messages in the batch
        if message_batch:
            full_title = f"{entity.title}_{topic_title}"
            self.storage.save_messages_to_db(full_title, topic_id, message_batch)
            total_saved += len(message_batch)
            self.metrics.record_messages(len(message_batch))

        # Update last message ID with thread-safe access
        if total_saved > 0 and max_id > 0:
            if last_msg_ids_lock:
                async with last_msg_ids_lock:
                    last_msg_ids[last_id_key] = max_id
            else:
                last_msg_ids[last_id_key] = max_id

        # Log final metrics
        if total_saved > 0:
            self.metrics.log_summary()

        # Display final extraction information on a new line
        if processed_count > 0:
            elapsed_total = (datetime.now() - start_time_dt).total_seconds()
            speed = processed_count / elapsed_total if elapsed_total > 0 else 0
            memory_usage = get_memory_usage_mb()
            print(
                f"\r    ✅ {topic_title:<20} | "
                f"Messages: {processed_count:>6} | "
                f"Saved: {total_saved:>6} | "
                f"Speed: {speed:>5.1f} msg/sec | "
                f"Memory: {memory_usage:>6.1f}MB"
            )

            extraction_time = time.time() - start_time
            extraction_speed = (
                processed_count / extraction_time if extraction_time > 0 else 0
            )
            print(
                f"\n📊 Summary for {entity.title}/{topic_title} | "
                f"Total: {total_saved} messages | "
                f"Speed: {extraction_speed:.1f} msg/sec | "
                f"Duration: {extraction_time:.1f}s"
            )
        else:
            logger.info(f"    📝 No new messages in '{topic_title}'")
            print(
                f"\n📊 Summary for {entity.title}/{topic_title} | "
                f"Total: {total_saved} messages | "
                f"Status: No new messages"
            )

        return total_saved

    @retry_with_backoff(max_retries=3, initial_wait=5.0, backoff_factor=2.0)
    @handle_critical_errors(default_alert_manager)
    async def extract_from_group_id(
        self,
        group_id: int,
        last_msg_ids: Dict[Tuple[int, int], int],
        entity=None,
        last_msg_ids_lock=None,
    ) -> int:
        """
        Extracts messages from a specific group ID.

        Args:
            group_id: The ID of the group to extract messages from.
            last_msg_ids: A dictionary mapping topic keys to the last processed message ID.
            entity: Optional pre-fetched group entity to avoid redundant API calls.

        Returns:
            The total number of messages extracted from the group.
        """
        total_messages = 0
        try:
            # Use pre-fetched entity if provided, otherwise fetch it
            if entity is None:
                entity = await self.client.get_chat(group_id)
            logger.info(f"\nProcessing Group: {entity.title} (ID: {group_id})")

            # Try to get forum topics. This is now much simpler with the new library.
            topics = []
            try:
                async for topic in self.client.get_forum_topics(entity.id):
                    topics.append(topic)
            except Exception as e:
                logger.warning(
                    f"Could not fetch topics for group {entity.id}. "
                    f"This might be a regular group or an error occurred: {e}"
                )

            if topics:
                self.storage.save_topics(topics, group_id)
                logger.info(f"📋 Found {len(topics)} topics:")

                # Display topic list upfront
                for i, topic in enumerate(topics, 1):
                    topic_title = normalize_title(getattr(topic, "name", "General"))
                    logger.info(f"  {i:2d}. {topic_title}")

                logger.info(f"🔄 Starting extraction of {len(topics)} topics...")

                # Process topics with progress tracking
                for i, topic in enumerate(topics, 1):
                    topic_title = normalize_title(getattr(topic, "name", "General"))
                    logger.info(
                        f"📊 Processing topic {i}/{len(topics)}: '{topic_title}'"
                    )
                    count = await self.extract_from_topic(
                        entity, topic, last_msg_ids, last_msg_ids_lock
                    )
                    total_messages += count
            else:
                # Check if it's marked as a forum but has no topics, or if it's a regular group
                is_forum = getattr(entity, "is_forum", False)
                if is_forum:
                    logger.info("  - Forum group with no topics found. Skipping.")
                else:
                    logger.info(
                        "  - This is a regular group. Extracting from main chat."
                    )

                    # Create a proper GeneralTopic object instead of using type() hack
                    general_topic = GeneralTopic()
                    count = await self.extract_from_topic(
                        entity, general_topic, last_msg_ids, last_msg_ids_lock
                    )
                    total_messages += count
        except FloodWait as fwe:
            logger.warning(
                f"Flood wait error for group {group_id}. Waiting for {fwe.value} seconds."
            )
            self.metrics.record_error("FloodWait")
            # Show a message every 30 seconds while waiting
            wait_time = fwe.value
            while wait_time > 0:
                if wait_time % 30 == 0 or wait_time < 30:
                    logger.info(f"Waiting for {wait_time} more seconds...")
                await asyncio.sleep(min(30, wait_time))
                wait_time -= 30
            # Retry after flood wait
            total_messages = await self.extract_from_group_id(
                group_id, last_msg_ids, entity, last_msg_ids_lock
            )
        except Exception as e:
            logger.exception(f"❌ Error processing group {group_id}: {e}")
            self.metrics.record_error("GeneralException")
            # The function already has retry decorator, so just re-raise to trigger it
            raise

        return total_messages
