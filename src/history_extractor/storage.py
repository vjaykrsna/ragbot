import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.core.app import AppContext


class Storage:
    """
    Handles data storage and progress tracking for the history extraction process.

    Args:
        app_context: The application context.
    """

    def __init__(self, app_context: AppContext):
        self.app_context = app_context
        self.settings = app_context.settings

    def save_messages_to_db(
        self, chat_title: str, topic_id: int, messages: List[Dict[str, Any]]
    ):
        """
        Saves a list of messages to the database.

        Args:
            chat_title: The title of the chat the messages are from.
            topic_id: The ID of the topic the messages are from.
            messages: A list of messages to save.
        """
        db = self.app_context.db
        ingestion_ts = datetime.now(timezone.utc).isoformat()
        for msg in messages:
            msg["source_name"] = chat_title
            msg["source_group_id"] = msg.get("group_id")
            msg["source_topic_id"] = topic_id
            msg["source_saved_file"] = None  # No longer saving to individual files
            msg["ingestion_timestamp"] = ingestion_ts
        db.insert_messages(messages)

    def load_last_msg_ids(self) -> Dict[str, int]:
        """
        Loads the last processed message ID for each topic from a file.

        Returns:
            A dictionary mapping topic keys to the last processed message ID.
        """
        if os.path.exists(self.settings.paths.tracking_file):
            with open(self.settings.paths.tracking_file, "r") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}  # Return empty dict if file is corrupted
        return {}

    def save_last_msg_ids(self, data: Dict[str, int]):
        """
        Saves the last processed message ID for each topic to a file.

        Args:
            data: A dictionary mapping topic keys to the last processed message ID.
        """
        with open(self.settings.paths.tracking_file, "w") as f:
            json.dump(data, f, indent=2)
